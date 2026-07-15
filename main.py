import sys

import pyglet
pyglet.options["shadow_window"] = False
from pyglet import shapes, text
from pyglet.window import key

from audio_capture import AudioCapture
from visualizer import Visualizer, THEME_NAMES, MODES

WIDTH, HEIGHT = 800, 600
NUM_BARS = 32
PANEL_W, PANEL_H = 420, 300

window = pyglet.window.Window(WIDTH, HEIGHT, caption="Audio Visualizer", vsync=False)

capture = AudioCapture(num_bars=NUM_BARS)
visualizer = Visualizer(WIDTH, HEIGHT, NUM_BARS)

show_panel = False

try:
    font_title_name = "DejaVu Sans Mono"
    font_title_size = 16
    font_body_name = "DejaVu Sans Mono"
    font_body_size = 14
except Exception:
    font_title_name = "monospace"
    font_title_size = 16
    font_body_name = "monospace"
    font_body_size = 14

panel_overlay = shapes.Rectangle(0, 0, PANEL_W, PANEL_H, color=(8, 10, 22))
panel_overlay.opacity = 0

panel_title = text.Label(
    "P R E F E R E N C E S", font_name=font_title_name,
    font_size=font_title_size, weight="bold",
    x=0, y=0, anchor_x="center", anchor_y="center",
    color=(200, 210, 230, 255),
)

panel_labels = []
panel_hints = []
panel_values = []
panel_value_texts = []
panel_ys = []
y_start = 90
line_h = 52
for i, (label, hint, _) in enumerate([
    ("Mode", "[1] Dots   [2] Blocks   [3] Bars", ""),
    ("Theme", "[C] Cycle", ""),
    ("Peaks", "[P] Toggle", ""),
]):
    y = y_start + i * line_h
    panel_ys.append(y)
    panel_labels.append(text.Label(
        label, font_name=font_body_name,
        font_size=font_body_size, weight="normal",
        x=0, y=0, anchor_y="center",
        color=(140, 150, 170, 255),
    ))
    panel_hints.append(text.Label(
        hint, font_name=font_body_name,
        font_size=font_body_size, weight="normal",
        x=0, y=0,
        color=(80, 85, 100, 255),
    ))
    v = text.Label(
        "", font_name=font_body_name,
        font_size=font_body_size, weight="normal",
        x=0, y=0,
        anchor_x="right", color=(100, 200, 255, 255),
    )
    panel_values.append(v)
    panel_value_texts.append("")

panel_close = text.Label(
    "[M] Close", font_name=font_body_name,
    font_size=font_body_size, weight="normal",
    x=0, y=0,
    anchor_x="center", color=(80, 85, 100, 255),
)

fps_label = text.Label(
    "", font_name=font_body_name, font_size=11, weight="normal",
    x=8, y=HEIGHT - 12, color=(100, 100, 100, 180),
)


def update_panel_texts():
    texts = [
        f"{MODES.index(visualizer.mode) + 1}  {visualizer.mode.upper()}",
        visualizer.theme_name.upper(),
        "ON" if visualizer.show_peaks else "OFF",
    ]
    for i, t in enumerate(texts):
        if t != panel_value_texts[i]:
            panel_values[i].text = t
            panel_value_texts[i] = t


def draw_panel():
    px = (WIDTH - PANEL_W) // 2
    py = (HEIGHT - PANEL_H) // 2

    panel_overlay.x = px
    panel_overlay.y = py
    panel_overlay.opacity = 230
    panel_overlay.draw()

    panel_title.x = px + PANEL_W // 2
    panel_title.y = py + PANEL_H - 30
    panel_title.draw()

    for i in range(len(panel_labels)):
        ry = panel_ys[i]
        panel_labels[i].x = px + 30
        panel_labels[i].y = py + ry
        panel_labels[i].draw()
        panel_hints[i].x = px + 30
        panel_hints[i].y = py + ry - 14
        panel_hints[i].draw()
        panel_values[i].x = px + PANEL_W - 30
        panel_values[i].y = py + ry + 4
        panel_values[i].draw()
    panel_close.x = px + PANEL_W // 2
    panel_close.y = py + 25
    panel_close.draw()


def draw_frame(dt):
    window.clear()
    mags = capture.get_magnitudes()
    visualizer.draw(mags)
    fps_label.text = f"{pyglet.clock.get_frequency():.0f} FPS"
    fps_label.draw()
    if show_panel:
        update_panel_texts()
        draw_panel()
    window.flip()


@window.event
def on_key_press(symbol, modifiers):
    global show_panel

    if symbol == key.M:
        show_panel = not show_panel

    elif symbol == key._1:
        visualizer.set_mode("dots")
    elif symbol == key._2:
        visualizer.set_mode("blocks")
    elif symbol == key._3:
        visualizer.set_mode("bars")
    elif symbol == key.C:
        idx = THEME_NAMES.index(visualizer.theme_name)
        visualizer.set_theme(THEME_NAMES[(idx + 1) % len(THEME_NAMES)])
    elif symbol == key.P:
        visualizer.show_peaks = not visualizer.show_peaks

    return pyglet.event.EVENT_HANDLED


@window.event
def on_close():
    capture.stop()
    pyglet.app.exit()


def run():
    try:
        source = capture.start()
        print(f"Capturing from: {source}", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        sys.exit(1)

    pyglet.clock.schedule(draw_frame)
    pyglet.app.run()
    capture.stop()


if __name__ == "__main__":
    run()
