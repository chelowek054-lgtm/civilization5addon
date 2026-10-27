"""Compact in-game overlay (Dear PyGui): one graph, the must-watch numbers and
a one-line tip. Sits on the left edge under the science panel, borderless,
always on top. The full analysis window (civstats.py) opens with the "+" button.

    python viewer/overlay.py [saved_game.log]
"""
import os
import subprocess
import sys
import time

import dearpygui.dearpygui as dpg

import advisor
from civstats import LOG_PATH, Data
from metrics_tree import compute_indices

TITLE = "Civ5 Stats Overlay"
WIDTH, HEIGHT = 340, 450
POS = (6, 132)           # left edge, just under the science / tech panel at 1080p
REFRESH_S = 2.0
ALPHAS = (0.88, 0.7, 1.0)

GOOD, BAD, WARN, DIM = (110, 210, 120), (240, 90, 80), (240, 190, 70), (170, 170, 170)
PALETTE = [(31, 119, 180), (255, 127, 14), (44, 160, 44), (214, 39, 40), (148, 103, 189),
           (140, 86, 75), (227, 119, 194), (127, 127, 127), (188, 189, 34), (23, 190, 207)]
ROWS = [("power", "Общая сила"), ("science", "Наука/ход"), ("gold", "Золото/ход"),
        ("army", "Армия"), ("happy", "Довольство"), ("cities", "Города"), ("era", "Эпоха")]
LEVEL_COLOR = {"red": BAD, "yellow": WARN, "green": GOOD}
# Clicking a row opens the full window on this metric-tree node (None = advisor view)
ROW_NODE = {"power": "overall", "science": "g_science", "gold": "g_economy", "army": "g_military",
            "happy": "g_stability", "cities": "g_scale", "era": None}

IS_WIN = sys.platform == "win32"


# ---------- window tricks (Windows only; elsewhere the viewport keeps its frame) ----------

def _hwnd():
    import ctypes
    return ctypes.windll.user32.FindWindowW(None, TITLE)


def set_alpha(alpha):
    if not IS_WIN:
        return
    import ctypes
    u = ctypes.windll.user32
    h = _hwnd()
    u.SetWindowLongW(h, -20, u.GetWindowLongW(h, -20) | 0x80000)   # WS_EX_LAYERED
    u.SetLayeredWindowAttributes(h, 0, int(255 * alpha), 2)         # LWA_ALPHA


def start_native_drag():
    import ctypes
    u = ctypes.windll.user32
    u.ReleaseCapture()
    u.SendMessageW(_hwnd(), 0xA1, 2, 0)   # WM_NCLBUTTONDOWN on HTCAPTION


# ---------- data -> what we show ----------

def rank_of(values, mine, higher_better=True):
    return 1 + sum(1 for v in values if (v > mine if higher_better else v < mine))


def rank_color(rank, total):
    if total <= 1:
        return DIM
    if rank == 1:
        return GOOD
    if rank == total:
        return BAD
    return None


def summarize(data):
    """Returns (series for the graph, rows {key: (value_text, rank_text, color)}, tip (text, color))."""
    pids = data.visible(False)
    me = data.me
    if me is None or me not in data.series or not data.series[me]:
        return [], {}, ("Ждём данных из игры…", DIM)
    idx = compute_indices(data.series, pids)
    t = max(data.series[me])
    s = data.series[me][t]
    others = [data.series[p][t] for p in pids if p != me and t in data.series[p]]
    total = len(others) + 1

    graph = []
    for i, p in enumerate(pids):
        turns = sorted(idx[p])
        graph.append((p == me, data.names.get(p, str(p)), PALETTE[i % len(PALETTE)],
                      turns, [idx[p][x].get("overall", 0) for x in turns]))

    rows = {}
    ov = idx[me].get(t, {}).get("overall", 0)
    r = rank_of([idx[p][t].get("overall", 0) for p in pids if p != me and t in idx[p]], ov)
    rows["power"] = (f"{ov:.0f}/100", f"{r}/{total}", rank_color(r, total))

    v = s.get("science", 0)
    r = rank_of([o.get("science", 0) for o in others], v)
    rows["science"] = (f"{v:g}", f"{r}/{total}", rank_color(r, total))

    g, bank = s.get("goldRate", 0), s.get("gold", 0)
    r = rank_of([o.get("goldRate", 0) for o in others], g)
    rows["gold"] = (f"{g:+g} ({bank:g})", f"{r}/{total}", BAD if g < 0 else rank_color(r, total))

    m = s.get("military", 0)
    top = max([o.get("military", 0) for o in others] or [0])
    ratio = m / top if top else 1
    r = rank_of([o.get("military", 0) for o in others], m)
    rows["army"] = (f"{ratio:.0%} от сильн.", f"{r}/{total}",
                    BAD if ratio < 0.3 else WARN if ratio < 0.6 else GOOD)

    h = s.get("happiness", 0)
    rows["happy"] = (f"{h:+g}", "", BAD if h < -10 else WARN if h < 0 else GOOD)

    c = s.get("cities", 0)
    avg = sum(o.get("cities", 0) for o in others) / len(others) if others else c
    rows["cities"] = (f"{c:g} (ср. {avg:.1f})", "", BAD if c < avg - 1 else WARN if c < avg else GOOD)

    civ = data.names.get(me, "")
    era = advisor.current_era(s)
    spikes = advisor.spike_eras(civ)
    era_name = advisor.ERA_NAMES.get(era, str(era))
    rows["era"] = (era_name, "ПИК" if era in spikes else "", GOOD if era in spikes else DIM)

    _, warns = advisor.analyse(data, idx, pids)
    level, text = warns[0] if warns else ("green", "")
    return graph, rows, (text, LEVEL_COLOR[level])


# ---------- UI ----------

class Overlay:
    def __init__(self, path):
        self.data = Data(path)
        self.alpha_i = 0
        self.themes = {}
        self.last_poll = 0.0

        dpg.create_context()
        self.load_font()
        self.build()
        dpg.create_viewport(title=TITLE, width=WIDTH, height=HEIGHT, x_pos=POS[0], y_pos=POS[1],
                            always_on_top=True, decorated=not IS_WIN, resizable=False)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main", True)
        set_alpha(ALPHAS[self.alpha_i])

    def load_font(self):
        candidates = [r"C:\Windows\Fonts\segoeui.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                      "/usr/share/fonts/TTF/DejaVuSans.ttf",
                      "/usr/share/fonts/dejavu/DejaVuSans.ttf"]
        path = next((p for p in candidates if os.path.exists(p)), None)
        if not path:
            return
        with dpg.font_registry():
            f = dpg.add_font(path, 15)   # DPG 2.x loads Cyrillic glyphs automatically
        dpg.bind_font(f)

    def line_theme(self, color, mine):
        key = (color, mine)
        if key not in self.themes:
            with dpg.theme() as th:
                with dpg.theme_component(dpg.mvLineSeries):
                    dpg.add_theme_color(dpg.mvPlotCol_Line, color, category=dpg.mvThemeCat_Plots)
                    dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 3.5 if mine else 1.3,
                                        category=dpg.mvThemeCat_Plots)
            self.themes[key] = th
        return self.themes[key]

    def row_button_theme(self):
        """Row labels look like plain grey text but highlight on hover."""
        if "row" not in self.themes:
            with dpg.theme() as th:
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (60, 80, 95, 255))
                    dpg.add_theme_color(dpg.mvThemeCol_Text, DIM)
                    dpg.add_theme_style(dpg.mvStyleVar_ButtonTextAlign, 0, 0.5)
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 2, 0)
            self.themes["row"] = th
        return self.themes["row"]

    def build(self):
        with dpg.theme() as main_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (18, 30, 38, 255))
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 8, 6)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 6, 3)
                dpg.add_theme_style(dpg.mvStyleVar_CellPadding, 4, 1)

        with dpg.window(tag="main", no_scrollbar=True):
            # Title on the left, buttons pinned to the right edge (stretch + fixed column)
            with dpg.table(header_row=False, policy=dpg.mvTable_SizingFixedFit):
                dpg.add_table_column(width_stretch=True)
                dpg.add_table_column(width_fixed=True)
                with dpg.table_row():
                    dpg.add_text("Civ 5 · статистика", tag="title", color=(220, 200, 140))
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="o", width=20, tag="btn_alpha", callback=self.cycle_alpha)
                        with dpg.tooltip(dpg.last_item()):
                            dpg.add_text("Прозрачность")
                        dpg.add_button(label="+", width=20, tag="btn_full", callback=self.open_full)
                        with dpg.tooltip(dpg.last_item()):
                            dpg.add_text("Подробный анализ")
                        dpg.add_button(label="x", width=20, tag="btn_close",
                                       callback=lambda: dpg.stop_dearpygui())

            with dpg.plot(height=170, width=-1, no_menus=True, no_box_select=True, no_mouse_pos=True):
                dpg.add_plot_axis(dpg.mvXAxis, tag="x", no_gridlines=True)
                with dpg.plot_axis(dpg.mvYAxis, tag="y", no_gridlines=False):
                    dpg.set_axis_limits("y", -2, 102)
            dpg.add_text("", tag="leader", color=DIM)

            with dpg.table(header_row=False, borders_innerH=False, policy=dpg.mvTable_SizingStretchProp):
                dpg.add_table_column(init_width_or_weight=0.42)
                dpg.add_table_column(init_width_or_weight=0.42)
                dpg.add_table_column(init_width_or_weight=0.16)
                for key, label in ROWS:
                    with dpg.table_row():
                        dpg.add_button(label=label, width=-1, callback=self.open_full,
                                       user_data=ROW_NODE[key])
                        dpg.bind_item_theme(dpg.last_item(), self.row_button_theme())
                        with dpg.tooltip(dpg.last_item()):
                            dpg.add_text("Открыть подробные графики")
                        dpg.add_text("—", tag=f"v_{key}")
                        dpg.add_text("", tag=f"r_{key}")

            dpg.add_separator()
            dpg.add_text("", tag="tip", wrap=WIDTH - 20)
        dpg.bind_item_theme("main", main_theme)

        if IS_WIN:
            with dpg.handler_registry():
                dpg.add_mouse_click_handler(button=dpg.mvMouseButton_Left, callback=self.maybe_drag)

    def maybe_drag(self):
        x, y = dpg.get_mouse_pos(local=False)
        on_button = any(dpg.is_item_hovered(b) for b in ("btn_alpha", "btn_full", "btn_close"))
        if y < 26 and not on_button:   # title row, not on a button
            start_native_drag()

    def cycle_alpha(self):
        self.alpha_i = (self.alpha_i + 1) % len(ALPHAS)
        set_alpha(ALPHAS[self.alpha_i])

    def open_full(self, sender=None, app_data=None, user_data=None):
        """Opens the full analysis window, on a metric-tree node if one is given.
        The full window only reads the log; archiving stays with the overlay."""
        here = os.path.dirname(os.path.abspath(__file__))
        exe = sys.executable.replace("python.exe", "pythonw.exe") if IS_WIN else sys.executable
        if not os.path.exists(exe):
            exe = sys.executable
        args = [exe, os.path.join(here, "civstats.py"), "--no-archive"]
        args += ["--node", user_data] if user_data else ["--view", "Советник"]
        if self.data.path != LOG_PATH:
            args.append(self.data.path)
        subprocess.Popen(args)

    def refresh(self, force=False):
        if not self.data.poll() and not force:
            return
        graph, rows, (tip, tip_color) = summarize(self.data)

        dpg.delete_item("y", children_only=True)
        for mine, name, color, xs, ys in graph:
            tag = dpg.add_line_series(xs, ys, label=("Вы" if mine else name), parent="y")
            dpg.bind_item_theme(tag, self.line_theme(color, mine))
        dpg.fit_axis_data("x")
        if graph:
            lead = max(graph, key=lambda g: g[4][-1] if g[4] else 0)
            dpg.set_value("leader", "Толстая линия — вы · лидер: " + ("вы" if lead[0] else lead[1]))
            dpg.configure_item("leader", color=lead[2])

        lt = self.data.last_turn()
        dpg.set_value("title", f"Civ 5 · ход {lt}" if lt is not None else "Civ 5 · статистика")
        for key, _ in ROWS:
            val, rank, color = rows.get(key, ("—", "", None))
            dpg.set_value(f"v_{key}", val)
            dpg.set_value(f"r_{key}", rank)
            dpg.configure_item(f"v_{key}", color=color or (230, 230, 230))
            dpg.configure_item(f"r_{key}", color=color or DIM)
        dpg.set_value("tip", tip)
        dpg.configure_item("tip", color=tip_color)

    def run(self):
        self.refresh(force=True)
        while dpg.is_dearpygui_running():
            now = time.monotonic()
            if now - self.last_poll > REFRESH_S:
                self.last_poll = now
                self.refresh()
            dpg.render_dearpygui_frame()
        dpg.destroy_context()


def main():
    Overlay(sys.argv[1] if len(sys.argv) > 1 else LOG_PATH).run()


if __name__ == "__main__":
    main()
