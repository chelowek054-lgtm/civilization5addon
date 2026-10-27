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

- **Metric tree** — all stats are normalized to a 0–100 index (0 = worst civ, 100 = best)
  and grouped: *Overall strength → 8 groups (scale, economy, science, culture,
  faith, stability, military, score) → subgroups → raw stats*. Select any node to
  see it per turn for every civ, plus what your own index is made of.
- **Dashboard**, single-metric graphs and a summary table.
- **Overlay mode** — always on top, adjustable transparency, compact side panel.
- **Automatic game archive** — every game is saved to `saves/` while the viewer runs.
- **Game history** — pick any saved game from the *Игра* (Game) list to analyse it;
  the current game keeps being recorded in the background.
- Civs you haven't met are hidden by default.

### Requirements

- Civilization V with **Brave New World** (Windows, or Linux: native port or Proton)
- Python 3.10+ with `matplotlib` and `tkinter`

### Installation — Windows

1. Install Python dependencies:

   ```bash
   pip install matplotlib
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

1. Install Python dependencies:

   ```bash
   sudo apt install python3-tk python3-matplotlib
   ```

   (Fedora: `sudo dnf install python3-tkinter python3-matplotlib`,
   Arch: `sudo pacman -S tk python-matplotlib`.)

2. Start the game once (so `config.ini` exists), close it, then install the logger:

   ```bash
   chmod +x install.sh run_viewer.sh
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
python viewer/civstats.py saves/<file>.log
```

### Project layout

| Path | What |
|---|---|
| `game/UI/CivStatsLogger.lua` | In-game logger (one `CIVSTATS|…` line per civ per turn) |
| `viewer/civstats.py` | Viewer window, log reader, game archive |
| `viewer/metrics_tree.py` | Metric tree and index calculation |
| `install.ps1`, `install.sh` | Installer / uninstaller (Windows / Linux) |
| `run_viewer.bat`, `run_viewer.sh` | Viewer launchers (Windows / Linux) |

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

- **Дерево показателей** — все показатели приводятся к индексу 0–100
  (0 — худшая цивилизация, 100 — лучшая) и группируются: *Общая сила → 8 групп
  (масштаб, экономика, наука, культура, вера, стабильность, армия, счёт) →
  подгруппы → сырые значения*. Выберите любой узел, чтобы увидеть его по ходам для
  всех цивилизаций и из чего складывается ваш индекс.
- **Панель**, графики по отдельным показателям и сводная таблица.
- **Режим поверх игры** — поверх всех окон, настраиваемая прозрачность, компактная колонка.
- **Автосохранение партий** — пока открыта программа, каждая игра сохраняется в `saves/`.
- **История игр** — выберите любую сохранённую партию в списке *Игра*, текущая
  при этом продолжает записываться в фоне.
- Цивилизации, которых вы ещё не встретили, по умолчанию скрыты.

### Требования

- Civilization V с **Brave New World** (Windows или Linux: нативная версия или Proton)
- Python 3.10+ с `matplotlib` и `tkinter`

### Установка — Windows

1. Установите зависимости Python:

   ```bash
   pip install matplotlib
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

1. Установите зависимости Python:

   ```bash
   sudo apt install python3-tk python3-matplotlib
   ```

   (Fedora: `sudo dnf install python3-tkinter python3-matplotlib`,
   Arch: `sudo pacman -S tk python-matplotlib`.)

2. Запустите игру один раз (чтобы появился `config.ini`), закройте её и установите логгер:

   ```bash
   chmod +x install.sh run_viewer.sh
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
python viewer/civstats.py saves/<файл>.log
```

### Структура проекта

| Путь | Что это |
|---|---|
| `game/UI/CivStatsLogger.lua` | Логгер в игре (одна строка `CIVSTATS|…` на цивилизацию за ход) |
| `viewer/civstats.py` | Окно программы, чтение лога, архив партий |
| `viewer/metrics_tree.py` | Дерево показателей и расчёт индексов |
| `install.ps1`, `install.sh` | Установка / удаление (Windows / Linux) |
| `run_viewer.bat`, `run_viewer.sh` | Запуск программы (Windows / Linux) |

### Примечания

- Если какого-то метода API нет в вашей версии игры, показатель записывается как `0`
  и не участвует в индексах.
- Технически логгер видит и скрытые данные соперников; программа показывает только
  встреченные цивилизации, если не отмечена соответствующая галочка.
