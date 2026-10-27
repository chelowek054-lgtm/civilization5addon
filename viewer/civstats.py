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

from metrics_tree import TREE, NODES, compute_indices
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
                pass
    return int(turn), int(pid), me == "1", met == "1", name, stats


def log_stamp(line):
    """'[1303.765] ...' -> '1303765' (seconds since boot, unique per game session)."""
    if line.startswith("[") and "]" in line:
        return line[1:line.index("]")].replace(".", "")
    return "0"


class Archive:
    """Copies every game's stat lines into games/<date>_<civ>_<id>.log.

    The file name depends only on log timestamps, so restarting the viewer
    rewrites the same file instead of creating duplicates.
    """

    def __init__(self, folder):
        self.folder = folder
        self.session = "0"
        self.game = None
        self.f = None
        self.buffer = []

    def close(self):
        if self.f:
            self.f.close()
        self.f = None

    def new_session(self, line=""):
        self.close()
        self.session = log_stamp(line)
        self.game = None

    def new_game(self, line):
        self.close()
        self.game = f"{self.session}-{log_stamp(line)}"
        self.buffer = [line]

    def write(self, line, rec):
        if self.f is None:
            if rec[2]:  # first line from the active player: now we know our civ
                if self.game is None:
                    self.game = f"{self.session}-0"
                os.makedirs(self.folder, exist_ok=True)
                name = f"{datetime.date.today():%Y-%m-%d}_{rec[4]}_{self.game}.log"
                self.f = open(os.path.join(self.folder, name), "w", encoding="utf-8")
                self.f.write("\n".join(self.buffer + [line]) + "\n")
                self.f.flush()
                self.buffer = []
            else:
                self.buffer.append(line)
            return
        self.f.write(line + "\n")
        self.f.flush()


class Data:
    def __init__(self, path):
        self.path = path
        self.pos = 0
        self.archive = Archive(ARCHIVE_DIR) if os.path.normcase(path) == os.path.normcase(LOG_PATH) else None
        self.reset()

    def reset(self):
        self.series = {}   # pid -> {turn: stats}
        self.names = {}
        self.met = set()
        self.me = None

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
            if self.archive and self.is_session_start(line):
                self.archive.new_session(line)
            if "CIVSTATS_START|" in line:
                # a different game was loaded: start fresh
                self.reset()
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

    @staticmethod
    def is_session_start(line):
        return "Initializing Lua" in line

    def visible(self, show_all):
        return [p for p in sorted(self.series) if show_all or p in self.met or p == self.me]

    def last_turn(self):
        turns = [t for s in self.series.values() for t in s]
        return max(turns) if turns else None


class App:
    def __init__(self, root, path):
        self.root = root
        # The live log is always polled (so games keep being archived) even
        # while a saved game from history is on screen.
        self.live = Data(LOG_PATH)
        self.data = self.live
        root.title("Civ 5 — статистика")
        root.geometry("1280x820")

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

        # Overlay controls: keep window above the game, transparency, compact layout
        bar2 = ttk.Frame(root, padding=(6, 0, 6, 4))
        bar2.pack(fill="x")
        self.topmost = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar2, text="Поверх всех окон", variable=self.topmost,
                        command=self.apply_topmost).pack(side="left")
        ttk.Label(bar2, text="Прозрачность:").pack(side="left", padx=(12, 4))
        self.alpha = tk.DoubleVar(value=0.9)
        ttk.Scale(bar2, from_=0.3, to=1.0, variable=self.alpha, length=120,
                  command=lambda v: root.attributes("-alpha", float(v))).pack(side="left")
        self.compact = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Компактно", variable=self.compact,
                        command=self.toggle_compact).pack(side="left", padx=12)
        root.attributes("-alpha", self.alpha.get())
        self.apply_topmost()

        self.body = ttk.Frame(root)
        self.body.pack(fill="both", expand=True)
        self.fig = Figure(figsize=(12, 7), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.body)
        self.table = ttk.Treeview(self.body, show="headings")
        self.build_tree()
        self.advice = tk.Text(self.body, width=62, wrap="word", font=("Segoe UI", 10),
                              relief="flat", padx=8, pady=6)
        for tag, color in (("red", "#c62828"), ("yellow", "#b26a00"), ("green", "#2e7d32")):
            self.advice.tag_configure(tag, foreground=color)
        self.advice.tag_configure("h", font=("Segoe UI", 11, "bold"))

        self.live.poll()
        self.refresh_games()
        if path != LOG_PATH:  # a saved game passed on the command line
            self.game.set(os.path.splitext(os.path.basename(path))[0])
            self.saved_paths[self.game.get()] = path
            self.open_game()
        self.redraw()
        root.after(REFRESH_MS, self.tick)

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
        path = self.saved_paths.get(self.game.get())
        if path is None:
            self.data = self.live
        else:
            self.data = Data(path)
            self.data.poll()
        self.redraw()

    def apply_topmost(self):
        self.root.attributes("-topmost", self.topmost.get())

    def toggle_compact(self):
        if self.compact.get():
            self.full_geometry = self.root.geometry()
            sw = self.root.winfo_screenwidth()
            self.root.geometry(f"380x640+{sw - 400}+80")
        else:
            self.root.geometry(getattr(self, "full_geometry", "1280x820"))
        self.redraw()

    def tick(self):
        # some games steal the topmost flag when they get focus: reassert it
        if self.topmost.get():
            self.root.attributes("-topmost", True)
        if self.live.poll() and self.data is self.live:
            self.redraw()
        self.root.after(REFRESH_MS, self.tick)

    def label(self, pid):
        n = self.data.names.get(pid, str(pid))
        return n + " (вы)" if pid == self.data.me else n

    def redraw(self):
        d = self.data
        lt = d.last_turn()
        if d is not self.live:
            self.status.config(text=f"Запись игры · до хода {lt if lt is not None else 0} · цивилизаций: {len(d.series)}")
        elif not os.path.exists(d.path):
            self.status.config(text="Lua.log не найден — запустите игру с LoggingEnabled = 1")
        elif lt is None:
            self.status.config(text="Ждём данных из игры…")
        else:
            self.status.config(text=f"Ход {lt} · цивилизаций: {len(d.series)}")

        for w in (self.table, self.tree_frame, self.advice, self.canvas.get_tk_widget()):
            w.pack_forget()
        if self.view.get() == "Советник":
            self.advice.pack(side="left", fill="both", expand=self.compact.get())
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
        d = self.data
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
        d = self.data
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
        if profile:
            txt.insert("end", "\nВаша цивилизация\n", "h")
            txt.insert("end", "\n".join(profile) + "\n")
        txt.configure(state="disabled")
        if self.compact.get():
            return

        # Right side: overall index for everyone + your era timeline with power spikes
        self.fig.clear()
        ax = self.fig.add_subplot(2, 1, 1)
        for pid in pids:
            turns = sorted(idx[pid])
            ax.plot(turns, [idx[pid][t].get("overall", 0) for t in turns], label=self.label(pid),
                    linewidth=3 if pid == d.me else 1.2)
        ax.set_title("Общая сила — индекс 0…100", fontsize=10)
        ax.set_ylim(-5, 105)
        self.style_axis(ax)
        if pids:
            ax.legend(fontsize=7, loc="upper left")

        ax2 = self.fig.add_subplot(2, 1, 2)
        civ = d.names.get(d.me, "")
        spikes = advisor.spike_eras(civ)
        cur = advisor.current_era(d.series[d.me][max(d.series[d.me])]) if d.me in d.series else -1
        eras = range(8)
        ax2.bar(eras, [1] * 8, color=["#e57373" if e in spikes else "#cfd8dc" for e in eras],
                edgecolor=["#000" if e == cur else "none" for e in eras], linewidth=2)
        for u in advisor.uniques(civ):
            if u.get("era") is not None:
                ax2.text(u["era"], 0.5, u["name"], rotation=90, ha="center", va="center", fontsize=8)
        ax2.set_xticks(list(eras))
        ax2.set_xticklabels([advisor.ERA_NAMES.get(e, e) for e in eras], rotation=20, fontsize=7)
        ax2.set_yticks([])
        ax2.set_title("Эпохи: красное — окна силы уникальных юнитов, рамка — вы сейчас", fontsize=10)
        self.fig.tight_layout()
        self.canvas.draw_idle()

    @staticmethod
    def style_axis(ax):
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=8)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    def draw_table(self):
        d = self.data
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
    path = sys.argv[1] if len(sys.argv) > 1 else LOG_PATH
    root = tk.Tk()
    App(root, path)
    root.mainloop()


if __name__ == "__main__":
    main()
