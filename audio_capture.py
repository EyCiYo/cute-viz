import os
import queue
import re
import subprocess
import threading
from threading import Lock

import numpy as np


class AudioCapture:
    def __init__(self, num_bars=32, buffer_size=1024, attack_alpha=0.45, fall_speed=0.03):
        self.num_bars = num_bars
        self.buffer_size = buffer_size
        self.attack_alpha = attack_alpha
        self.fall_speed = fall_speed

        self.lock = Lock()
        self.sample_rate = None
        self.bin_starts = None
        self.bin_ends = None

        self.magnitudes = np.zeros(num_bars, dtype=np.float32)
        self.smoothed = np.zeros(num_bars, dtype=np.float32)
        self.global_max = 100.0
        self.stream = None
        self.running = False
        self.process_thread = None
        self.audio_queue = queue.Queue(maxsize=4)

        self.hann = np.hanning(buffer_size).astype(np.float32)

        t = np.linspace(0, 1, num_bars)
        comp_db = 38 * (3 * t**2 - 2 * t**3)
        self.freq_gain = (10 ** (comp_db / 20)).astype(np.float32)

    @staticmethod
    def find_monitor_source():
        result = subprocess.run(["pactl", "info"], capture_output=True, text=True)
        m = re.search(r"Default Sink: (.+)", result.stdout)
        if not m:
            raise RuntimeError("Could not find default sink via pactl")
        sink = m.group(1).strip()
        return f"{sink}.monitor"

    def _init_bin_mapping(self):
        n_fft = self.buffer_size // 2 + 1
        max_freq_bin = int(16000 / (self.sample_rate / self.buffer_size))
        max_bin = min(max_freq_bin, n_fft - 1)

        edges = np.logspace(np.log10(2), np.log10(max_bin), self.num_bars + 1)
        edges = np.round(edges).astype(int)
        edges = np.clip(edges, 1, n_fft - 1)

        unique = [edges[0]]
        for e in edges[1:]:
            if e > unique[-1]:
                unique.append(e)
        while len(unique) < self.num_bars + 1:
            unique.append(min(unique[-1] + 1, n_fft - 1))
        edges = np.array(unique[:self.num_bars + 1], dtype=int)

        self.bin_starts = edges[:-1]
        self.bin_ends = edges[1:]

    def start(self):
        source = self.find_monitor_source()
        os.environ["PULSE_SOURCE"] = source

        import sounddevice as sd

        info = sd.query_devices("pulse")
        samplerate = int(info["default_samplerate"])
        self.sample_rate = samplerate
        self._init_bin_mapping()

        self.stream = sd.InputStream(
            device="pulse",
            channels=1,
            samplerate=samplerate,
            blocksize=self.buffer_size,
            callback=self._audio_callback,
        )
        self.stream.start()

        self.running = True
        self.process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.process_thread.start()

        return source

    def stop(self):
        self.running = False
        if self.process_thread:
            self.process_thread.join(timeout=1.0)
        if self.stream:
            self.stream.stop()
            self.stream.close()

    def _audio_callback(self, indata, frames, time, status):
        if status:
            return
        try:
            self.audio_queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass

    def _process_loop(self):
        while self.running:
            try:
                audio = self.audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            audio = audio.astype(np.float32) * self.hann
            fft = np.abs(np.fft.rfft(audio))

            bars = np.zeros(self.num_bars, dtype=np.float32)
            for i in range(self.num_bars):
                s, e = int(self.bin_starts[i]), int(self.bin_ends[i])
                bars[i] = np.mean(fft[s:e]) if e > s else fft[s]

            bars = bars * self.freq_gain

            current_max = np.max(bars)
            if current_max > self.global_max:
                self.global_max += (current_max - self.global_max) * 0.08
            else:
                self.global_max *= 0.9998
            self.global_max = max(self.global_max, 10.0)

            bars = bars / self.global_max
            bars[bars < 0.01] = 0.0
            bars = np.clip(bars, 0.0, 1.0)

            attack = self.smoothed * (1 - self.attack_alpha) + bars * self.attack_alpha
            decay = self.smoothed - self.fall_speed
            self.smoothed = np.maximum(np.maximum(attack, decay), 0.0)

            with self.lock:
                self.magnitudes = self.smoothed.copy()

    def get_magnitudes(self):
        with self.lock:
            return self.magnitudes.copy()
