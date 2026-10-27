"""Groups all logged stats into a tree of indices.

Every leaf is a raw stat. Its index for a civ on a turn places it between the
worst (0) and the best (100) civ in view that turn; inverted stats like
unhappiness score 100 for the lowest value. A group's index is the mean of its children's
indices, so the root shows one "overall strength" line and each level down
explains where it comes from.
"""


class Node:
    def __init__(self, key, label, children=(), invert=False, weight=1.0):
        self.key = key
        self.label = label
        self.children = list(children)
        self.invert = invert
        self.weight = weight

    @property
    def is_leaf(self):
        return not self.children

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()


def G(key, label, *children, weight=1.0):
    return Node(key, label, children, weight=weight)


def L(key, label, invert=False, weight=1.0):
    return Node(key, label, invert=invert, weight=weight)


TREE = G("overall", "Общая сила",
    G("g_scale", "Масштаб империи",
        L("cities", "Города"),
        L("population", "Население"),
        L("land", "Территория"),
        L("foodSurplus", "Излишек еды"),
        L("starvingCities", "Голодающие города", invert=True, weight=0.5),
    ),
    G("g_economy", "Экономика",
        G("g_econ_flow", "Поток золота",
            L("goldRate", "Чистый доход/ход", weight=2),
            L("CalculateGrossGold", "Валовой доход"),
            L("GetGoldFromCities", "Золото из городов"),
            L("GetGoldPerTurnFromTradeRoutes", "Золото от торговли"),
            L("GetCityConnectionGold", "Дороги между городами"),
            L("GetGoldPerTurnFromDiplomacy", "Золото от дипломатии"),
        ),
        G("g_econ_costs", "Расходы",
            L("CalculateUnitCost", "Содержание юнитов", invert=True),
            L("GetBuildingGoldMaintenance", "Содержание зданий", invert=True),
            L("GetImprovementGoldMaintenance", "Содержание улучшений", invert=True),
        ),
        L("gold", "Казна"),
        L("production", "Производство/ход", weight=2),
        L("GetNumInternationalTradeRoutesUsed", "Торговые пути"),
    ),
    G("g_science", "Наука",
        L("science", "Наука/ход", weight=2),
        L("techs", "Технологии", weight=2),
        L("GetCurrentEra", "Эра"),
        G("g_sci_src", "Источники науки",
            L("GetScienceFromCities", "Из городов"),
            L("GetScienceFromOtherPlayers", "От других игроков"),
            L("GetScienceFromHappiness", "От довольства"),
            L("GetScienceFromResearchAgreements", "Научные договоры"),
            L("GetScienceFromBudgetDeficit", "Потери от дефицита"),
        ),
    ),
    G("g_culture", "Культура и туризм",
        L("culture", "Культура/ход", weight=2),
        L("policies", "Политики", weight=2),
        L("GetJONSCultureEverGenerated", "Культура за игру"),
        L("tourism", "Туризм", weight=2),
        L("GetNumGreatWorks", "Великие произведения"),
        L("GetNumWorldWonders", "Чудеса света"),
        L("GetNumPolicyBranchesFinished", "Завершённые ветки"),
    ),
    G("g_faith", "Вера",
        L("faith", "Вера/ход", weight=2),
        L("GetFaith", "Накоплено веры"),
        L("GetFaithPerTurnFromCities", "Из городов"),
        L("GetFaithPerTurnFromReligion", "От религии"),
    ),
    G("g_stability", "Стабильность",
        L("happiness", "Избыток довольства", weight=2),
        G("g_happy_src", "Источники довольства",
            L("GetHappinessFromLuxury", "Роскошь"),
            L("GetHappinessFromBuildings", "Здания"),
            L("GetHappinessFromPolicies", "Политики"),
            L("GetHappinessFromReligion", "Религия"),
            L("GetHappinessFromMinorCivs", "Города-государства"),
            L("GetHappinessFromNaturalWonders", "Природные чудеса"),
        ),
        G("g_unhappy_src", "Источники недовольства",
            L("GetUnhappinessFromCityCount", "Число городов", invert=True),
            L("GetUnhappinessFromCityPopulation", "Население", invert=True),
            L("GetUnhappinessFromOccupiedCities", "Захваченные города", invert=True),
            L("GetUnhappinessFromPublicOpinion", "Общественное мнение", invert=True),
        ),
        L("GetGoldenAgeTurns", "Ходы золотого века"),
    ),
    G("g_military", "Армия",
        L("military", "Военная мощь", weight=3),
        L("units", "Юниты"),
        L("GetNumUnitsOutOfSupply", "Сверх лимита снабжения", invert=True),
        L("GetLifetimeCombatExperience", "Боевой опыт"),
        L("GetWarmongerThreat", "Угроза агрессора", invert=True, weight=0.5),
    ),
    G("g_score", "Состав счёта",
        L("score", "Счёт", weight=2),
        L("GetScoreFromCities", "За города"),
        L("GetScoreFromPopulation", "За население"),
        L("GetScoreFromLand", "За землю"),
        L("GetScoreFromWonders", "За чудеса"),
        L("GetScoreFromTechs", "За технологии"),
        L("GetScoreFromPolicies", "За политики"),
        L("GetScoreFromGreatWorks", "За произведения"),
        L("GetScoreFromReligion", "За религию"),
    ),
)

NODES = {n.key: n for n in TREE.walk()}
PARENT = {c.key: n.key for n in TREE.walk() for c in n.children}


def compute_indices(series, pids):
    """series: pid -> {turn: stats}. Returns pid -> {turn: {node_key: index 0..100}}.

    Leaves that nobody has logged (old logs, missing API) are left out of
    their group so they do not drag averages down.
    """
    turns = sorted({t for p in pids for t in series[p]})
    out = {p: {} for p in pids}
    for t in turns:
        present = [p for p in pids if t in series[p]]
        idx = {p: {} for p in present}
        _fill(TREE, t, present, series, idx)
        for p in present:
            out[p][t] = idx[p]
    return out


def _fill(node, t, pids, series, idx):
    """Writes node index into idx[pid][node.key]; returns False if no data."""
    if node.is_leaf:
        vals = {p: series[p][t].get(node.key) for p in pids}
        if all(v is None for v in vals.values()):
            return False
        nums = [v for v in vals.values() if v is not None]
        hi, lo = max(nums), min(nums)
        for p, v in vals.items():
            v = lo if v is None else v
            if hi == lo:
                score = 50.0
            elif node.invert:
                score = 100.0 * (hi - v) / (hi - lo)
            else:
                score = 100.0 * (v - lo) / (hi - lo)
            idx[p][node.key] = score
        return True
    used = [c for c in node.children if _fill(c, t, pids, series, idx)]
    if not used:
        return False
    total_w = sum(c.weight for c in used)
    for p in pids:
        idx[p][node.key] = sum(idx[p][c.key] * c.weight for c in used) / total_w
    return True
