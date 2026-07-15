import pyglet
from pyglet import shapes, text
import numpy as np

THEMES = {
    "neon":   [(25, 55, 195), (0, 175, 215), (155, 55, 195), (215, 55, 95), (250, 135, 25)],
    "fire":   [(80, 0, 0), (200, 30, 0), (255, 100, 0), (255, 180, 0), (255, 230, 100)],
    "ocean":  [(10, 30, 100), (0, 80, 140), (0, 140, 160), (50, 190, 180), (150, 220, 210)],
    "pastel": [(150, 170, 255), (150, 230, 240), (220, 170, 240), (255, 170, 190), (255, 210, 150)],
    "mono":   [(50, 55, 75), (80, 85, 110), (120, 125, 150), (170, 175, 195), (220, 225, 235)],
}
THEME_NAMES = list(THEMES.keys())
MODES = ["dots", "blocks", "bars"]


def _interp(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _make_gradient(stops, n):
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        for j in range(len(stops) - 1):
            t0, c0 = stops[j]
            t1, c1 = stops[j + 1]
            if t0 <= t <= t1:
                out.append(_interp(c0, c1, (t - t0) / (t1 - t0)))
                break
        else:
            out.append(stops[-1][1])
    return out


class Visualizer:
    def __init__(self, width, height, num_bars=32):
        self.width = width
        self.height = height
        self.num_bars = num_bars
        self.num_rows = 20

        self.mode = "dots"
        self.theme_name = "neon"
        self.show_peaks = True

        self.peaks = np.zeros(num_bars, dtype=float)
        self.peak_speed = 0.03

        self.mx = 30
        self.my = 18
        self.bm = 10

        self._compute_layout()
        self._update_colors()
        self._create_background()

        self.batch = pyglet.graphics.Batch()
        self._current_mode_shapes = None

    def _compute_layout(self):
        n = self.num_bars
        r = self.num_rows
        aw = self.width - 2 * self.mx
        ah = self.height - self.my - self.bm

        self.cell_w = aw / n
        self.cell_h = ah / r
        self.dot_r = max(2, int(min(self.cell_w, self.cell_h) * 0.22))
        self.blk_s = max(2, int(min(self.cell_w, self.cell_h) * 0.45))

        bit = self.bm
        self.dot_pos = np.zeros((n, r, 2), dtype=int)
        for c in range(n):
            px = int(self.mx + c * self.cell_w + self.cell_w / 2)
            for row in range(r):
                py = int(bit + row * self.cell_h + self.cell_h / 2)
                self.dot_pos[c, row] = (px, py)

        self.blk_rects = np.zeros((n, r, 4), dtype=int)
        for c in range(n):
            rx = int(self.mx + c * self.cell_w + (self.cell_w - self.blk_s) / 2)
            for row in range(r):
                ry = int(bit + row * self.cell_h - self.blk_s / 2)
                self.blk_rects[c, row] = (rx, max(ry, 0), self.blk_s, self.blk_s)

        bar_aw = self.width - 40
        gap = 3
        bw = max(2, (bar_aw - (n - 1) * gap) // n)
        tw = bw * n + gap * (n - 1)
        mg = (self.width - tw) // 2
        self.bar_w = bw
        self.bar_gap = gap
        self.bar_margin = mg
        self.bar_h = ah
        self.bar_xs = [mg + i * (bw + gap) for i in range(n)]
        self.bar_cxs = [x + bw // 2 for x in self.bar_xs]

    def _update_colors(self):
        stops = [(i / 4, THEMES[self.theme_name][i]) for i in range(5)]
        self.bar_colors = _make_gradient(stops, self.num_bars)
        row_stops = [(0, THEMES[self.theme_name][0]),
                     (0.5, THEMES[self.theme_name][2]),
                     (1, THEMES[self.theme_name][4])]
        self.row_colors = _make_gradient(row_stops, self.num_rows)

        peak_top = THEMES[self.theme_name][4]
        peak_bot = THEMES[self.theme_name][0]
        self.peak_color = tuple(min(255, c + 40) for c in _interp(peak_bot, peak_top, 0.5))

    def _create_background(self):
        self.bg_batch = pyglet.graphics.Batch()
        n_bands = 8
        band_h = self.height // n_bands
        for i in range(n_bands):
            t = (i + 0.5) / n_bands
            r = int(7 + 5 * t)
            g = int(9 + 6 * t)
            b = int(17 + 7 * t)
            shapes.Rectangle(0, i * band_h, self.width, band_h + 1,
                             color=(r, g, b), batch=self.bg_batch)

    def set_mode(self, mode):
        if mode in MODES and mode != self.mode:
            self.mode = mode
            self._current_mode_shapes = None

    def set_theme(self, name):
        if name in THEMES:
            self.theme_name = name
            self._update_colors()
            self._current_mode_shapes = None

    def _rebuild_shapes(self):
        self.batch = pyglet.graphics.Batch()
        self.mode_shapes = []
        self.peak_indicators = []

        if self.mode == "dots":
            self._build_dots()
        elif self.mode == "blocks":
            self._build_blocks()
        elif self.mode == "bars":
            self._build_bars()

        self._build_peaks()
        self._current_mode_shapes = self.mode

    def _build_dots(self):
        r = self.dot_r
        for c in range(self.num_bars):
            col = self.bar_colors[c]
            for row in range(self.num_rows):
                x, y = self.dot_pos[c, row]
                circle = shapes.Circle(x, y, r, color=col, batch=self.batch)
                circle.opacity = 0
                self.mode_shapes.append(circle)

    def _build_blocks(self):
        bs = self.blk_s
        for c in range(self.num_bars):
            col = self.bar_colors[c]
            for row in range(self.num_rows):
                x, y, w, h = self.blk_rects[c, row]
                rect = shapes.Rectangle(x, y, w, h, color=col, batch=self.batch)
                rect.opacity = 0
                self.mode_shapes.append(rect)

    def _build_bars(self):
        bw = self.bar_w
        for c in range(self.num_bars):
            col = self.bar_colors[c]
            rect = shapes.Rectangle(self.bar_xs[c], self.bm, bw, 0, color=col, batch=self.batch)
            rect.opacity = 0
            self.mode_shapes.append(rect)

    def _build_peaks(self):
        for c in range(self.num_bars):
            if self.mode == "dots":
                p = shapes.Circle(0, 0, self.dot_r + 1, color=self.peak_color, batch=self.batch)
            elif self.mode == "blocks":
                p = shapes.Rectangle(0, 0, self.blk_s, self.blk_s, color=self.peak_color, batch=self.batch)
            else:
                p = shapes.Circle(0, 0, 2, color=self.peak_color, batch=self.batch)
            p.opacity = 0
            self.peak_indicators.append(p)

    def draw(self, magnitudes):
        if self._current_mode_shapes != self.mode:
            self._rebuild_shapes()

        self.bg_batch.draw()

        mags = np.asarray(magnitudes)
        decay = self.peak_speed * (1 if self.show_peaks else 3)

        if self.mode == "dots":
            r = self.dot_r
            stride = self.num_rows
            for c in range(self.num_bars):
                m = mags[c] if c < len(mags) else 0
                lit = int(m * self.num_rows)
                base = c * stride
                for row in range(self.num_rows):
                    circle = self.mode_shapes[base + row]
                    circle.opacity = 255 if row < lit else 0

                p = m - self.peaks[c]
                if p > 0:
                    self.peaks[c] = m
                else:
                    self.peaks[c] = max(0, self.peaks[c] - decay)
                pr = int(self.peaks[c] * self.num_rows)
                if pr < self.num_rows and self.show_peaks:
                    px, py = self.dot_pos[c, pr]
                    peak = self.peak_indicators[c]
                    peak.opacity = 255
                    peak.x = px
                    peak.y = py
                else:
                    self.peak_indicators[c].opacity = 0

        elif self.mode == "blocks":
            stride = self.num_rows
            for c in range(self.num_bars):
                m = mags[c] if c < len(mags) else 0
                lit = int(m * self.num_rows)
                base = c * stride
                for row in range(self.num_rows):
                    rect = self.mode_shapes[base + row]
                    rect.opacity = 255 if row < lit else 0

                p = m - self.peaks[c]
                if p > 0:
                    self.peaks[c] = m
                else:
                    self.peaks[c] = max(0, self.peaks[c] - decay)
                pr = int(self.peaks[c] * self.num_rows)
                if pr < self.num_rows and self.show_peaks:
                    px, py = self.blk_rects[c, pr][:2]
                    peak = self.peak_indicators[c]
                    peak.opacity = 255
                    peak.x = px
                    peak.y = py
                else:
                    self.peak_indicators[c].opacity = 0

        elif self.mode == "bars":
            for c in range(self.num_bars):
                m = mags[c] if c < len(mags) else 0
                h = int(m * self.bar_h)
                rect = self.mode_shapes[c]
                if h > 0:
                    rect.opacity = 255
                    rect.y = self.bm
                    rect.height = h
                else:
                    rect.opacity = 0

                p = m - self.peaks[c]
                if p > 0:
                    self.peaks[c] = m
                else:
                    self.peaks[c] = max(0, self.peaks[c] - decay)
                py = self.bm + int(self.peaks[c] * self.bar_h)
                if py > self.bm and self.show_peaks:
                    peak = self.peak_indicators[c]
                    peak.opacity = 255
                    peak.x = self.bar_cxs[c]
                    peak.y = py
                else:
                    self.peak_indicators[c].opacity = 0

        self.batch.draw()
