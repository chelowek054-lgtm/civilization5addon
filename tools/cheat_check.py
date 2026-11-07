"""Looks for signs of cheating by opponents in a recorded game.

Compares each player's stats turn to turn and flags jumps the game rules
hardly allow: several techs or policies at once, gold or units out of
nowhere, an army that triples in a turn. Each flag has normal explanations
too (a great scientist, a finished policy branch, a captured city, a sold
building, a trade), so look at players with many flags, not at one flag.

    python tools/cheat_check.py                 newest game in saves/
    python tools/cheat_check.py saves/<file>.log
    python tools/cheat_check.py --all
"""
import argparse
import glob
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viewer"))
from civstats import ARCHIVE_DIR, parse_line  # noqa: E402


def load(path):
    """{pid: {turn: stats}}, {pid: name}, active player's pid."""
    series, names, me = {}, {}, None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            rec = parse_line(line)
            if not rec:
                continue
            turn, pid, is_me, _, name, stats = rec
            series.setdefault(pid, {})[turn] = stats
            names[pid] = name
            if is_me:
                me = pid
    return series, names, me


def g(s, k):
    v = s.get(k, 0)
    return v if isinstance(v, (int, float)) else 0


def checks(prev, cur):
    """(weight, text) for every suspicious change between two consecutive turns."""
    out = []
    techs = g(cur, "techs") - g(prev, "techs")
    if techs >= 3:
        out.append((2, f"+{techs:.0f} технологий за ход"))
    elif techs == 2 and g(prev, "science") < 30:
        out.append((1, f"+2 технологии за ход при науке {g(prev, 'science'):.0f}"))
    pol = g(cur, "policies") - g(prev, "policies")
    if pol >= 3:
        out.append((2, f"+{pol:.0f} политик за ход"))
    expected = g(prev, "gold") + g(prev, "goldRate")
    extra = g(cur, "gold") - expected
    if extra > max(400, 8 * abs(g(prev, "goldRate"))) and g(cur, "cities") <= g(prev, "cities"):
        out.append((2, f"золото +{extra:.0f} сверх дохода без захвата городов"))
    units = g(cur, "units") - g(prev, "units")
    if units >= 6:
        out.append((2 if units >= 10 else 1, f"+{units:.0f} юнитов за ход"))
    mil_prev, mil = g(prev, "military"), g(cur, "military")
    if mil_prev > 100 and mil > 3 * mil_prev:
        out.append((2, f"армия выросла в {mil / mil_prev:.1f} раза ({mil_prev:.0f} → {mil:.0f})"))
    pop = g(cur, "population") - g(prev, "population")
    if pop >= 6 and g(cur, "cities") <= g(prev, "cities"):
        out.append((1, f"население +{pop:.0f} без новых городов"))
    if g(prev, "gold") >= 0 and g(cur, "gold") > 5000 and g(prev, "gold") < 1000:
        out.append((3, f"казна {g(prev, 'gold'):.0f} → {g(cur, 'gold'):.0f}"))
    wonders = g(cur, "GetNumWorldWonders") - g(prev, "GetNumWorldWonders")
    if wonders >= 2 and g(cur, "cities") <= g(prev, "cities"):
        out.append((1, f"+{wonders:.0f} чуда за ход"))
    return out


def analyse(path, show_me=False):
    series, names, me = load(path)
    report = []
    for pid, turns in series.items():
        if pid == me and not show_me:
            continue
        flags = []
        ts = sorted(turns)
        for a, b in zip(ts, ts[1:]):
            if b != a + 1:
                continue  # gap or reload: can't compare
            flags += [(b, w, t) for w, t in checks(turns[a], turns[b])]
        score = sum(w for _, w, _ in flags)
        report.append((score, names[pid], len(ts), flags))
    report.sort(key=lambda r: -r[0])
    return report, (names.get(me) if me is not None else "?")


def verdict(score, turns):
    rate = score / max(turns, 1) * 100
    if score >= 8 and rate >= 8:
        return "ПОДОЗРИТЕЛЬНО"
    if score >= 4:
        return "стоит присмотреться"
    return "чисто"


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="Signs of cheating in a recorded Civ 5 game")
    ap.add_argument("log", nargs="?", help="game file from saves/ (default: the newest)")
    ap.add_argument("--all", action="store_true", help="check every game in saves/")
    ap.add_argument("--me", action="store_true", help="also check your own civ")
    args = ap.parse_args()
    files = sorted(glob.glob(os.path.join(ARCHIVE_DIR, "*.log")), key=os.path.getmtime)
    files = files if args.all else [args.log] if args.log else files[-1:]
    for path in files:
        report, me = analyse(path, args.me)
        print(f"\n=== {os.path.basename(path)} (вы: {me})")
        for score, name, turns, flags in report:
            print(f"  {name}: {verdict(score, turns)} — {len(flags)} отметок за {turns} ходов")
            for turn, _, text in flags[:8]:
                print(f"      ход {turn}: {text}")
            if len(flags) > 8:
                print(f"      … ещё {len(flags) - 8}")


if __name__ == "__main__":
    main()
