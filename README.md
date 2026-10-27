# Civ 5 Stats

[English](#english) · [Русский](#русский)

---

## English

Live graphs and strategy analysis for **Sid Meier's Civilization V: Brave New World**.

A small in-game logger writes ~90 stats for every major civilization each turn to
`Lua.log`; a desktop viewer reads that log and draws the graphs in a separate
window that can stay on top of the game.

The logger only *reads* game state, so it is safe in **multiplayer**: no desyncs,
and other players don't need to install it.

### Features

- **Compact overlay** (Dear PyGui, `run_viewer`) — a small always-on-top panel on the left edge under the science panel: one graph (overall strength of every civ, you in bold), the must-watch numbers with your rank (strength, science, gold, army vs. strongest rival, happiness, cities, era / power spike) and a one-line tip. Click any number or `+` to open the full analysis window on that branch; drag it by the title row; `o` cycles transparency.
- **Full analysis window** (`run_analysis`) — everything below.
- **Advisor** (default view) — red/yellow/green warnings while you play (too few cities, weak army vs. strongest neighbour, negative gold, unhappiness, falling behind in science, sharp drops in the metric tree), your civ's trait and unique units/buildings with the era and tech that unlock them, and its power-spike windows on an era timeline. Civ data is read from the game's own database: `python tools/extract_civ_data.py` (re-run after DLC or game updates).
- **Metric tree** — all stats are normalized to a 0–100 index (0 = worst civ, 100 = best)
  and grouped: *Overall strength → 8 groups (scale, economy, science, culture,
  faith, stability, military, score) → subgroups → raw stats*. Select any node to
  see it per turn for every civ, plus what your own index is made of.
- **Dashboard**, single-metric graphs and a summary table.
- **Turn slider** — replay your game: graphs, tree, table and advisor show the state on any past turn (◀ ▶ step a turn, *Последний* returns to the latest).
- **Automatic game archive** — every game is saved to `saves/` while the viewer runs.
- **Game history** — pick any saved game from the *Игра* (Game) list to analyse it;
  the current game keeps being recorded in the background.
- Civs you haven't met are hidden by default.

### Reading the overlay

| Element | Meaning |
|---|---|
| **Title** `Civ 5 · ход N` | Current turn. Drag the window by this row. |
| `o` · `+` · `x` | Transparency (88% → 70% → opaque) · open the full analysis window · close. |
| **Graph** | Overall strength of every civ you have met, turn by turn. The index is 0–100: 100 = best of the visible civs, 0 = worst. Your line is the thick one; the line under the graph names the current leader in its colour. A falling line means you are falling behind even if your own numbers grow. |
| **Общая сила** (Strength) | Your overall index now and your place (`6/6` = last of six). |
| **Наука/ход** (Science) | Science per turn and your place. |
| **Золото/ход** (Gold) | Net gold per turn, treasury in brackets, your place. Red when the income is negative. |
| **Армия** (Army) | Your military strength as a share of the strongest rival. Red below 30%, yellow below 60%. |
| **Довольство** (Happiness) | Empire happiness. Yellow below 0 (slower growth), red below −10 (unrest). |
| **Города** (Cities) | Your cities, rivals' average in brackets. |
| **Эпоха** (Era) | Current era; **ПИК** means your civ's unique units are in their power window right now. |
| **Bottom line** | The single most urgent tip from the advisor (red = act now, yellow = watch, green = all fine). |

Colours: green = first place / healthy, yellow = risk, red = last place / problem, white = in between.
Click any row label to open the full window on that branch of the metric tree (Era opens the advisor).
### Requirements

- Civilization V with **Brave New World** (Windows, or Linux: native port or Proton)
- Python 3.10+ with `tkinter`; other dependencies (`matplotlib`, `dearpygui`) are installed into the project's `.venv` by `setup.bat` / `setup.sh` (Fedora: `sudo dnf install python3-tkinter`, Arch: `sudo pacman -S tk`). The launchers use `.venv` automatically and fall back to the system Python if it is missing.

### Installation — Windows

1. Create the project's virtual environment `.venv` and install the dependencies from `requirements.txt` (double-click `setup.bat` or run):

   ```bash
   setup.bat
   ```

2. Install the logger into the game and enable Lua logging:

   ```bash
   powershell -ExecutionPolicy Bypass -File install.ps1
   ```

   If the game is not in the default location, pass it explicitly:

   ```bash
   powershell -ExecutionPolicy Bypass -File install.ps1 -GameDir "C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization V"
   ```

3. **Fully restart** Civilization V and start or load a game.
4. Run the viewer: double-click `run_viewer.bat`.

Uninstall: `powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall`

### Installation — Linux

Works with the native Linux port and with Proton; the script finds the game in the
usual Steam folders (including Flatpak Steam).

1. Install tkinter and venv from the system, then create `.venv` with the dependencies:

   ```bash
   sudo apt install python3-tk python3-venv
   chmod +x setup.sh install.sh run_viewer.sh run_analysis.sh
   ./setup.sh
   ```

2. Start the game once (so `config.ini` exists), close it, then install the logger:

   ```bash
   ./install.sh
   ```

   Custom locations:

   ```bash
   ./install.sh --game-dir "/path/to/Sid Meier's Civilization V" --user-dir "/path/to/folder/with/config.ini"
   ```

3. **Fully restart** Civilization V and start or load a game.
4. Run the viewer:

   ```bash
   ./run_viewer.sh
   ```

   If it says `Lua.log` is not found, point it to the log:

   ```bash
   CIVSTATS_LOG="/path/to/Logs/Lua.log" ./run_viewer.sh
   ```

Uninstall: `./install.sh --uninstall`

Where things live on Linux:

| | Native port | Proton |
|---|---|---|
| `config.ini`, `Logs/Lua.log` | `~/.local/share/Aspyr/Sid Meier's Civilization 5/` | `<Steam>/steamapps/compatdata/8930/pfx/drive_c/users/steamuser/Documents/My Games/Sid Meier's Civilization 5/` |

### What the installer changes

- copies `CivStatsLogger.lua/.xml` into the Brave New World `UI/InGame` folder;
- adds one `<LuaContext>` line to that folder's `InGame.xml`
  (the original is kept as `InGame.xml.civstats-backup`);
- sets `LoggingEnabled = 1` in `config.ini`.

Steam updates or "Verify integrity of game files" restore the original `InGame.xml` —
run the installer again.

### Overlay

To see the game behind the viewer, run Civ 5 in **windowed / borderless** mode;
exclusive fullscreen draws over every other window. On Linux, transparency needs
a compositing window manager.

### Viewing a recorded game

Choose it in the *Игра* (Game) drop-down at the top of the window (newest first,
`▶ Текущая игра` is the live game). You can also pass a file from `saves/`:

```bash
run_analysis.bat saves/<file>.log
```

### Project layout

| Path | What |
|---|---|
| `game/UI/CivStatsLogger.lua` | In-game logger (one `CIVSTATS|…` line per civ per turn) |
| `viewer/civstats.py` | Viewer window, log reader, game archive |
| `viewer/metrics_tree.py` | Metric tree and index calculation |
| `requirements.txt`, `setup.bat`, `setup.sh` | Python dependencies and `.venv` setup |
| `install.ps1`, `install.sh` | Installer / uninstaller (Windows / Linux) |
| `run_viewer.bat`, `run_viewer.sh` | Overlay launchers (Windows / Linux) |
| `run_analysis.bat`, `run_analysis.sh` | Full analysis window launchers |
| `viewer/overlay.py` | Compact Dear PyGui overlay |

### Notes

- If a stat's API method doesn't exist in your game version it logs `0` and is
  left out of the indices.
- The logger can technically read rivals' data that the normal UI hides; the
  viewer shows only civs you have met unless you tick the checkbox.

---

## Русский

Графики в реальном времени и анализ стратегии для **Sid Meier's Civilization V: Brave New World**.

Небольшой логгер внутри игры каждый ход записывает в `Lua.log` около 90 показателей
всех крупных цивилизаций. Программа на компьютере читает этот лог и рисует графики
в отдельном окне, которое может висеть поверх игры.

Логгер только *читает* состояние игры, поэтому безопасен в **мультиплеере**:
рассинхрона нет, другим игрокам ставить его не нужно.

### Возможности

- **Компактная панель** (Dear PyGui, `run_viewer`) — маленькое окно поверх игры у левого края под панелью науки: один график (общая сила всех цивилизаций, вы — толстой линией), обязательные показатели с вашим местом (сила, наука, золото, армия против сильнейшего, довольство, города, эпоха / пик) и совет в одну строку. Клик по показателю или `+` открывает подробное окно сразу на этой ветке; перетаскивается за заголовок; `o` меняет прозрачность.
- **Подробное окно** (`run_analysis`) — всё, что ниже.
- **Советник** (вид по умолчанию) — красные, жёлтые и зелёные предупреждения во время игры (мало городов, армия слабее сильнейшего соседа, отрицательный доход, недовольство, отставание в науке, резкие падения в дереве показателей), особенность вашей цивилизации, уникальные юниты и здания с эпохой и технологией открытия и окна силы на шкале эпох. Данные о цивилизациях берутся из базы самой игры: `python tools/extract_civ_data.py` (перезапустите после обновлений игры или DLC).
- **Дерево показателей** — все показатели приводятся к индексу 0–100
  (0 — худшая цивилизация, 100 — лучшая) и группируются: *Общая сила → 8 групп
  (масштаб, экономика, наука, культура, вера, стабильность, армия, счёт) →
  подгруппы → сырые значения*. Выберите любой узел, чтобы увидеть его по ходам для
  всех цивилизаций и из чего складывается ваш индекс.
- **Панель**, графики по отдельным показателям и сводная таблица.
- **Ползунок ходов** — пересмотр партии: графики, дерево, таблица и советник показывают состояние на любом прошлом ходу (◀ ▶ — шаг на ход, «Последний» — вернуться к текущему).
- **Автосохранение партий** — пока открыта программа, каждая игра сохраняется в `saves/`.
- **История игр** — выберите любую сохранённую партию в списке *Игра*, текущая
  при этом продолжает записываться в фоне.
- Цивилизации, которых вы ещё не встретили, по умолчанию скрыты.

### Как читать панель

| Элемент | Что значит |
|---|---|
| **Заголовок** `Civ 5 · ход N` | Текущий ход. За эту строку окно перетаскивается. |
| `o` · `+` · `x` | Прозрачность (88% → 70% → без прозрачности) · открыть подробное окно · закрыть. |
| **График** | Общая сила всех встреченных цивилизаций по ходам. Индекс 0–100: 100 — лучший среди видимых, 0 — худший. Ваша линия — толстая; строка под графиком называет текущего лидера его цветом. Падающая линия значит, что вы отстаёте, даже если ваши цифры растут. |
| **Общая сила** | Ваш общий индекс сейчас и место (`6/6` — последний из шести). |
| **Наука/ход** | Наука за ход и ваше место. |
| **Золото/ход** | Чистый доход за ход, в скобках — казна, ваше место. Красным — если доход отрицательный. |
| **Армия** | Ваша военная мощь в процентах от сильнейшего соперника. Красным — меньше 30%, жёлтым — меньше 60%. |
| **Довольство** | Довольство империи. Жёлтым — меньше 0 (рост замедлен), красным — меньше −10 (бунты). |
| **Города** | Число ваших городов, в скобках — среднее у соперников. |
| **Эпоха** | Текущая эпоха; **ПИК** — сейчас окно силы уникальных юнитов вашей цивилизации. |
| **Нижняя строка** | Самый срочный совет советника (красный — действовать сейчас, жёлтый — следить, зелёный — всё в порядке). |

Цвета: зелёный — первое место или всё хорошо, жёлтый — риск, красный — последнее место или проблема, белый — между ними.
Клик по названию строки открывает подробное окно на этой ветке дерева показателей («Эпоха» открывает советника).
### Требования

- Civilization V с **Brave New World** (Windows или Linux: нативная версия или Proton)
- Python 3.10+ с `tkinter`; остальные зависимости (`matplotlib`, `dearpygui`) ставятся в окружение проекта `.venv` через `setup.bat` / `setup.sh` (Fedora: `sudo dnf install python3-tkinter`, Arch: `sudo pacman -S tk`). Скрипты запуска сами используют `.venv`, а если его нет — системный Python.

### Установка — Windows

1. Создайте виртуальное окружение проекта `.venv` и установите зависимости из `requirements.txt` (двойной клик по `setup.bat` или команда):

   ```bash
   setup.bat
   ```

2. Установите логгер в игру и включите Lua-логирование:

   ```bash
   powershell -ExecutionPolicy Bypass -File install.ps1
   ```

   Если игра стоит не по стандартному пути, укажите его:

   ```bash
   powershell -ExecutionPolicy Bypass -File install.ps1 -GameDir "C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization V"
   ```

3. **Полностью перезапустите** Civilization V и начните или загрузите партию.
4. Запустите программу: двойной клик по `run_viewer.bat`.

Удаление: `powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall`

### Установка — Linux

Работает с нативной Linux-версией и с Proton. Скрипт сам ищет игру в обычных папках
Steam (включая Steam из Flatpak).

1. Установите tkinter и venv из системы, затем создайте `.venv` с зависимостями:

   ```bash
   sudo apt install python3-tk python3-venv
   chmod +x setup.sh install.sh run_viewer.sh run_analysis.sh
   ./setup.sh
   ```

2. Запустите игру один раз (чтобы появился `config.ini`), закройте её и установите логгер:

   ```bash
   ./install.sh
   ```

   Если пути нестандартные:

   ```bash
   ./install.sh --game-dir "/путь/к/Sid Meier's Civilization V" --user-dir "/путь/к/папке/с/config.ini"
   ```

3. **Полностью перезапустите** Civilization V и начните или загрузите партию.
4. Запустите программу:

   ```bash
   ./run_viewer.sh
   ```

   Если программа пишет, что `Lua.log` не найден, укажите путь к нему:

   ```bash
   CIVSTATS_LOG="/путь/к/Logs/Lua.log" ./run_viewer.sh
   ```

Удаление: `./install.sh --uninstall`

Где лежат файлы на Linux:

| | Нативная версия | Proton |
|---|---|---|
| `config.ini`, `Logs/Lua.log` | `~/.local/share/Aspyr/Sid Meier's Civilization 5/` | `<Steam>/steamapps/compatdata/8930/pfx/drive_c/users/steamuser/Documents/My Games/Sid Meier's Civilization 5/` |

### Что меняет установщик

- копирует `CivStatsLogger.lua/.xml` в папку `UI/InGame` дополнения Brave New World;
- добавляет одну строку `<LuaContext>` в `InGame.xml` этой папки
  (оригинал сохраняется как `InGame.xml.civstats-backup`);
- ставит `LoggingEnabled = 1` в `config.ini`.

Обновление игры в Steam или «Проверка целостности файлов» возвращают оригинальный
`InGame.xml` — запустите установщик ещё раз.

### Окно поверх игры

Чтобы окно было видно поверх игры, запускайте Civ 5 в **оконном / безрамочном** режиме:
в эксклюзивном полноэкранном режиме игра перекрывает все окна. На Linux для
прозрачности нужен композитный оконный менеджер.

### Просмотр сохранённой партии

Выберите её в списке *Игра* вверху окна (новые сверху, `▶ Текущая игра` — живые
данные). Можно также передать файл из `saves/`:

```bash
run_analysis.bat saves/<файл>.log
```

### Структура проекта

| Путь | Что это |
|---|---|
| `game/UI/CivStatsLogger.lua` | Логгер в игре (одна строка `CIVSTATS|…` на цивилизацию за ход) |
| `viewer/civstats.py` | Окно программы, чтение лога, архив партий |
| `viewer/metrics_tree.py` | Дерево показателей и расчёт индексов |
| `requirements.txt`, `setup.bat`, `setup.sh` | Зависимости Python и создание `.venv` |
| `install.ps1`, `install.sh` | Установка / удаление (Windows / Linux) |
| `run_viewer.bat`, `run_viewer.sh` | Запуск компактной панели (Windows / Linux) |
| `run_analysis.bat`, `run_analysis.sh` | Запуск подробного окна |
| `viewer/overlay.py` | Компактная панель на Dear PyGui |

### Примечания

- Если какого-то метода API нет в вашей версии игры, показатель записывается как `0`
  и не участвует в индексах.
- Технически логгер видит и скрытые данные соперников; программа показывает только
  встреченные цивилизации, если не отмечена соответствующая галочка.
