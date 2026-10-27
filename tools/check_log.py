"""Checks that the in-game logger really works: run after playing a few turns.

    python tools/check_log.py [Lua.log or saves/<game>.log]

Reports the logger version, errors, and which expected fields are missing or
always zero (an API method that doesn't exist in your game version).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viewer"))
from civstats import LOG_PATH, LOGGER_VERSION, Data  # noqa: E402
from metrics_tree import TREE  # noqa: E402

MY_FIELDS = ["techIds", "policyIds", "branchIds", "research", "culturePoints", "loggerVersion",
             "speed", "speedPercent", "worldSize", "worldPlayers", "mapW", "mapH", "gameId"]
RIVAL_FIELDS = ["dist", "war", "knownCities"]
# Legitimately zero for many civs/turns: don't flag them as broken
OFTEN_ZERO = {"starvingCities", "tourism", "GetNumGreatWorks", "GetNumWorldWonders", "GetGoldenAgeTurns",
              "GetScoreFromFutureTech", "GetScoreFromGreatWorks", "GetScoreFromReligion",
              "GetScienceFromResearchAgreements", "GetScienceFromBudgetDeficit",
              "GetUnhappinessFromOccupiedCities", "GetUnhappinessFromPublicOpinion",
              "GetNumUnitsOutOfSupply", "GetWarmongerThreat", "GetHappinessFromMinorCivs",
              "GetHappinessFromNaturalWonders", "GetHappinessFromReligion", "GetFaithPerTurnFromReligion",
              "GetGoldPerTurnFromDiplomacy", "GetNumPolicyBranchesFinished", "GetScienceFromOtherPlayers",
              "GetNumInternationalTradeRoutesUsed", "GetLifetimeCombatExperience", "war", "knownCities"}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else LOG_PATH
    d = Data(path, archive=False)
    d.poll()
    print(f"Log: {path}")
    diag = d.diagnose()
    print(f"Status: {diag[1] if diag else 'OK'}")
    print(f"Logger version: {d.version} (viewer expects {LOGGER_VERSION})")
    for e in d.errors[-5:]:
        print(f"  ERROR: {e}")
    if d.me is None:
        print("No data from your civilization yet.")
        return 1
    turns = sorted(d.series[d.me])
    print(f"Your civ: {d.names[d.me]}, turns {turns[0]}..{turns[-1]} ({len(turns)} logged), "
          f"civs: {len(d.series)}")
    mine = d.series[d.me][turns[-1]]
    print(f"Game: speed={mine.get('speed')} ({mine.get('speedPercent')}%), map={mine.get('worldSize')} "
          f"{mine.get('mapW')}x{mine.get('mapH')}, id={mine.get('gameId')}")

    leaves = [n.key for n in TREE.walk() if n.is_leaf]
    missing = [k for k in leaves + MY_FIELDS if k not in mine]
    rivals = [p for p in d.series if p != d.me]
    rival_last = [d.series[p][max(d.series[p])] for p in rivals]
    missing += [f"{k} (rivals)" for k in RIVAL_FIELDS if rival_last and all(k not in r for r in rival_last)]
    print(f"\nMissing fields ({len(missing)}): {', '.join(missing) or 'none'}")

    every = [s for ts in d.series.values() for s in ts.values()]
    zero = [k for k in leaves if k not in OFTEN_ZERO and any(k in s for s in every)
            and all(not s.get(k) for s in every)]
    print(f"Always zero across all civs and turns ({len(zero)}): {', '.join(zero) or 'none'}")
    if rival_last and all(r.get("dist", -1) < 0 for r in rival_last):
        print("Distances: no rival city seen yet (normal early in the game).")
    print(f"\nKnown techs: {len(str(mine.get('techIds', '')).split(','))}, "
          f"policies: {mine.get('policyIds') or '-'}, branches: {mine.get('branchIds') or '-'}")
    return 0 if not (diag and diag[0] == "red") and not missing else 1


if __name__ == "__main__":
    sys.exit(main())
