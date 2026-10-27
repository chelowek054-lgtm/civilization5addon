"""In-game advisor: civ profile, power-spike windows and "you are doing it wrong" warnings.

Civ facts (traits, unique units/buildings, the tech and era that unlock them)
come from civ_data.json, extracted from the game's own database
(tools/extract_civ_data.py). Strategic focus per civ is community consensus.
"""
import json
import os

from metrics_tree import TREE

HERE = os.path.dirname(os.path.abspath(__file__))

# Main victory focus and a one-line plan per civ (community consensus, BNW).
STRATEGY = {
    "Америка": ("Наука / Дипломатия", "Широкая империя: покупайте клетки, Минитмены — сильная оборона в Новое время."),
    "Аравия": ("Культура / Религия", "Базар удваивает роскошь — торгуйте ею; караваны дают веру и религию."),
    "Ацтеки": ("Завоевание", "Ранняя агрессия: Воины-ягуары лечатся за убийства и дают культуру."),
    "Китай": ("Завоевание / Наука", "Чжугэ ну — лучший средневековый стрелок; генералы сильнее."),
    "Египет": ("Культура (чудеса)", "+20% к чудесам: занимайте все ранние чудеса, Гробница даёт довольство."),
    "Англия": ("Завоевание (море) / Наука", "Флот и шпионы: Йомены обороняются, Линейные корабли захватывают побережье."),
    "Франция": ("Культура", "Культура из столицы и произведения: ставьте Шато у роскоши, музеи и чудеса."),
    "Германия": ("Завоевание / Дипломатия", "Варвары переходят к вам: качайте армию рано, Ганзейская контора — деньги."),
    "Греция": ("Дипломатия", "Влияние на города-государства держится дольше: покупайте союзы."),
    "Индия": ("Религия / Наука (высокие города)", "Мало, но большие города: меньше недовольства от населения."),
    "Ирокезы": ("Завоевание / Широкая империя", "Леса — дороги; Длинный дом: строите в лесах."),
    "Япония": ("Завоевание", "Раненые юниты бьют в полную силу: Самураи — средневековая волна."),
    "Турция": ("Завоевание (море)", "Янычары лечатся после боя — пик в Новое время; захватывайте корабли варваров."),
    "Персия": ("Завоевание / Культура", "Длинные золотые века: Бессмертные рано, Двор сатрапа — золото."),
    "Рим": ("Завоевание", "Легионы и Баллисты в Античности — главное окно войны; здания строятся быстрее."),
    "Россия": ("Завоевание / Широкая империя", "Двойные стратегические ресурсы: Острог для обороны, Казаки в Новейшее время."),
    "Сиам": ("Дипломатия", "Города-государства дают на 50% больше: Ват = наука + культура."),
    "Сонгай": ("Завоевание", "Втрое больше золота за грабёж: Всадники мандекалу берут города."),
    "Монголия": ("Завоевание", "Пик — Кешиктены в Средневековье: стреляют на скаку. Бейте города-государства (+30%)."),
    "Инки": ("Широкая империя / Наука", "Горы и террасы: Пращники отпугивают, дороги в горах бесплатны."),
    "Испания": ("Завоевание / Религия", "Природные чудеса дают много: Конкистадоры основывают города, Терции в Новое время."),
    "Полинезия": ("Культура", "Моаи + ранняя разведка океана: дешёвое расширение на острова."),
    "Дания": ("Завоевание (набеги)", "Высадки без штрафа: Берсерки в Средневековье грабят побережье."),
    "Корея": ("Наука", "Специалисты дают науку: великие учёные, Хвачха для обороны."),
    "Вавилон": ("Наука", "Бесплатный великий учёный рано и рост учёных +50%: библиотеки и университеты."),
    "Австрия": ("Дипломатия", "Женитесь на городах-государствах: Кофейня ускоряет великих людей."),
    "Византия": ("Религия", "Лишнее верование: сильная религия, Катафракты в Античности."),
    "Карфаген": ("Широкая империя (море)", "Бесплатные гавани, горы проходимы: Лесные слоны в Античности."),
    "Кельты": ("Религия / Культура", "Вера из лесов без построек: ранний пантеон и религия."),
    "Эфиопия": ("Религия / Оборона", "+20% в бою против сильнейших: Стела и вера, Мехал Сефари защищают."),
    "Гунны": ("Завоевание (раннее)", "Конные лучники и Тараны: окно войны — первые 60–80 ходов."),
    "Майя": ("Наука / Религия", "Пирамида рано, календарь даёт великих людей по выбору."),
    "Нидерланды": ("Экономика / Дипломатия", "Польдеры на болотах, роскошь не теряет довольства при торговле."),
    "Швеция": ("Дипломатия / Завоевание", "Великие люди за дружбу; Хаккапелиты и Каролинцы с генералами."),
    "Ассирия": ("Завоевание / Наука", "Технологии за захват городов: Осадные башни — окно в Античности."),
    "Бразилия": ("Культура (туризм)", "Вырубка красного дерева и карнавалы: туризм в золотые века."),
    "Индонезия": ("Широкая империя (острова)", "Уникальная роскошь на других островах: Канди даёт веру."),
    "Марокко": ("Культура / Экономика", "Торговые пути дают золото и культуру; Касба в пустыне."),
    "Польша": ("Любая (гибкая)", "Бесплатные политики каждую эру: Крылатые гусары в Новое время."),
    "Португалия": ("Экономика / Дипломатия", "Торговля роскошью и Фейтории; Нау грабят побережье."),
    "Шошоны": ("Широкая империя / Завоевание", "Больше земли при основании, Следопыты выбирают награду руин."),
    "Венеция": ("Дипломатия", "Один город, зато купцы покупают города-государства."),
    "Зулусы": ("Завоевание", "Импи и опыт без содержания: Иканда — сильнейшая пехота Средневековья."),
}

# Rough number of techs that marks the start of each era (standard speed).
ERA_TECHS = [0, 9, 17, 27, 39, 51, 63, 73]


def load_civ_data():
    try:
        with open(os.path.join(HERE, "civ_data.json"), encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {"eras": [], "civs": {}}


CIV_DATA = load_civ_data()
ERA_NAMES = dict((i, n) for i, n in CIV_DATA["eras"]) or {i: str(i) for i in range(8)}


def current_era(stats):
    if "GetCurrentEra" in stats:
        return int(stats["GetCurrentEra"])
    techs = stats.get("techs", 0)
    return max(i for i, n in enumerate(ERA_TECHS) if techs >= n)


def uniques(civ):
    info = CIV_DATA["civs"].get(civ, {})
    out = []
    for kind, label in (("units", "юнит"), ("buildings", "здание"), ("improvements", "улучшение")):
        for u in info.get(kind, []):
            out.append(dict(u, kind=label))
    return out


def spike_eras(civ):
    """Eras where a unique unit is active (its era and the next one)."""
    eras = set()
    for u in uniques(civ):
        if u["kind"] == "юнит" and u.get("era") is not None and u.get("combat"):
            eras.update({u["era"], u["era"] + 1})
    return eras


NEAR = 10          # tiles between nearest cities: closer than this is a neighbour (standard map)
STD_MAP = (80, 52, 8)   # standard map: width, height, players


def game_scale(data):
    """How this game differs from standard speed / standard map.

    speed  — turn multiplier (quick 0.67, epic 1.5, marathon 3): benchmarks like
             "3 cities by turn 40" and "over 10 turns" are stretched by it.
    dist   — map-size multiplier for neighbour distances.
    land   — land per player relative to standard, softens city-count targets.
    Old logs without these fields behave as standard.
    """
    me = data.me
    s = data.series[me][max(data.series[me])] if me in data.series and data.series[me] else {}
    speed = (s.get("speedPercent") or 100) / 100
    w, h = s.get("mapW") or STD_MAP[0], s.get("mapH") or STD_MAP[1]
    players = s.get("worldPlayers") or STD_MAP[2]
    dist = ((w * h) / (STD_MAP[0] * STD_MAP[1])) ** 0.5
    land = ((w * h / players) / (STD_MAP[0] * STD_MAP[1] / STD_MAP[2])) ** 0.5
    names = {"QUICK": "быстрая", "STANDARD": "обычная", "EPIC": "эпическая", "MARATHON": "марафон",
             "DUEL": "дуэль", "TINY": "крошечная", "SMALL": "маленькая", "LARGE": "большая", "HUGE": "огромная"}
    speed_name = s.get("speed")
    size_name = s.get("worldSize")
    return {"speed": speed, "dist": dist, "land": min(1.4, max(0.75, land)),
            "label": speed_name and f"скорость {names.get(str(speed_name).split('_')[-1], speed_name)}",
            "size": size_name and f"карта {names.get(str(size_name).split('_')[-1], size_name)}"}


def turns(n, scale):
    """n standard-speed turns at this game's speed."""
    return max(1, round(n * scale["speed"]))

# How each civ focus maps onto a metric-tree group
FOCUS_GROUP = [("Завоевание", "g_military"), ("Наука", "g_science"), ("Культура", "g_culture"),
               ("Религия", "g_faith"), ("Дипломатия", "g_economy"), ("Экономика", "g_economy"),
               ("Широкая", "g_scale"), ("Любая", "g_scale")]

# What raises each group (one line per group)
GROUP_ACTIONS = {
    "g_scale": "поселенцы на свободные земли, рост городов: фермы, амбары, излишек еды",
    "g_economy": "рынки, торговые пути, дороги между городами, мастерские и шахты",
    "g_science": "библиотеки → университеты, рост населения, научные договоры",
    "g_culture": "монументы, амфитеатры, чудеса, великие произведения в слотах",
    "g_faith": "святилища, храмы, пантеон и религия пораньше",
    "g_stability": "новые виды роскоши (обмен с соседями), колизеи, храмы",
    "g_military": "современные юниты на уровне эпохи, стены и стрелки в пограничных городах",
}
GROUP_LABELS = {g.key: g.label for g in TREE.children}


def rivals(data, idx, pids):
    """One dict per met rival on the latest shown turn, nearest first."""
    me = data.me
    if me is None or me not in data.series or not data.series[me]:
        return []
    t = max(data.series[me])
    s = data.series[me][t]
    my_mil = s.get("military", 0) or 1
    sc = game_scale(data)
    window, near_tiles = turns(10, sc), round(NEAR * sc["dist"])
    out = []
    for p in pids:
        if p == me or t not in data.series[p]:
            continue
        r = data.series[p][t]
        past = [x for x in data.series[p] if x <= t - window]
        mil_then = data.series[p][past[-1]].get("military", 0) if past else None
        groups = {g: idx[p][t].get(g) for g in GROUP_LABELS if g != "g_score" and t in idx.get(p, {})}
        groups = {g: v for g, v in groups.items() if v is not None}
        dist = r.get("dist")
        out.append({
            "pid": p, "name": data.names.get(p, str(p)),
            "dist": None if dist is None or dist < 0 else int(dist),
            "near": dist is not None and 0 <= dist <= near_tiles,
            "window": window,
            "war": r.get("war", 0) >= 1,
            "mil_ratio": r.get("military", 0) / my_mil,
            "mil_growth": (r.get("military", 0) / mil_then - 1) if mil_then else None,
            "overall": idx.get(p, {}).get(t, {}).get("overall", 0),
            "best": max(groups, key=groups.get) if groups else None,
            "groups": groups,
        })
    out.sort(key=lambda x: (x["dist"] is None, x["dist"] or 0))
    return out


def rival_role(rv):
    """(level, short role) for one rival relative to you."""
    near = rv["near"]
    rising = (rv["mil_growth"] or 0) > 0.3
    if rv["war"] and rv["mil_ratio"] > 1:
        return "red", "война, он сильнее"
    if rv["war"]:
        return "yellow", "война"
    if near and rv["mil_ratio"] > 1.5:
        return "red" if rising else "yellow", "угроза рядом" + (", армия растёт" if rising else "")
    if near and rv["mil_ratio"] < 0.6:
        return "green", "слабый сосед — цель"
    if rv["overall"] >= 75:
        return "yellow", "лидер партии"
    return "green", "нейтрально"


def development_plan(data, idx, pids):
    """Up to 5 prioritized lines: what to develop given your civ and the rivals."""
    me = data.me
    if me is None or me not in idx or not idx[me]:
        return []
    t = max(idx[me])
    mine = idx[me][t]
    civ = data.names.get(me, "")
    focus, _ = STRATEGY.get(civ, ("", ""))
    focus_group = next((g for k, g in FOCUS_GROUP if k in focus), None)
    rv = rivals(data, idx, pids)
    s = data.series[me][max(data.series[me])]
    era = current_era(s)
    plan = []

    # 1. survival
    threats = [r for r in rv if rival_role(r)[1].startswith(("угроза", "война, он"))]
    if threats:
        r = threats[0]
        where = f"в {r['dist']} клетках" if r["dist"] is not None else "рядом"
        plan.append(f"Оборона прежде всего: {r['name']} {where}, армия ×{r['mil_ratio']:.1f} от вашей. "
                    f"Стены и стрелки в ближних городах, дружба или договор о границах с ним.")

    # 2. foundation
    if mine.get("g_scale", 100) < 40:
        plan.append("Расширяйтесь: масштаб империи — основа всех остальных показателей. "
                    + GROUP_ACTIONS["g_scale"].capitalize() + ".")

    # 3. your civ's focus vs. the leader in that direction
    if focus_group and focus_group in mine:
        leader = max(rv, key=lambda r: r["groups"].get(focus_group, 0), default=None)
        lead_v = leader["groups"].get(focus_group, 0) if leader else 0
        if leader and lead_v - mine[focus_group] > 40:
            plan.append(f"Ваш фокус — {focus}, но здесь далеко впереди {leader['name']} "
                        f"({lead_v:.0f} против {mine[focus_group]:.0f}). Догоняйте "
                        f"({GROUP_ACTIONS.get(focus_group, '')}) или смените путь к победе.")
        else:
            plan.append(f"Держитесь фокуса «{focus}»: {GROUP_ACTIONS.get(focus_group, '')}.")

    # 4. a weak neighbour is an opportunity, especially in your power window
    prey = [r for r in rv if rival_role(r)[1].startswith("слабый")]
    if prey:
        r = prey[0]
        spike = era in spike_eras(civ)
        plan.append(f"Возможность: {r['name']} в {r['dist']} клетках с армией {r['mil_ratio']:.0%} от вашей"
                    + (" — сейчас ваш пик, лучшее время для захвата." if spike else
                       " — можно расшириться за его счёт или требовать уступок."))

    # 5. a runaway leader
    leader = max(rv, key=lambda r: r["overall"], default=None)
    if leader and leader["overall"] - mine.get("overall", 0) > 30:
        lg = GROUP_LABELS.get(leader["best"], "")
        plan.append(f"{leader['name']} уходит в отрыв (сила {leader['overall']:.0f}, сильнее всего в «{lg}»). "
                    "Не соревнуйтесь с ним там; объединяйтесь с другими против него.")

    # 6. build on your best side
    groups = {g: v for g, v in mine.items() if g in GROUP_LABELS and g != "g_score"}
    if groups:
        best = max(groups, key=groups.get)
        weak = min(groups, key=groups.get)
        if groups[best] >= 50:
            plan.append(f"Ваша сильная сторона — «{GROUP_LABELS[best]}» ({groups[best]:.0f}): стройте стратегию на ней.")
        if len(plan) < 5 and groups[weak] < 25 and weak != best:
            plan.append(f"Подтяните «{GROUP_LABELS[weak]}» ({groups[weak]:.0f}): {GROUP_ACTIONS.get(weak, '')}.")
    return plan[:5]


# ---------- what to research ----------

TECHS = {int(k): v for k, v in CIV_DATA.get("techs", {}).items()}
TECH_BY_TYPE = {v["type"]: k for k, v in TECHS.items()}
POLICIES = {int(k): v for k, v in CIV_DATA.get("policies", {}).items()}
BRANCHES = {int(k): v for k, v in CIV_DATA.get("branches", {}).items()}
BRANCH_BY_TYPE = {v["type"].replace("POLICY_BRANCH_", ""): k for k, v in BRANCHES.items()}

# Techs that fix a problem, earliest first: the first one you lack is the goal
PROBLEM_TECHS = {
    "defence": ("армия слабее соседей", ["TECH_BRONZE_WORKING", "TECH_MASONRY", "TECH_CONSTRUCTION",
                                         "TECH_MACHINERY", "TECH_GUNPOWDER", "TECH_RIFLING"]),
    "happiness": ("недовольство", ["TECH_CONSTRUCTION", "TECH_PHILOSOPHY", "TECH_PRINTING_PRESS"]),
    "gold": ("отрицательный доход", ["TECH_CURRENCY", "TECH_BANKING", "TECH_ECONOMICS"]),
    "science": ("отставание в науке", ["TECH_WRITING", "TECH_EDUCATION", "TECH_SCIENTIFIC_THEORY"]),
    "growth": ("мало городов и еды", ["TECH_POTTERY", "TECH_CALENDAR", "TECH_CIVIL_SERVICE"]),
}
FOCUS_TECHS = [
    ("Наука", ["TECH_WRITING", "TECH_PHILOSOPHY", "TECH_EDUCATION", "TECH_SCIENTIFIC_THEORY", "TECH_PLASTIC"]),
    ("Культура", ["TECH_DRAMA", "TECH_ACOUSTICS", "TECH_ARCHAEOLOGY", "TECH_RADIO"]),
    ("Религия", ["TECH_CALENDAR", "TECH_PHILOSOPHY", "TECH_THEOLOGY"]),
    ("Завоевание", ["TECH_BRONZE_WORKING", "TECH_IRON_WORKING", "TECH_STEEL", "TECH_GUNPOWDER", "TECH_DYNAMITE"]),
    ("Дипломатия", ["TECH_CURRENCY", "TECH_BANKING", "TECH_ECONOMICS"]),
    ("Экономика", ["TECH_CURRENCY", "TECH_BANKING", "TECH_ECONOMICS"]),
    ("Широкая", ["TECH_POTTERY", "TECH_CURRENCY", "TECH_CIVIL_SERVICE"]),
    ("Любая", ["TECH_WRITING", "TECH_CURRENCY", "TECH_EDUCATION"]),
]


def id_set(value):
    """Logger id lists: '3,7,12' (text), a single id parsed as a number, or empty."""
    if value is None or value == "":
        return set()
    if isinstance(value, float):
        return {int(value)}
    return {int(x) for x in str(value).split(",") if x.strip().isdigit()}


def _missing_path(goal, known):
    """Techs still needed for `goal` (prerequisites first)."""
    need, stack = set(), [goal]
    while stack:
        t = stack.pop()
        if t in known or t in need or t not in TECHS:
            continue
        need.add(t)
        stack.extend(TECHS[t]["prereqs"])
    return sorted(need, key=lambda t: (TECHS[t]["era"], TECHS[t]["cost"]))


def research_plan(data, warns_levels=None):
    """Up to 3 (goal, reason, research_now, steps). None if the log has no tech list."""
    me = data.me
    if me is None or me not in data.series or not data.series[me]:
        return None
    s = data.series[me][max(data.series[me])]
    if "techIds" not in s or not TECHS:
        return None
    known = id_set(s["techIds"])
    civ = data.names.get(me, "")
    focus, _ = STRATEGY.get(civ, ("", ""))
    others = [data.series[p][max(data.series[p])] for p in data.series if p != me]
    top_mil = max([o.get("military", 0) for o in others] or [0])

    goals = []   # (reason, tech type)

    def first_missing(types):
        return next((x for x in types if x in TECH_BY_TYPE and TECH_BY_TYPE[x] not in known), None)

    problems = []
    if top_mil and s.get("military", 0) / top_mil < 0.6:
        problems.append("defence")
    if s.get("happiness", 0) < 0:
        problems.append("happiness")
    if s.get("goldRate", 0) < 0:
        problems.append("gold")
    sci = sorted([o.get("science", 0) for o in others] + [s.get("science", 0)], reverse=True)
    if sci.index(s.get("science", 0)) + 1 > (len(sci) + 1) / 2:
        problems.append("science")
    if s.get("cities", 0) < 3 or s.get("starvingCities", 0) > 0:
        problems.append("growth")
    for p in problems[:2]:   # leave room for your uniques and focus
        reason, types = PROBLEM_TECHS[p]
        tt = first_missing(types)
        if tt:
            goals.append((reason, tt))

    # your next unique unit / building
    for u in sorted(uniques(civ), key=lambda u: u.get("era") or 99):
        tid = next((k for k, v in TECHS.items() if v["name"] == u.get("tech")), None)
        if tid is not None and tid not in known:
            goals.append((f"уникальный {u['kind']} {u['name']}", TECHS[tid]["type"]))
            break

    for key, types in FOCUS_TECHS:
        if key in focus:
            tt = first_missing(types)
            if tt:
                goals.append((f"фокус «{focus}»", tt))
            break

    plan, seen = [], set()
    for reason, tt in goals:
        goal = TECH_BY_TYPE[tt]
        if goal in seen:
            continue
        seen.add(goal)
        path = _missing_path(goal, known)
        now = [t for t in path if all(p in known for p in TECHS[t]["prereqs"])]
        plan.append((TECHS[goal]["name"], reason, [TECHS[t]["name"] for t in now], len(path)))
        if len(plan) == 3:
            break
    return plan


# ---------- social policies ----------

FOCUS_BRANCHES = [
    ("Наука", ["TRADITION", "RATIONALISM", "PATRONAGE"], "FREEDOM"),
    ("Культура", ["TRADITION", "AESTHETICS", "RATIONALISM"], "FREEDOM"),
    ("Религия", ["TRADITION", "PIETY", "RATIONALISM"], "ORDER"),
    ("Завоевание", ["LIBERTY", "HONOR", "COMMERCE", "RATIONALISM"], "AUTOCRACY"),
    ("Дипломатия", ["LIBERTY", "PATRONAGE", "COMMERCE"], "FREEDOM"),
    ("Экономика", ["TRADITION", "COMMERCE", "PATRONAGE"], "FREEDOM"),
    ("Широкая", ["LIBERTY", "COMMERCE", "RATIONALISM"], "ORDER"),
    ("Любая", ["TRADITION", "RATIONALISM", "AESTHETICS"], "FREEDOM"),
]
IDEOLOGIES = {"FREEDOM", "ORDER", "AUTOCRACY"}


def policy_plan(data):
    """List of advice lines about social policies. None if the log has no policy list."""
    me = data.me
    if me is None or me not in data.series or not data.series[me]:
        return None
    s = data.series[me][max(data.series[me])]
    if "policyIds" not in s or not POLICIES:
        return None
    adopted = id_set(s["policyIds"])
    unlocked = id_set(s.get("branchIds"))
    civ = data.names.get(me, "")
    focus, _ = STRATEGY.get(civ, ("", ""))
    order, ideology = next(((b, i) for k, b, i in FOCUS_BRANCHES if k in focus), FOCUS_BRANCHES[-1][1:])
    order = list(order)
    # tall vs wide opener depends on how many cities you actually have
    if order[0] == "TRADITION" and s.get("cities", 0) >= 5:
        order[0] = "LIBERTY"
    elif order[0] == "LIBERTY" and s.get("cities", 0) <= 2 and max(data.series[me]) > turns(40, game_scale(data)):
        order[0] = "TRADITION"
    era = current_era(s)
    lines = []

    # time to the next policy
    cost, have, rate = s.get("GetNextPolicyCost", 0), s.get("culturePoints", s.get("GetJONSCulture", 0)), s.get("culture", 0)
    if cost and rate:
        left = max(0, cost - have)
        lines.append(f"Следующая политика через ~{-(-left // rate):.0f} ход(ов) ({have:g}/{cost:g} культуры, +{rate:g}/ход).")

    def next_in_branch(bid):
        cands = [pid for pid, p in POLICIES.items()
                 if p["branch"] == bid and pid not in adopted and all(x in adopted for x in p["prereqs"])
                 and not p.get("level")]
        return min(cands) if cands else None

    open_branches = [b for b in (BRANCH_BY_TYPE.get(t) for t in order) if b in unlocked]
    open_branches += [b for b in unlocked if b not in open_branches and BRANCHES[b]["type"].split("_")[-1] not in IDEOLOGIES]
    for bid in open_branches:
        nxt = next_in_branch(bid)
        if nxt is not None:
            p = POLICIES[nxt]
            help_ = p["help"][len(p["name"]):].strip() if p["help"].startswith(p["name"]) else p["help"]
            lines.append(f"Берите: «{p['name']}» (ветка «{BRANCHES[bid]['name']}»). {help_[:160]}")
            break
    else:
        for t in order:
            bid = BRANCH_BY_TYPE.get(t)
            if bid is None or bid in unlocked:
                continue
            b = BRANCHES[bid]
            if era >= b["era"]:
                lines.append(f"Откройте ветку «{b['name']}» — она лучше всего подходит под фокус «{focus or 'универсальный'}».")
            else:
                lines.append(f"Следующая ветка — «{b['name']}», откроется в эпоху «{ERA_NAMES.get(b['era'], b['era'])}». "
                             "Пока копите культуру или берите из открытых веток.")
            break

    plan_names = " → ".join(BRANCHES[BRANCH_BY_TYPE[t]]["name"] for t in order if t in BRANCH_BY_TYPE)
    lines.append(f"Порядок веток для вас: {plan_names}.")
    ideo = BRANCHES.get(BRANCH_BY_TYPE.get(ideology))
    if ideo:
        has_ideo = any(BRANCHES[b]["type"].split("_")[-1] in IDEOLOGIES for b in unlocked)
        if era >= 4 and not has_ideo:
            lines.append(f"Идеология: «{ideo['name']}» (откроется после 3 фабрик или в Новейшее время).")
        elif era < 4:
            lines.append(f"Идеология в будущем: «{ideo['name']}».")
    return lines


def _rank(values, mine, higher_is_better=True):
    better = sum(1 for v in values if (v > mine if higher_is_better else v < mine))
    return better + 1


def analyse(data, idx, pids):
    """Returns (profile_lines, warnings). warnings: list of (level, text), level in 'red','yellow','green'."""
    me = data.me
    if me is None or me not in data.series or not data.series[me]:
        return [], [("yellow", "Нет данных о вашей цивилизации. Дождитесь начала хода.")]
    civ = data.names.get(me, "")
    t = max(data.series[me])
    s = data.series[me][t]
    rival_ids = [p for p in pids if p != me and t in data.series[p]]
    rs = [data.series[p][t] for p in rival_ids]
    era = current_era(s)
    warns = []

    # --- profile ---
    info = CIV_DATA["civs"].get(civ, {})
    focus, plan = STRATEGY.get(civ, ("?", ""))
    prof = [f"{info.get('name', civ)} — {info.get('leader', '')}",
            f"Фокус: {focus}",
            plan,
            f"Особенность «{info.get('trait', '')}»: {info.get('traitHelp', '')}",
            ""]
    for u in uniques(civ):
        when = f"{u['eraName']}, {u['tech']}" if u.get("tech") else "великий человек / особый юнит"
        stat = f", сила {u['combat']}" + (f"/{u['ranged']}" if u.get("ranged") else "") if u.get("combat") else ""
        repl = f" (вместо: {u['replaces']})" if u.get("replaces") else ""
        prof.append(f"• {u['kind']} {u['name']}{repl} — {when}{stat}")

    # --- power spike ---
    spikes = spike_eras(civ)
    if era in spikes:
        names = ", ".join(u["name"] for u in uniques(civ)
                          if u["kind"] == "юнит" and u.get("era") in (era, era - 1) and u.get("combat"))
        mil_rank = _rank([r.get("military", 0) for r in rs], s.get("military", 0))
        msg = f"Сейчас ваше окно силы ({ERA_NAMES.get(era, era)}): {names}."
        if mil_rank > 1:
            warns.append(("yellow", msg + f" Но по армии вы {mil_rank}-й — стройте уникальные юниты и используйте окно."))
        else:
            warns.append(("green", msg + " Вы сильнейшие по армии — лучшее время для атаки."))
    else:
        nxt = [u for u in uniques(civ) if u.get("era") is not None and u["era"] > era]
        if nxt:
            u = min(nxt, key=lambda u: u["era"])
            warns.append(("green", f"Следующий пик: {u['name']} — {u['eraName']}, изучите «{u['tech']}»."))
        elif spikes and era > max(spikes):
            warns.append(("yellow", "Окна уникальных юнитов позади — выигрывайте за счёт экономики и фокуса цивилизации."))

    # --- scale ---
    sc = game_scale(data)
    cities = s.get("cities", 0)
    std_t = t / sc["speed"]                     # this turn expressed at standard speed
    base = 2 if std_t < 40 else 3 if std_t < 80 else 4
    expect = max(1, round(base * sc["land"]))   # more land per player — more cities expected
    if std_t >= 30 and cities < expect:
        avg = sum(r.get("cities", 0) for r in rs) / len(rs) if rs else 0
        warns.append(("red" if cities < expect - 1 else "yellow",
                      f"Мало городов: {cities:g} на ходу {t} (ориентир ≥{expect}, у соперников в среднем {avg:.1f}). Нужны поселенцы."))
    if s.get("starvingCities", 0) > 0:
        warns.append(("yellow", f"Голодают города: {s['starvingCities']:g}. Переназначьте жителей на еду."))

    # --- military ---
    if rs:
        strongest = max(rs, key=lambda r: r.get("military", 0))
        top = strongest.get("military", 0)
        ratio = s.get("military", 0) / top if top else 1
        if ratio < 0.3:
            warns.append(("red", (f"Армия в {1/ratio:.0f}× слабее сильнейшего соседа" if ratio > 0.05 else "Армии почти нет") + " — высокий риск нападения. Стройте оборону и стены."))
        elif ratio < 0.6:
            warns.append(("yellow", f"Армия {ratio:.0%} от сильнейшего соседа. Подтяните оборону."))

    # --- economy / stability ---
    gpt, gold = s.get("goldRate", 0), s.get("gold", 0)
    if gpt < 0:
        lvl = "red" if gold + gpt * 10 < 0 else "yellow"
        warns.append((lvl, f"Доход {gpt:g}/ход (в казне {gold:g}). При нуле в казне распускаются юниты — стройте рынки, торговые пути, распустите лишнее."))
    hap = s.get("happiness", 0)
    if hap < -10:
        warns.append(("red", f"Довольство {hap:g}: бунты и остановка роста. Срочно роскошь, Колизеи, религия."))
    elif hap < 0:
        warns.append(("yellow", f"Довольство {hap:g}: рост замедлен. Нужна роскошь или здания довольства."))

    # --- science pace ---
    if rs:
        sci_rank = _rank([r.get("science", 0) for r in rs], s.get("science", 0))
        if sci_rank > (len(rs) + 1) / 2 + 0.5:
            warns.append(("yellow", f"Наука: {sci_rank}-е место из {len(rs) + 1}. Библиотеки, рост населения, торговые пути."))

    # --- trends and weak spots from the metric tree ---
    if me in idx and idx[me]:
        tlist = sorted(idx[me])
        now = idx[me][tlist[-1]]
        window = turns(10, sc)
        past_t = [x for x in tlist if x <= tlist[-1] - window]
        if past_t:
            past = idx[me][past_t[-1]]
            drop = past.get("overall", 0) - now.get("overall", 0)
            if drop > 12:
                warns.append(("red", f"Общий индекс упал на {drop:.0f} за {window} ходов — вы быстро отстаёте."))
            losers = sorted(((past.get(g.key, 0) - now.get(g.key, 0), g.label) for g in TREE.children), reverse=True)
            if losers and losers[0][0] > 15:
                warns.append(("yellow", f"Сильнее всего просела группа «{losers[0][1]}» (−{losers[0][0]:.0f} за {window} ходов)."))
        groups = [(now.get(g.key), g.label) for g in TREE.children if g.key in now]
        if groups:
            weak = min(groups)
            warns.append(("yellow" if weak[0] < 30 else "green", f"Слабейшее направление: «{weak[1]}» (индекс {weak[0]:.0f})."))

    # --- neighbours ---
    for rv in rivals(data, idx, pids):
        level, role = rival_role(rv)
        if level == "red":
            where = f"в {rv['dist']} клетках" if rv["dist"] is not None else ""
            warns.append(("red", f"{rv['name']} {where}: {role} (армия ×{rv['mil_ratio']:.1f} от вашей)."))

    if not any(lvl == "red" for lvl, _ in warns):
        warns.append(("green", "Красных сигналов нет."))
    order = {"red": 0, "yellow": 1, "green": 2}
    warns.sort(key=lambda w: order[w[0]])
    return prof, warns
