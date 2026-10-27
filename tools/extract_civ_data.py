"""Builds viewer/civ_data.json from the game's own database cache.

Civ 5 keeps the full game rules (civilizations, traits, unique units,
buildings, improvements, techs, eras) and all texts in SQLite files under
Documents/My Games/Sid Meier's Civilization 5/cache after the game has run
once. Reading them gives exact, version-matched data in the game's language.

    python tools/extract_civ_data.py [cache_dir] [language]   (default ru_RU)
"""
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "viewer", "civ_data.json")


def default_cache():
    sys.path.insert(0, os.path.join(HERE, "..", "viewer"))
    from civstats import find_log_path
    return os.path.join(os.path.dirname(os.path.dirname(find_log_path())), "cache")


def clean(text):
    if not text:
        return ""
    text = text.split("|")[0]  # Russian names carry all grammatical cases: "Рыцари|рыцарей|..."
    text = text.replace("[NEWLINE]", " ")
    text = re.sub(r"\[ICON_[A-Z_0-9]+\]", "", text)
    text = re.sub(r"\[/?COLOR[A-Z_0-9]*\]|\[ENDCOLOR\]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def main():
    cache = sys.argv[1] if len(sys.argv) > 1 else default_cache()
    lang = sys.argv[2] if len(sys.argv) > 2 else "ru_RU"
    db = sqlite3.connect(os.path.join(cache, "Civ5DebugDatabase.db"))
    db.row_factory = sqlite3.Row
    loc = sqlite3.connect(os.path.join(cache, "Localization-Merged.db"))

    texts = {}
    for table in (f"Language_{lang}", "Language_en_US"):
        try:
            for tag, txt in loc.execute(f"select Tag, Text from {table}"):
                texts.setdefault(tag, txt)
        except sqlite3.OperationalError:
            pass

    def t(key):
        return clean(texts.get(key, key or ""))

    q = lambda sql, *a: db.execute(sql, a).fetchall()

    eras = {r["Type"]: {"id": r["ID"], "name": t(r["Description"])} for r in q("select * from Eras")}
    techs = {r["Type"]: {"name": t(r["Description"]), "era": r["Era"], "cost": r["Cost"],
                         "column": r["GridX"]} for r in q("select * from Technologies")}

    def tech_info(tech):
        if not tech or tech not in techs:
            return {"tech": None, "era": None, "eraName": None, "column": 0}
        ti = techs[tech]
        return {"tech": ti["name"], "era": eras[ti["era"]]["id"],
                "eraName": eras[ti["era"]]["name"], "column": ti["column"]}

    civs = {}
    for c in q("select * from Civilizations where Playable = 1"):
        ct = c["Type"]
        leader = q("select l.* from Civilization_Leaders cl join Leaders l on l.Type = cl.LeaderheadType "
                   "where cl.CivilizationType = ?", ct)[0]
        trait = q("select t.* from Leader_Traits lt join Traits t on t.Type = lt.TraitType "
                  "where lt.LeaderType = ?", leader["Type"])
        trait = trait[0] if trait else None

        units = []
        for u in q("select u.*, o.UnitClassType as Cls from Civilization_UnitClassOverrides o "
                   "join Units u on u.Type = o.UnitType where o.CivilizationType = ?", ct):
            base = q("select u.Description from UnitClasses c join Units u on u.Type = c.DefaultUnit "
                     "where c.Type = ?", u["Cls"])
            units.append({"name": t(u["Description"]), "replaces": t(base[0][0]) if base else "",
                          "combat": u["Combat"], "ranged": u["RangedCombat"], "moves": u["Moves"],
                          "help": t(u["Help"]), **tech_info(u["PrereqTech"])})

        buildings = []
        for b in q("select b.*, o.BuildingClassType as Cls from Civilization_BuildingClassOverrides o "
                   "join Buildings b on b.Type = o.BuildingType where o.CivilizationType = ? "
                   "and o.BuildingType is not null", ct):
            base = q("select b.Description from BuildingClasses c join Buildings b on b.Type = c.DefaultBuilding "
                     "where c.Type = ?", b["Cls"])
            buildings.append({"name": t(b["Description"]), "replaces": t(base[0][0]) if base else "",
                              "help": t(b["Help"]), **tech_info(b["PrereqTech"])})

        improvements = []
        for i in q("select * from Improvements where CivilizationType = ?", ct):
            build = q("select PrereqTech from Builds where ImprovementType = ?", i["Type"])
            improvements.append({"name": t(i["Description"]), "help": t(i["Help"]),
                                 **tech_info(build[0][0] if build else None)})

        civs[t(c["ShortDescription"])] = {
            "type": ct,
            "name": t(c["Description"]),
            "leader": t(leader["Description"]),
            "trait": t(trait["ShortDescription"]) if trait else "",
            "traitHelp": t(trait["Description"]) if trait else "",
            "units": units, "buildings": buildings, "improvements": improvements,
        }

    # Tech tree and social policies, keyed by database ID (what the logger writes)
    tech_tree = {}
    for r in q("select * from Technologies"):
        pre = [x[0] for x in q("select t.ID from Technology_PrereqTechs p join Technologies t "
                                "on t.Type = p.PrereqTech where p.TechType = ?", r["Type"])]
        tech_tree[r["ID"]] = {"type": r["Type"], "name": t(r["Description"]), "era": eras[r["Era"]]["id"],
                              "cost": r["Cost"], "prereqs": pre}
    branches = {}
    for r in q("select * from PolicyBranchTypes"):
        branches[r["ID"]] = {"type": r["Type"], "name": t(r["Description"]),
                             "era": eras[r["EraPrereq"]]["id"] if r["EraPrereq"] in eras else 0}
    branch_id = {b["type"]: i for i, b in branches.items()}
    policies = {}
    for r in q("select * from Policies"):
        pre = [x[0] for x in q("select p2.ID from Policy_PrereqPolicies pp join Policies p2 "
                                "on p2.Type = pp.PrereqPolicy where pp.PolicyType = ?", r["Type"])]
        policies[r["ID"]] = {"type": r["Type"], "name": t(r["Description"]), "help": t(r["Help"]),
                             "branch": branch_id.get(r["PolicyBranchType"]), "level": r["Level"],
                             "prereqs": pre}

    out = {"eras": sorted((e["id"], e["name"]) for e in eras.values()), "civs": civs,
           "techs": tech_tree, "branches": branches, "policies": policies}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"{len(civs)} civilizations -> {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
