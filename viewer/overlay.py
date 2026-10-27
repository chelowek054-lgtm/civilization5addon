"""Compact in-game overlay (Dear PyGui): one graph, the must-watch numbers and
a one-line tip. Sits on the left edge under the science panel, borderless,
always on top. The full analysis window (civstats.py) opens with the "+" button.

    python viewer/overlay.py [saved_game.log]
"""
import json
import os
import subprocess
import sys
import time

import dearpygui.dearpygui as dpg

import advisor
import gamewindow
from civstats import LOG_PATH, Data
from metrics_tree import compute_indices

TITLE = "Civ5 Stats Overlay"
WIDTH, HEIGHT = 340, 480
LINE_HEIGHT = 104        # one-line mode: title, tip and next pick only
POS = (6, 132)           # left edge, just under the science / tech panel at 1080p
REFRESH_S = 2.0
ALPHAS = (0.88, 0.7, 1.0)
HOTKEY = "Ctrl+Shift+S"  # cycles: full panel → one line → hidden → full panel
SETTINGS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "overlay_settings.json")
MODES = ("full", "line", "hidden")

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
    from ctypes import wintypes
    find = ctypes.windll.user32.FindWindowW
    find.restype = wintypes.HWND   # pointer-sized, not a truncated 32-bit int
    return find(None, TITLE)


def window_rect():
    """Overlay rectangle in screen pixels (left, top, right, bottom), or None."""
    if not IS_WIN:
        x, y = dpg.get_viewport_pos()
        return (int(x), int(y), int(x + dpg.get_viewport_width()), int(y + dpg.get_viewport_height()))
    import ctypes
    from ctypes import wintypes
    r = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(_hwnd(), ctypes.byref(r)):
        return None
    return (r.left, r.top, r.right, r.bottom)


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


def show_window(visible):
    if IS_WIN:
        import ctypes
        ctypes.windll.user32.ShowWindow(_hwnd(), 4 if visible else 0)   # SW_SHOWNOACTIVATE / SW_HIDE


def keep_on_top():
    """Put the panel back above the game. Civ 5 in (borderless) windowed mode
    raises itself over 'always on top' windows when you click into it, so the
    flag alone is not enough; this runs a few times a second and never steals
    focus. Exclusive fullscreen still covers everything — use windowed mode."""
    if not IS_WIN:
        return
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    # Without argtypes ctypes passes -1 as a 32-bit int and 64-bit Windows rejects
    # it as an invalid window handle (error 1400): HWND_TOPMOST must be pointer-sized.
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetWindowPos.restype = wintypes.BOOL
    h = _hwnd()
    if h and user32.IsWindowVisible(h):
        # HWND_TOPMOST, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER
        user32.SetWindowPos(h, wintypes.HWND(-1), 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010 | 0x0200)


def window_visible():
    if not IS_WIN:
        return True
    import ctypes
    h = _hwnd()
    return bool(h and ctypes.windll.user32.IsWindowVisible(h))


def hotkey_down():
    """Ctrl+Shift+S held right now, even while the game has focus (Windows).
    Elsewhere only works while the overlay itself is focused."""
    if IS_WIN:
        import ctypes
        key = ctypes.windll.user32.GetAsyncKeyState
        return all(key(vk) & 0x8000 for vk in (0x11, 0x10, 0x53))   # Ctrl, Shift, S
    return (dpg.is_key_down(dpg.mvKey_LControl) or dpg.is_key_down(dpg.mvKey_RControl)) and \
        (dpg.is_key_down(dpg.mvKey_LShift) or dpg.is_key_down(dpg.mvKey_RShift)) and dpg.is_key_down(dpg.mvKey_S)


def load_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    try:
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(settings, f)
    except OSError:
        pass


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


def next_steps(data):
    """'Изучать: X · Культура: Y' — the immediate research and policy pick."""
    parts = []
    research = advisor.research_plan(data)
    if research:
        goal, _, now, _ = research[0]
        parts.append(f"Изучать: {now[0] if now else goal}" + (f" (→ {goal})" if now and now[0] != goal else ""))
    policies = advisor.policy_plan(data) or []
    pick = next((l for l in policies if l.startswith(("Берите", "Откройте"))), None)
    if pick:
        name = pick.split("«")[1].split("»")[0] if "«" in pick else pick
        parts.append(f"Культура: {name}")
    return " · ".join(parts)


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
        self.settings = load_settings()
        self.alpha_i = self.settings.get("alpha", 0) % len(ALPHAS)
        self.mode = self.settings.get("mode", "full")
        if self.mode not in MODES[:2]:
            self.mode = "full"          # never start invisible
        self.themes = {}
        self.last_poll = 0.0
        self.hotkey_was_down = False

        dpg.create_context()
        self.load_font()
        self.build()
        x, y = self.settings.get("pos", POS)
        if IS_WIN:   # saved on a monitor that is gone now: back to the default place
            import ctypes
            m = ctypes.windll.user32.GetSystemMetrics
            if not (m(76) - 50 <= x <= m(76) + m(78) - 50 and m(77) <= y <= m(77) + m(79) - 50):
                x, y = POS
        dpg.create_viewport(title=TITLE, width=WIDTH, height=HEIGHT, x_pos=int(x), y_pos=int(y),
                            always_on_top=True, decorated=not IS_WIN, resizable=False)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main", True)
        # the window is sized to its content (fit_height), so it never needs to scroll
        dpg.configure_item("main", no_scrollbar=True, no_scroll_with_mouse=True)
        set_alpha(ALPHAS[self.alpha_i])
        self.apply_mode()

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
                        dpg.add_button(label="-", width=20, tag="btn_mode", callback=self.toggle_line)
                        with dpg.tooltip(dpg.last_item()):
                            dpg.add_text(f"Одна строка / вся панель. {HOTKEY}: панель → строка → скрыть")
                        dpg.add_button(label="o", width=20, tag="btn_alpha", callback=self.cycle_alpha)
                        with dpg.tooltip(dpg.last_item()):
                            dpg.add_text("Прозрачность")
                        dpg.add_button(label="+", width=20, tag="btn_full", callback=self.open_full)
                        with dpg.tooltip(dpg.last_item()):
                            dpg.add_text("Подробный анализ")
                        dpg.add_button(label="x", width=20, tag="btn_close",
                                       callback=lambda: dpg.stop_dearpygui())

            with dpg.group(tag="details"):   # hidden in one-line mode
                self.build_details()
            dpg.add_text("", tag="tip", wrap=WIDTH - 20)
            dpg.add_text("", tag="next", wrap=WIDTH - 20, color=(150, 190, 230))
        dpg.bind_item_theme("main", main_theme)

        if IS_WIN:
            with dpg.handler_registry():
                dpg.add_mouse_click_handler(button=dpg.mvMouseButton_Left, callback=self.maybe_drag)

    def build_details(self):
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

    # ---------- modes, hotkey, position ----------

    def fit_height(self):
        """Grow or shrink the window to its content: long tips wrap onto more
        lines, and display scaling changes text height — no scrollbar either way."""
        if self.mode == "hidden" or not dpg.is_item_visible("next"):
            return
        bottom = dpg.get_item_rect_max("next")[1]   # primary window starts at the viewport's top
        want = int(bottom) + 10
        if want > 40 and abs(want - dpg.get_viewport_height()) > 2:
            dpg.set_viewport_height(want)

    def apply_mode(self):
        self.save()   # remember the position while the window is still visible
        if self.mode != "hidden":
            # resize first: resizing a hidden window would show it again
            dpg.configure_item("details", show=self.mode == "full")
            dpg.configure_item("btn_mode", label="-" if self.mode == "full" else "=")
            dpg.set_viewport_height(HEIGHT if self.mode == "full" else LINE_HEIGHT)
        show_window(self.mode != "hidden")

    def toggle_line(self):
        self.mode = "line" if self.mode == "full" else "full"
        self.apply_mode()

    def check_hotkey(self):
        down = hotkey_down()
        if down and not self.hotkey_was_down:
            self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
            self.apply_mode()
        self.hotkey_was_down = down

    def save(self):
        rect = window_rect() if window_visible() else None   # a hidden window has no useful position
        if rect:
            self.settings["pos"] = [rect[0], rect[1]]
        self.settings.update(mode=self.mode, alpha=self.alpha_i)
        save_settings(self.settings)

    def check_game_window(self):
        """Exclusive fullscreen → remember to warn; windowed → make it borderless."""
        hwnd, exe = gamewindow.find_game()
        self.game_fullscreen = bool(hwnd) and gamewindow.exclusive_fullscreen(
            exe, os.path.dirname(os.path.dirname(LOG_PATH)))
        if hwnd and not self.game_fullscreen and self.settings.get("borderless_game", True):
            gamewindow.make_borderless(hwnd)

    def follow_game(self):
        """Windowed game: keep the panel above it. Exclusive fullscreen: never fight
        the game for the screen (that makes it flicker in and out of fullscreen) —
        hide while the game has focus, show again when you Alt+Tab out."""
        if self.mode == "hidden":
            return
        if getattr(self, "game_fullscreen", False):
            hwnd, _ = gamewindow.find_game()
            import ctypes
            game_focused = bool(hwnd) and ctypes.windll.user32.GetForegroundWindow() == hwnd
            if game_focused == window_visible():
                show_window(not game_focused)
            return
        if not window_visible():
            show_window(True)   # back from fullscreen auto-hide
        keep_on_top()

    def game_window_problem(self):
        if getattr(self, "game_fullscreen", False):
            return "yellow", ("Игра в полноэкранном режиме: панель прячется, пока вы в игре, "
                              "и видна только по Alt+Tab. Чтобы видеть её поверх игры: "
                              "Настройки → Видео, снимите «Полноэкранный режим».")
        return None

    def maybe_drag(self):
        x, y = dpg.get_mouse_pos(local=False)
        on_button = any(dpg.is_item_hovered(b) for b in ("btn_mode", "btn_alpha", "btn_full", "btn_close"))
        if y < 26 and not on_button:   # title row, not on a button
            start_native_drag()       # returns when the drag ends
            self.save()               # remember where the panel was put

    def cycle_alpha(self):
        self.alpha_i = (self.alpha_i + 1) % len(ALPHAS)
        set_alpha(ALPHAS[self.alpha_i])
        self.save()

    def open_full(self, sender=None, app_data=None, user_data=None):
        """Opens the full analysis window, on a metric-tree node if one is given.
        The full window only reads the log; archiving stays with the overlay."""
        here = os.path.dirname(os.path.abspath(__file__))
        exe = sys.executable.replace("python.exe", "pythonw.exe") if IS_WIN else sys.executable
        if not os.path.exists(exe):
            exe = sys.executable
        args = [exe, os.path.join(here, "civstats.py"), "--no-archive"]
        args += ["--node", user_data] if user_data else ["--view", "Советник"]
        rect = window_rect()
        if rect:  # open the big window next to the overlay, not under it
            args += ["--beside", ",".join(map(str, rect))]
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
        diag = self.data.diagnose() or self.game_window_problem()   # setup problems beat game advice
        if diag:
            tip, tip_color = diag[1], LEVEL_COLOR[diag[0]]
        dpg.set_value("tip", tip)
        dpg.set_value("next", "" if diag and diag[0] == "red" else next_steps(self.data))
        dpg.configure_item("tip", color=tip_color)

    def run(self):
        self.refresh(force=True)
        last_top = 0.0
        while dpg.is_dearpygui_running():
            now = time.monotonic()
            if now - self.last_poll > REFRESH_S:
                self.last_poll = now
                was_fullscreen = getattr(self, "game_fullscreen", False)
                self.check_game_window()
                self.refresh(force=self.data.series == {} or was_fullscreen != self.game_fullscreen)
            if now - last_top > 0.3:
                last_top = now
                self.follow_game()
            self.check_hotkey()
            dpg.render_dearpygui_frame()
            self.fit_height()
        self.save()
        dpg.destroy_context()


def main():
    Overlay(sys.argv[1] if len(sys.argv) > 1 else LOG_PATH).run()


if __name__ == "__main__":
    main()
