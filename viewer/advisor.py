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
    rivals = [p for p in pids if p != me and t in data.series[p]]
    rs = [data.series[p][t] for p in rivals]
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
    cities = s.get("cities", 0)
    expect = 2 if t < 40 else 3 if t < 80 else 4
    if t >= 30 and cities < expect:
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
        turns = sorted(idx[me])
        now = idx[me][turns[-1]]
        past_t = [x for x in turns if x <= turns[-1] - 10]
        if past_t:
            past = idx[me][past_t[-1]]
            drop = past.get("overall", 0) - now.get("overall", 0)
            if drop > 12:
                warns.append(("red", f"Общий индекс упал на {drop:.0f} за 10 ходов — вы быстро отстаёте."))
            losers = sorted(((past.get(g.key, 0) - now.get(g.key, 0), g.label) for g in TREE.children), reverse=True)
            if losers and losers[0][0] > 15:
                warns.append(("yellow", f"Сильнее всего просела группа «{losers[0][1]}» (−{losers[0][0]:.0f} за 10 ходов)."))
        groups = [(now.get(g.key), g.label) for g in TREE.children if g.key in now]
        if groups:
            weak = min(groups)
            warns.append(("yellow" if weak[0] < 30 else "green", f"Слабейшее направление: «{weak[1]}» (индекс {weak[0]:.0f})."))

    if not any(lvl == "red" for lvl, _ in warns):
        warns.append(("green", "Красных сигналов нет."))
    order = {"red": 0, "yellow": 1, "green": 2}
    warns.sort(key=lambda w: order[w[0]])
    return prof, warns
