"""Civ Stats viewer: tails Civ 5 Lua.log and draws live per-turn graphs."""
import datetime
import os
import sys
import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from metrics_tree import TREE, NODES, PARENT, compute_indices
import advisor

def find_log_path():
    """Lua.log location: $CIVSTATS_LOG, else the first existing known place
    (Windows, native Linux port, Proton), else the Windows default."""
    if os.environ.get("CIVSTATS_LOG"):
        return os.environ["CIVSTATS_LOG"]
    home = os.path.expanduser("~")
    user_dirs = [
        os.path.join(home, "Documents", "My Games", "Sid Meier's Civilization 5"),
        os.path.join(home, ".local", "share", "Aspyr", "Sid Meier's Civilization 5"),
        os.path.join(home, ".local", "share", "Steam", "steamapps", "compatdata", "8930", "pfx",
                     "drive_c", "users", "steamuser", "Documents", "My Games",
                     "Sid Meier's Civilization 5"),
    ]
    candidates = [os.path.join(d, "Logs", "Lua.log") for d in user_dirs]
    for c in candidates:
        if os.path.exists(c):
            return c
    for d in user_dirs:  # game installed but no log yet
        if os.path.isdir(d):
            return os.path.join(d, "Logs", "Lua.log")
    return candidates[0]


LOG_PATH = find_log_path()

METRICS = [
    ("score", "Счёт"), ("science", "Наука/ход"), ("goldRate", "Доход золота/ход"),
    ("gold", "Казна"), ("culture", "Культура/ход"), ("tourism", "Туризм"),
    ("faith", "Вера/ход"), ("military", "Военная мощь"), ("population", "Население"),
    ("cities", "Города"), ("techs", "Технологии"), ("policies", "Политики"),
    ("happiness", "Довольство"), ("land", "Территория (клетки)"), ("units", "Юниты"),
]
DASHBOARD = ["score", "science", "goldRate", "military", "culture", "population"]
ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "saves")
LIVE_LABEL = "▶ Текущая игра"
REFRESH_MS = 2000


def parse_line(line):
    i = line.find("CIVSTATS|")
    if i < 0:
        return None
    parts = line[i:].rstrip("\r\n").split("|")
    if len(parts) < 7:
        return None
    _, turn, pid, me, met, name, kv = parts[:7]
    stats = {}
    for pair in kv.split(";"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            try:
                stats[k] = float(v)
            except ValueError:
                stats[k] = v   # id lists like techIds=0,1,5 stay text
    return int(turn), int(pid), me == "1", met == "1", name, stats


def log_stamp(line):
    """'[1303.765] ...' -> '1303765' (seconds since boot, unique per game session)."""
    if line.startswith("[") and "]" in line:
        return line[1:line.index("]")].replace(".", "")
    return "0"


class Archive:
    """Copies every game's stat lines into saves/<date>_<civ>_<game id>.log.

    The logger writes a game id that survives save/load (civ, starting tile,
    map size), so all sessions of one game land in one file. Lines are stored
    without the log timestamp and each distinct line only once, so restarting
    the viewer or reloading an older save never duplicates anything.
    Logs from loggers before v3 have no game id and get one file per session.
    """

    def __init__(self, folder):
        self.folder = folder
        self.session = "0"
        self.start = "0"
        self.f = None
        self.seen = set()
        self.buffer = []

    def close(self):
        if self.f:
            self.f.close()
        self.f = None

    def new_session(self, line=""):
        self.close()
        self.session = log_stamp(line)
        self.start = "0"
        self.buffer = []

    def new_game(self, line):
        self.close()
        self.start = log_stamp(line)
        self.buffer = []

    def _open(self, rec):
        stats = rec[5]
        gid = str(stats.get("gameId") or f"{self.session}-{self.start}")
        gid = "".join(c for c in gid if c.isalnum() or c in "-_x")
        os.makedirs(self.folder, exist_ok=True)
        existing = [f for f in os.listdir(self.folder) if f.endswith(f"_{gid}.log")]
        if existing:  # the same game played in an earlier session: continue its file
            path = os.path.join(self.folder, existing[0])
            with open(path, encoding="utf-8", errors="replace") as f:
                self.seen = {normalize(l) for l in f.read().splitlines()}
        else:
            path = os.path.join(self.folder, f"{datetime.date.today():%Y-%m-%d}_{rec[4]}_{gid}.log")
            self.seen = set()
        self.f = open(path, "a", encoding="utf-8")

    def write(self, line, rec):
        if self.f is None:
            if not rec[2]:  # wait for the active player's line: it carries civ and game id
                self.buffer.append(line)
                return
            self._open(rec)
            lines, self.buffer = self.buffer + [line], []
        else:
            lines = [line]
        new = [n for n in (normalize(l) for l in lines) if n not in self.seen]
        if new:
            self.seen.update(new)
            self.f.write("\n".join(new) + "\n")
            self.f.flush()


def normalize(line):
    """Stat line without the '[1303.765] CivStatsLogger: ' prefix."""
    i = line.find("CIVSTATS|")
    return line[i:].rstrip("\r\n") if i >= 0 else line.rstrip("\r\n")


LOGGER_VERSION = 3   # must match LOGGER_VERSION in CivStatsLogger.lua
INGAME_MARKERS = ("TopPanel:", "NotificationPanel:", "GenericPopup:", "InGame:")


def config_logging_enabled(log_path):
    """True/False from config.ini next to the Logs folder, None if unknown."""
    cfg = os.path.join(os.path.dirname(os.path.dirname(log_path)), "config.ini")
    try:
        with open(cfg, encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                if line.strip().startswith("LoggingEnabled"):
                    return line.split("=", 1)[1].strip() == "1"
    except OSError:
        pass
    return None


class Data:
    def __init__(self, path, archive=True):
        self.path = path
        self.pos = 0
        is_live = os.path.normcase(path) == os.path.normcase(LOG_PATH)
        self.archive = Archive(ARCHIVE_DIR) if archive and is_live else None
        self.reset()

    def reset(self):
        self.series = {}   # pid -> {turn: stats}
        self.names = {}
        self.met = set()
        self.me = None
        # what the log told us about the logger itself (for diagnose())
        self.version = None
        self.errors = []
        self.in_game = False

    def diagnose(self):
        """(level, text) when something is wrong with the logger setup, else None.
        level: 'red' broken, 'yellow' works partly or waiting."""
        if self.archive is None and os.path.normcase(self.path) != os.path.normcase(LOG_PATH):
            return None  # a saved game: nothing to set up
        if not os.path.exists(self.path):
            if config_logging_enabled(self.path) is False:
                return "red", "Логирование выключено (LoggingEnabled = 0). Запустите install и перезапустите игру."
            return "yellow", "Lua.log не найден — запустите игру (или задайте CIVSTATS_LOG)."
        if self.errors:
            return "red", "Ошибка логгера: " + self.errors[-1][:150]
        if not self.series:
            if self.in_game:
                return "red", ("Партия идёт, но логгер молчит: запустите install и полностью "
                               "перезапустите игру (Steam мог восстановить файлы).")
            return "yellow", "Ждём загрузки партии…"
        if (self.version or 0) < LOGGER_VERSION:
            return "yellow", (f"Устаревший логгер (v{self.version or 1}, нужен v{LOGGER_VERSION}): "
                              "запустите install и перезапустите игру — часть советов недоступна.")
        return None

    def poll(self):
        """Read new log lines. Returns True if anything changed."""
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return False
        if size < self.pos:  # game restarted, log was recreated
            self.pos = 0
            self.reset()
            if self.archive:
                self.archive.new_session()
        if size == self.pos:
            return False
        with open(self.path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(self.pos)
            chunk = f.read()
            self.pos = f.tell()
        changed = False
        for line in chunk.splitlines():
            if self.is_session_start(line):
                self.in_game, self.errors = False, []
                if self.archive:
                    self.archive.new_session(line)
            if not self.in_game and any(m in line for m in INGAME_MARKERS):
                self.in_game = True
            if "CIVSTATS_ERROR|" in line or ("CivStatsLogger" in line and
                                             ("Runtime Error" in line or "Syntax Error" in line)):
                self.errors.append(line[line.find("CIVSTATS_ERROR|") + 15:] if "CIVSTATS_ERROR|" in line else line)
                changed = True
                continue
            if "CIVSTATS_TURN|" in line and "|v=" in line:
                try:
                    self.version = int(line.rsplit("|v=", 1)[1].strip())
                except ValueError:
                    pass
            if "CIVSTATS_START|" in line:
                # a different game was loaded: start fresh. The logger has just loaded
                # fine, so errors from earlier failed loads no longer apply.
                version = self.version
                self.reset()
                self.version, self.in_game = version, True
                if self.archive:
                    self.archive.new_game(line)
                changed = True
                continue
            rec = parse_line(line)
            if not rec:
                continue
            if self.archive:
                self.archive.write(line, rec)
            turn, pid, me, met, name, stats = rec
            self.series.setdefault(pid, {})[turn] = stats
            self.names[pid] = name
            if me:
                self.me = pid
            if met:
                self.met.add(pid)
            changed = True
        return changed

    def until(self, turn):
        """Read-only copy of the data as it was on `turn` (for the turn slider)."""
        snap = Data.__new__(Data)
        snap.path, snap.pos, snap.archive = self.path, self.pos, None
        snap.series = {p: {t: s for t, s in ts.items() if t <= turn} for p, ts in self.series.items()}
        snap.series = {p: ts for p, ts in snap.series.items() if ts}
        snap.names, snap.met, snap.me = self.names, self.met, self.me
        return snap

    @staticmethod
    def is_session_start(line):
        return "Initializing Lua" in line

    def visible(self, show_all):
        return [p for p in sorted(self.series) if show_all or p in self.met or p == self.me]

    def last_turn(self):
        turns = [t for s in self.series.values() for t in s]
        return max(turns) if turns else None


class App:
    def __init__(self, root, path, view=None, node=None, archive=True, beside=None):
        self.root = root
        # The live log is always polled (so games keep being archived) even
        # while a saved game from history is on screen.
        self.live = Data(LOG_PATH, archive=archive)
        self.data = self.live
        root.title("Civ 5 — статистика")
        self.place_window(beside)

        bar = ttk.Frame(root, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="Игра:").pack(side="left")
        self.game = tk.StringVar(value=LIVE_LABEL)
        self.game_box = ttk.Combobox(bar, textvariable=self.game, state="readonly", width=34,
                                     postcommand=self.refresh_games)
        self.game_box.pack(side="left", padx=(6, 12))
        self.game_box.bind("<<ComboboxSelected>>", lambda e: self.open_game())
        ttk.Label(bar, text="Вид:").pack(side="left")
        self.view = tk.StringVar(value="Советник")
        choices = ["Советник", "Дерево", "Панель"] + [label for _, label in METRICS] + ["Таблица"]
        cb = ttk.Combobox(bar, textvariable=self.view, values=choices, state="readonly", width=24)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.redraw())
        self.show_all = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Показывать незнакомые цивилизации", variable=self.show_all,
                        command=self.redraw).pack(side="left", padx=12)
        self.status = ttk.Label(bar, text="")
        self.status.pack(side="right")

        # Turn slider: look at the game as it was on any past turn
        bar2 = ttk.Frame(root, padding=(6, 0, 6, 4))
        bar2.pack(fill="x")
        self.compact = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Компактно", variable=self.compact,
                        command=self.toggle_compact).pack(side="left")
        ttk.Label(bar2, text="Ход:").pack(side="left", padx=(16, 4))
        self.turn = None          # None = follow the latest turn
        self.turn_job = None
        self.turn_scale = tk.Scale(bar2, from_=0, to=0, orient="horizontal", showvalue=True,
                                   resolution=1, command=self.on_turn)
        self.turn_scale.pack(side="left", fill="x", expand=True)
        ttk.Button(bar2, text="◀", width=3, command=lambda: self.step_turn(-1)).pack(side="left")
        ttk.Button(bar2, text="▶", width=3, command=lambda: self.step_turn(1)).pack(side="left")
        ttk.Button(bar2, text="Последний", command=self.latest_turn).pack(side="left", padx=(4, 0))

        self.body = ttk.Frame(root)
        self.body.pack(fill="both", expand=True)
        # Match the screen DPI so charts are as readable as the rest of the window
        self.fig = Figure(figsize=(12, 7), dpi=max(100, root.winfo_fpixels("1i")))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.body)
        self.table = ttk.Treeview(self.body, show="headings")
        self.build_tree()
        self.advice_frame = ttk.Frame(self.body)
        self.advice = tk.Text(self.advice_frame, width=58, wrap="word", font=("Segoe UI", 10),
                              relief="flat", padx=8, pady=6)
        adv_sb = ttk.Scrollbar(self.advice_frame, orient="vertical", command=self.advice.yview)
        self.advice.configure(yscrollcommand=adv_sb.set)
        adv_sb.pack(side="right", fill="y")
        self.advice.pack(side="left", fill="both", expand=True)
        for tag, color in (("red", "#c62828"), ("yellow", "#b26a00"), ("green", "#2e7d32")):
            self.advice.tag_configure(tag, foreground=color)
        self.advice.tag_configure("h", font=("Segoe UI", 11, "bold"))

        self.live.poll()
        self.refresh_games()
        if path != LOG_PATH:  # a saved game passed on the command line
            self.game.set(os.path.splitext(os.path.basename(path))[0])
            self.saved_paths[self.game.get()] = path
            self.open_game()
        if node in NODES:
            view = "Дерево"
            self.selected = node
            parent = PARENT.get(node)
            while parent:  # unfold the branch down to the node
                self.tree.item(parent, open=True)
                parent = PARENT.get(parent)
            self.tree.selection_set(node)
            self.tree.see(node)
        if view:
            self.view.set(view)
        self.redraw()
        root.after(REFRESH_MS, self.tick)

    def place_window(self, beside):
        """Default size, or — when opened from the overlay — right next to it,
        filling the rest of the screen so the overlay never covers the window."""
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if not beside:
            w, h = min(1280, sw - 40), min(820, sh - 80)
            self.root.geometry(f"{w}x{h}")
            return
        left, top, right, bottom = beside
        gap = 8
        if right + gap + 900 <= sw:          # room on the right of the overlay
            x, w = right + gap, sw - right - 2 * gap
        else:                                # overlay is on the right side: go left
            x, w = gap, max(900, left - 2 * gap)
        y = max(0, top - 40)                 # leave space for the title bar
        h = sh - y - 60                      # keep clear of the taskbar
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def refresh_games(self):
        """Fills the game list: live game first, then saves/ newest first."""
        self.saved_paths = {}
        try:
            files = [f for f in os.listdir(ARCHIVE_DIR) if f.endswith(".log")]
        except OSError:
            files = []
        files.sort(key=lambda f: os.path.getmtime(os.path.join(ARCHIVE_DIR, f)), reverse=True)
        for f in files:
            self.saved_paths[os.path.splitext(f)[0]] = os.path.join(ARCHIVE_DIR, f)
        self.game_box["values"] = [LIVE_LABEL] + list(self.saved_paths)

    def open_game(self):
        self.turn = None
        path = self.saved_paths.get(self.game.get())
        if path is None:
            self.data = self.live
        else:
            self.data = Data(path)
            self.data.poll()
        self.redraw()

    def on_turn(self, value):
        """Slider moved: remember the turn and redraw shortly after (debounced)."""
        t = int(float(value))
        lt = self.data.last_turn()
        self.turn = None if lt is None or t >= lt else t
        if self.turn_job:
            self.root.after_cancel(self.turn_job)
        self.turn_job = self.root.after(120, self.redraw)

    def step_turn(self, delta):
        self.turn_scale.set(int(self.turn_scale.get()) + delta)

    def latest_turn(self):
        self.turn = None
        self.redraw()

    def toggle_compact(self):
        if self.compact.get():
            self.full_geometry = self.root.geometry()
            sw = self.root.winfo_screenwidth()
            self.root.geometry(f"380x640+{sw - 400}+80")
        else:
            self.root.geometry(getattr(self, "full_geometry", "1280x820"))
        self.redraw()

    def tick(self):
        if self.live.poll() and self.data is self.live:
            self.redraw()
        self.root.after(REFRESH_MS, self.tick)

    def label(self, pid):
        n = self.data.names.get(pid, str(pid))
        return n + " (вы)" if pid == self.data.me else n

    def redraw(self):
        self.turn_job = None
        d = self.data
        lt = d.last_turn()
        turns = [t for s in d.series.values() for t in s]
        self.turn_scale.configure(from_=min(turns) if turns else 0, to=lt or 0)
        if self.turn is not None and lt is not None and self.turn >= lt:
            self.turn = None
        shown_turn = lt if self.turn is None else self.turn
        if shown_turn is not None and int(self.turn_scale.get()) != shown_turn:
            self.turn_scale.set(shown_turn)   # fires on_turn, which keeps the same state
        self.shown = d if self.turn is None else d.until(self.turn)
        if self.turn is not None:
            self.status.config(text=f"Просмотр хода {self.turn} из {lt} · «Последний» — вернуться")
        elif d is not self.live:
            self.status.config(text=f"Запись игры · до хода {lt if lt is not None else 0} · цивилизаций: {len(d.series)}")
        elif d.diagnose():
            self.status.config(text=d.diagnose()[1])
        else:
            sc = advisor.game_scale(d)
            game = f" · {sc['label']}, {sc['size']}" if sc["label"] else ""
            self.status.config(text=f"Ход {lt} · цивилизаций: {len(d.series)}{game}")

        d = self.shown
        for w in (self.table, self.tree_frame, self.advice_frame, self.canvas.get_tk_widget()):
            w.pack_forget()
        if self.view.get() == "Советник":
            self.advice_frame.pack(side="left", fill="both", expand=self.compact.get())
            if not self.compact.get():
                self.canvas.get_tk_widget().pack(side="left", fill="both", expand=True)
            self.draw_advisor()
            return
        if self.view.get() == "Таблица":
            self.table.pack(fill="both", expand=True)
            self.draw_table()
            return
        if self.view.get() == "Дерево":
            if not self.compact.get():
                self.tree_frame.pack(side="left", fill="y")
            self.canvas.get_tk_widget().pack(side="left", fill="both", expand=True)
            self.draw_tree_view()
            return
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.fig.clear()
        if self.view.get() == "Панель":
            keys = DASHBOARD[:3] if self.compact.get() else DASHBOARD
        else:
            keys = [k for k, lbl in METRICS if lbl == self.view.get()]
        cols = 1 if self.compact.get() else (3 if len(keys) > 1 else 1)
        rows = (len(keys) + cols - 1) // cols
        labels = dict(METRICS)
        pids = d.visible(self.show_all.get())
        for n, key in enumerate(keys, 1):
            ax = self.fig.add_subplot(rows, cols, n)
            ax.set_title(labels[key], fontsize=10)
            ax.grid(alpha=0.3)
            for pid in pids:
                turns = sorted(d.series[pid])
                ys = [d.series[pid][t].get(key, 0) for t in turns]
                ax.plot(turns, ys, label=self.label(pid),
                        linewidth=3 if pid == d.me else 1.4)
            ax.tick_params(labelsize=8)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            if n == 1 and pids:
                ax.legend(fontsize=7, loc="upper left")
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def build_tree(self):
        self.tree_frame = ttk.Frame(self.body)
        self.tree = ttk.Treeview(self.tree_frame, columns=("idx", "rank", "val"),
                                 show="tree headings", height=30)
        self.tree.heading("#0", text="Показатель")
        self.tree.heading("idx", text="Индекс")
        self.tree.heading("rank", text="Место")
        self.tree.heading("val", text="Значение")
        self.tree.column("#0", width=230)
        for col, w in (("idx", 55), ("rank", 50), ("val", 70)):
            self.tree.column(col, width=w, anchor="e")
        sb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="y")
        sb.pack(side="left", fill="y")

        def add(node, parent):
            self.tree.insert(parent, "end", iid=node.key, text=node.label, open=(node is TREE))
            for c in node.children:
                add(c, node.key)
        add(TREE, "")
        self.selected = TREE.key
        self.tree.selection_set(TREE.key)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def on_select(self, _event):
        sel = self.tree.selection()
        if sel and sel[0] != self.selected:
            self.selected = sel[0]
            self.draw_tree_view()

    def draw_tree_view(self):
        d = self.shown
        pids = d.visible(self.show_all.get())
        idx = compute_indices(d.series, pids) if pids else {}
        lt = d.last_turn()

        # Tree columns: your index, rank among visible civs, raw value (leaves)
        me = d.me if d.me in idx else None
        for node in TREE.walk():
            vals = ("", "", "")
            if me is not None and lt in idx[me] and node.key in idx[me][lt]:
                mine = idx[me][lt][node.key]
                others = [idx[p][lt].get(node.key) for p in pids if lt in idx[p]]
                rank = 1 + sum(1 for v in others if v is not None and v > mine + 1e-9)
                raw = d.series[me][lt].get(node.key) if node.is_leaf else None
                vals = (f"{mine:.0f}", f"{rank}/{len(others)}",
                        "" if raw is None else f"{raw:g}")
            self.tree.item(node.key, values=vals)

        node = NODES[self.selected]
        self.fig.clear()
        compact = self.compact.get()
        show_children = not node.is_leaf and not compact and me is not None
        ax = self.fig.add_subplot(2 if show_children else 1, 1, 1)
        for pid in pids:
            turns = sorted(idx[pid])
            if node.is_leaf:
                ys = [d.series[pid][t].get(node.key, 0) for t in turns]
            else:
                ys = [idx[pid][t].get(node.key, 0) for t in turns]
            ax.plot(turns, ys, label=self.label(pid), linewidth=3 if pid == d.me else 1.4)
        ax.set_title(node.label + ("" if node.is_leaf else " — индекс 0…100 (100 = лучший)"),
                     fontsize=10)
        self.style_axis(ax)
        if pids:
            ax.legend(fontsize=7, loc="upper left")

        if show_children:
            ax2 = self.fig.add_subplot(2, 1, 2)
            turns = sorted(idx[me])
            for c in node.children:
                ax2.plot(turns, [idx[me][t].get(c.key, 0) for t in turns], label=c.label)
            ax2.set_title(f"Из чего складывается: {self.label(me)}", fontsize=10)
            ax2.set_ylim(-5, 105)
            self.style_axis(ax2)
            ax2.legend(fontsize=7, loc="upper left", ncol=2)
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def draw_advisor(self):
        d = self.shown
        pids = d.visible(self.show_all.get())
        idx = compute_indices(d.series, pids) if pids else {}
        profile, warns = advisor.analyse(d, idx, pids)

        txt = self.advice
        txt.configure(state="normal")
        txt.delete("1.0", "end")
        txt.insert("end", "Что сейчас не так\n", "h")
        icons = {"red": "●", "yellow": "●", "green": "●"}
        for level, msg in warns:
            txt.insert("end", icons[level] + " ", level)
            txt.insert("end", msg + "\n")

        plan = advisor.development_plan(d, idx, pids)
        if plan:
            txt.insert("end", "\nКак развиваться\n", "h")
            for n, line in enumerate(plan, 1):
                txt.insert("end", f"{n}. {line}\n")

        txt.insert("end", "\nЧто изучать\n", "h")
        research = advisor.research_plan(d)
        if research is None:
            txt.insert("end", "Появится в новой партии: логгер теперь пишет изученные технологии.\n")
        for goal, reason, now, steps in research or []:
            txt.insert("end", "● ", "green")
            txt.insert("end", f"{goal} — {reason}, ещё {steps} техн. Сейчас: {', '.join(now) or '—'}.\n")

        txt.insert("end", "\nЧто выбирать в культуре\n", "h")
        policies = advisor.policy_plan(d)
        if policies is None:
            txt.insert("end", "Появится в новой партии: логгер теперь пишет принятые политики.\n")
        for line in policies or []:
            txt.insert("end", "● ", "green")
            txt.insert("end", line + "\n")

        rv = advisor.rivals(d, idx, pids)
        if rv:
            txt.insert("end", "\nСоседи и соперники\n", "h")
            if all(r["dist"] is None for r in rv):
                txt.insert("end", "Расстояний пока нет: они появятся в новой записи после "
                                  "переустановки логгера и когда вы увидите их города.\n")
            for r in rv:
                level, role = advisor.rival_role(r)
                dist = "?" if r["dist"] is None else f"{r['dist']} кл."
                growth = "" if r["mil_growth"] is None else f", армия {r['mil_growth']:+.0%} за {r['window']} ходов"
                best = advisor.GROUP_LABELS.get(r["best"], "—")
                txt.insert("end", "● ", level)
                txt.insert("end", f"{r['name']} — {dist}, {role}. Сила {r['overall']:.0f}, "
                                  f"армия ×{r['mil_ratio']:.1f} от вашей{growth}; "
                                  f"сильнее всего: {best}.\n")
        if profile:
            txt.insert("end", "\nВаша цивилизация\n", "h")
            txt.insert("end", "\n".join(profile) + "\n")
        txt.configure(state="disabled")
        if self.compact.get():
            return

        # Right side: overall index for everyone + your era timeline with power spikes
        self.fig.clear()
        grid = self.fig.add_gridspec(2, 1, height_ratios=[4, 1])   # the graph matters most
        ax = self.fig.add_subplot(grid[0])
        for pid in pids:
            turns = sorted(idx[pid])
            ax.plot(turns, [idx[pid][t].get("overall", 0) for t in turns], label=self.label(pid),
                    linewidth=3 if pid == d.me else 1.2)
        ax.set_title("Общая сила — индекс 0…100", fontsize=10)
        ax.set_ylim(-5, 105)
        self.style_axis(ax)
        if pids:
            ax.legend(fontsize=7, loc="upper left")

        # Era strip: one cell per era, era name and your unique units written inside
        ax2 = self.fig.add_subplot(grid[1])
        civ = d.names.get(d.me, "")
        spikes = advisor.spike_eras(civ)
        cur = advisor.current_era(d.series[d.me][max(d.series[d.me])]) if d.me in d.series else -1
        eras = range(8)
        ax2.bar(eras, [1] * 8, width=0.94, color=["#e57373" if e in spikes else "#cfd8dc" for e in eras],
                edgecolor=["#000" if e == cur else "none" for e in eras], linewidth=2)
        units = {}
        for u in advisor.uniques(civ):
            if u.get("era") is not None:
                units.setdefault(u["era"], []).append(u["name"])
        for e in eras:
            # one word per line; split very long words so they fit their cell
            words = advisor.ERA_NAMES.get(e, str(e)).split()
            name = "\n".join(w if len(w) <= 11 else w[:len(w) // 2] + "-\n" + w[len(w) // 2:]
                             for w in words)
            ax2.text(e, 0.72, name, ha="center", va="center", fontsize=6)
            if e in units:
                ax2.text(e, 0.25, "\n".join(units[e]), ha="center", va="center", fontsize=6,
                         fontweight="bold")
        ax2.set_xlim(-0.5, 7.5)
        ax2.set_ylim(0, 1)
        ax2.set_xticks([])
        ax2.set_yticks([])
        ax2.set_title("Эпохи: красное — окна силы ваших уникальных юнитов, рамка — вы сейчас", fontsize=9)
        self.fig.tight_layout()
        self.canvas.draw_idle()

    @staticmethod
    def style_axis(ax):
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=8)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    def draw_table(self):
        d = self.shown
        cols = ["civ"] + [k for k, _ in METRICS]
        self.table.configure(columns=cols)
        self.table.heading("civ", text="Цивилизация")
        self.table.column("civ", width=150)
        for k, lbl in METRICS:
            self.table.heading(k, text=lbl)
            self.table.column(k, width=80, anchor="e")
        self.table.delete(*self.table.get_children())
        for pid in d.visible(self.show_all.get()):
            last = d.series[pid][max(d.series[pid])]
            self.table.insert("", "end", values=[self.label(pid)] +
                              [f"{last.get(k, 0):g}" for k, _ in METRICS])


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Civ 5 stats: full analysis window")
    ap.add_argument("log", nargs="?", default=LOG_PATH, help="Lua.log or a saved game from saves/")
    ap.add_argument("--view", help="start view, e.g. Советник, Дерево, Таблица")
    ap.add_argument("--node", help="metric-tree node to open (implies the tree view)")
    ap.add_argument("--no-archive", action="store_true",
                    help="don't archive games (the overlay already does it)")
    ap.add_argument("--beside", help="left,top,right,bottom of the overlay: open next to it")
    args = ap.parse_args()
    if sys.platform == "win32":
        # Sharp text on scaled displays, and screen coordinates that match the overlay's
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    beside = tuple(int(v) for v in args.beside.split(",")) if args.beside else None
    root = tk.Tk()
    App(root, args.log, view=args.view, node=args.node, archive=not args.no_archive, beside=beside)
    root.mainloop()


if __name__ == "__main__":
    main()
