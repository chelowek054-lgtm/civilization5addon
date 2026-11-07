"""Looks for signs of cheating by opponents in a recorded game.

Covers what Civ 5 cheaters actually use, as far as it shows in the stats:
- Cheat Engine tables and trainers edit stored gold, faith and culture or
  multiply research: stock jumps beyond the per-turn income, and techs far
  cheaper in science than everyone else's;
- FireTuner (EnableTuner = 1 in config.ini) and the In-Game Editor mod give
  techs, policies, units, cities, population, buildings, wonders and
  promotions: several of them in one turn, units with more levels than
  their experience allows (logger v4 records the most experienced units).
Map hacks and a faked civ pick in the lobby change no numbers: these
checks cannot see them.

Each flag has honest explanations too (a great scientist, a finished policy
branch, a captured city, a sold building, a trade), so look at players with
many flags, not at one flag.

The analysis window shows the same report in its «Проверка на читы» view.

    python tools/cheat_check.py                 newest game in saves/
    python tools/cheat_check.py saves/<file>.log
    python tools/cheat_check.py --all
"""
import argparse
import glob
import io
import os
import sys

from civstats import ARCHIVE_DIR, parse_line


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
    # Cheat Engine / trainers edit stored faith and culture the same way as gold
    faith_extra = g(cur, "GetFaith") - g(prev, "GetFaith") - g(prev, "faith")
    if faith_extra > max(250, 10 * g(prev, "faith")):
        out.append((2, f"вера +{faith_extra:.0f} сверх прироста"))
    culture_got = g(cur, "GetJONSCultureEverGenerated") - g(prev, "GetJONSCultureEverGenerated")
    if g(prev, "GetJONSCultureEverGenerated") > 0 and culture_got > max(300, 12 * g(prev, "culture")):
        out.append((2, f"культура +{culture_got:.0f} за ход при {g(prev, 'culture'):.0f}/ход"))
    # FireTuner / IGE: cities, happiness and wonders set by hand
    if g(cur, "cities") - g(prev, "cities") >= 2:
        out.append((1, f"+{g(cur, 'cities') - g(prev, 'cities'):.0f} города за ход"))
    happy = g(cur, "happiness") - g(prev, "happiness")
    if abs(happy) >= 25 and g(cur, "cities") == g(prev, "cities"):
        out.append((1, f"довольство {happy:+.0f} за ход без смены городов"))
    wonders = g(cur, "GetNumWorldWonders") - g(prev, "GetNumWorldWonders")
    if wonders >= 2 and g(cur, "cities") <= g(prev, "cities"):
        out.append((1, f"+{wonders:.0f} чуда за ход"))
    return out


def xp_for_level(level):
    """Total experience a unit needs to reach `level` (10, 30, 60, 100, 150, 210…)."""
    return 5 * level * (level - 1)


def units(s):
    """{unit id: (type, level, xp)} from the logger's topUnits field (logger v4+)."""
    out = {}
    for item in str(s.get("topUnits") or "").split(","):
        parts = item.split(":")
        if len(parts) == 4:
            try:
                out[parts[0]] = (parts[1], int(parts[2]), int(parts[3]))
            except ValueError:
                pass
    return out


XP_PER_TURN = 25   # one unit rarely earns more in a turn, even fighting every turn


def unit_checks(prev, cur):
    out = []
    before = units(prev)
    for uid, (utype, level, xp) in units(cur).items():
        if uid in before:
            _, level0, xp0 = before[uid]
            if xp - xp0 > XP_PER_TURN:
                out.append((2, f"{utype}: опыт +{xp - xp0} за ход ({xp0} → {xp})"))
            if level - level0 >= 2:
                out.append((2, f"{utype}: уровень {level0} → {level} за ход"))
        # free promotions exist (great generals, some wonders), but not many
        honest = max(n for n in range(1, 20) if xp_for_level(n) <= xp + 30)
        if level > honest + 1:
            out.append((3, f"{utype}: уровень {level} при опыте {xp} (опыт даёт максимум {honest})"))
    return out


def science_per_tech(turns):
    """Science spent per tech learned over the recorded turns, None if too few techs."""
    ts = sorted(turns)
    gained = g(turns[ts[-1]], "techs") - g(turns[ts[0]], "techs")
    if gained < 8:
        return None
    return sum(g(turns[t], "science") for t in ts[:-1]) / gained


def research_check(pid, series):
    """A research multiplier (trainer) shows as techs far cheaper than everyone else's."""
    mine = science_per_tech(series[pid])
    others = sorted(v for p, v in ((p, science_per_tech(t)) for p, t in series.items() if p != pid) if v)
    if mine is None or len(others) < 2:
        return []
    median = others[len(others) // 2]
    if mine < 0.4 * median:
        last = max(series[pid])
        return [(last, 3, f"технология обходится в {median / mine:.1f} раза дешевле, чем у остальных "
                          f"({mine:.0f} колб против {median:.0f})")]
    return []


def analyse_series(series, names, me, show_me=False):
    """Report for already loaded data: [(score, name, turns, [(turn, weight, text)])]."""
    report = []
    for pid, turns in series.items():
        if pid == me and not show_me:
            continue
        flags = []
        ts = sorted(turns)
        for a, b in zip(ts, ts[1:]):
            if b != a + 1:
                continue  # gap or reload: can't compare
            flags += [(b, w, t) for w, t in checks(turns[a], turns[b]) + unit_checks(turns[a], turns[b])]
        # level 7+ units: rare, worth a look even without a jump between turns
        best = max((lv for s in turns.values() for _, lv, _ in units(s).values()), default=0)
        if best >= 7:
            flags.append((ts[-1], 1, f"есть юнит {best}-го уровня"))
        flags += research_check(pid, series)
        score = sum(w for _, w, _ in flags)
        report.append((score, names[pid], len(ts), flags))
    report.sort(key=lambda r: -r[0])
    return report


def analyse(path, show_me=False):
    series, names, me = load(path)
    return analyse_series(series, names, me, show_me), (names.get(me) if me is not None else "?")


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
