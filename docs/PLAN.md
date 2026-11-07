# Animated Cursor Setup (`anicursor`): Project Plan and Process Log

> **How to use this file with any AI:** paste the whole file at the start of a new chat, then say which phase or task you are on. Update the checkboxes, the "Current status" section, the "Decision log" and the "Changelog" after each work session, so the next AI has accurate context.

**Plan version:** 1.1 (architecture locked; progress updated)
**Last updated:** 2026-11-06

---

## 1. Project summary

A lightweight Ubuntu desktop utility (installer/setup tool) that makes installing animated Windows cursor packs (`.ani` / `.cur`) fast. The user types one command, a window opens, they browse to a cursor folder, the tool converts the files, the user maps each converted cursor to a role (normal pointer, link, loading, text, resize...) while seeing a live animated preview, and the tool installs and applies the theme.

**Origin:** a manual setup guide for "The Herta Cursor ver.2.0.0" on Ubuntu. That manual process (convert with `win2xcur`, build `index.theme`, create many symlinks, run `gsettings`) is tedious and hardcoded to one pack. The tool generalizes it.

**Learning goals:** the user is new to Bash and somewhat familiar with Python. The project doubles as a way to learn Bash (launcher and system scripts) while Python handles the core logic.

**Naming vocabulary:** "utility" or "installer" for the whole product, "app" for the GTK window, "tool" for the command line side.

---

## 2. Names

| Item | Value |
|---|---|
| Display name | Animated Cursor Setup |
| Command | `anicursor` |
| Project folder | `anicursor/` (e.g. `~/Documents/Side_Project/anicursor`) |
| Python package | `anicursor` |

The display name (with spaces) appears only in the GUI title, README and `.desktop` file.

---

## 3. Verified environment (baseline)

| Item | Value | Status |
|---|---|---|
| OS | Ubuntu 26.04 LTS | Target |
| Python | 3.14.4 | Verified on the user's machine |
| GNOME Shell | 50.1 | Verified on the user's machine |
| Session | Wayland (`echo $XDG_SESSION_TYPE` printed `wayland`) | Verified |
| GUI toolkit | GTK 4 via apt packages `python3-gi`, `gir1.2-gtk-4.0` | Planned |
| Install scope | Per-user, no root | Planned |
| Theme location | `~/.local/share/icons/THEME_NAME/` | Planned |

**Rules that follow from this baseline**
- Install PyGObject through **apt**, not pip, so it matches the system Python 3.14.
- `win2xcur` is installed with **pipx** (isolated environment). The tool calls it as a **command** via `subprocess`; it cannot be imported from system Python.
- `~/.local/bin` (where pipx installs commands) may be missing from `PATH` in some contexts such as `.desktop` launches, so the **launcher** must add it.
- Do not assume X11-era cursor methods behave identically on Wayland. Test `gsettings` on the real session early (Phase 2).

---

## 4. Architecture

**Bash** (small, with clearly defined jobs):
- `bin/anicursor`: launcher (PATH fix, dependency check, error notification, starts Python)
- `scripts/check-dependencies.sh`: dependency checker (report only)
- `scripts/install.sh`, `scripts/uninstall.sh`: installation (Phase 7)

**Python** (all core logic and the GUI):
- Detect cursor files (Path A / Path B)
- Convert, map roles, build the theme
- Apply and restore settings
- GTK 4 GUI and live preview

**Avoid in Bash:** JSON parsing, GUI communication, cursor file parsing, mapping logic.

### Core logic: Path A / Path B

After the user selects a folder, check for `.ani` or `.cur` files.

- **Path A: raw files detected**
  1. Create `~/.local/share/icons/THEME_NAME/cursors`
  2. Run `win2xcur` to convert the `.ani` and `.cur` files into that folder
  3. Flatten any nested output folders
  4. Continue to mapping and symlink generation
- **Path B: already converted or pre-existing structure**
  1. Skip `win2xcur` entirely
  2. Tell the user (terminal message or GUI notice) that conversion was bypassed
  3. Continue to mapping and symlink generation
  4. Detect which kind of Path B: a finished theme (`cursors/` plus `index.theme`) or loose Xcursor files with no theme. Generate only what is missing.

### Launcher design (`bin/anicursor`)

Order of the file (Bash reads top to bottom, so functions must be defined before they are called):

1. Shebang and `set -euo pipefail`
2. Function definitions (`notify_error`, `check_path`)
3. **Call** `check_path` (a function does nothing until called). It must stay quiet.
4. Locate the project directory (use `readlink -f` so it still works through a symlink in `~/.local/bin`) and set `checker`
5. Dependency check:
   ```bash
   if ! output=$("$checker" 2>&1); then
       notify_error "$output"
       exit 1
   fi
   ```
   The `if !` form is required, because under `set -e` a bare failing command would end the launcher before `notify_error` runs.
6. `export PYTHONPATH="$PROJECT_DIR"`
7. `exec python3 -m anicursor "$@"`

`notify_error()` behavior: use `zenity --error --no-markup` when a graphical session (`WAYLAND_DISPLAY` or `DISPLAY`, read with `${VAR:-}`) and `zenity` exist; always also print to stderr when stderr is a terminal (`[ -t 2 ]`); append `|| true` so closing the dialog doesn't trip `set -e`; fall back to a generic message if the captured report is empty. It lives in the launcher for now; move it into a shared `scripts/lib.sh` only when `install.sh` needs it too.

### Dependency checker design (`scripts/check-dependencies.sh`)

**Done and tested.** Summary of the final design:
- **Report only, never installs.** Automatic installing is opt-in and belongs in `install.sh` (see decision log).
- Global lookup table `APT_PACKAGE` maps an item name to its apt package(s): `python3`, `gsettings` (`libglib2.0-bin`), `gtk4` (`python3-gi gir1.2-gtk-4.0`), `libmagickwand-dev`.
- `check_deps` owns local `commands` and `missing` arrays. `missing` holds the **table keys**, so there is no translation step.
- `win2xcur` is a special case (installed with pipx, not apt). `pipx` is **not** a required dependency; it is only suggested when `win2xcur` is missing and pipx itself is absent.
- `print_install` is a standalone function that takes the missing names as arguments (`print_install "${missing[@]}"`), reads only the global table, and prints the hints to stderr.
- Silent on success, exit `0`. On failure: a `Missing: ...` line, the install hints, a count message, exit `1`.
- Main call is wrapped in `if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then check_deps; fi`, so the file can be sourced to test functions without running the checks.
- Expects PATH to be prepared by the launcher. Running it directly may falsely report `win2xcur` missing.

---

## 5. Folder structure

```
anicursor/
├── bin/
│   └── anicursor              # Bash launcher
├── scripts/
│   ├── check-dependencies.sh
│   ├── install.sh
│   └── uninstall.sh
├── anicursor/                 # Python package
│   ├── __init__.py
│   ├── __main__.py            # enables: python3 -m anicursor
│   ├── cli.py
│   ├── detector.py
│   ├── converter.py
│   ├── mapper.py
│   ├── theme_builder.py
│   ├── settings.py
│   ├── validator.py
│   └── gui/
│       ├── __init__.py
│       ├── main_window.py
│       ├── mapping_view.py
│       └── preview.py
├── data/
│   └── cursor_roles.json
├── tests/
├── docs/
│   └── PLAN.md                # this file
├── .gitignore
├── README.md
└── pyproject.toml
```

`gui/` lives **inside** the Python package so imports are clean (`from anicursor.gui import ...`). Keep each module's interface small (functions take paths and return results), and keep all `subprocess` calls to external tools in one place, so a component such as `win2xcur` can be swapped later by touching one file.

---

## 6. Definition of "fully works"

Goal: works on most computers with the current setup.

**Supported environment (v1):** Ubuntu 26.04 LTS, GNOME, Wayland, GTK 4, system Python 3, per-user install.

**On a fresh Ubuntu 26.04 machine, a user can:**
- [ ] Run `anicursor` and get a clear message listing missing dependencies with exact install commands
- [ ] Select a folder of raw `.ani` / `.cur` files (Path A) and get a converted theme
- [ ] Select an already-converted folder (Path B) and see "conversion skipped"
- [ ] Map cursors to roles, with sensible auto-suggestions
- [ ] Install the theme to `~/.local/share/icons/`
- [ ] Apply it, and **restore the previous theme** with one command
- [ ] Hit bad input (empty folder, corrupt file, spaces in names) and get a clear error, not a crash

**Out of scope for v1:** other distros, X11-specific behavior, KDE, system-wide install (optional opt-in later), and `.ani` files that `win2xcur` itself cannot parse.

**Validation idea:** test the install on a second machine or fresh Ubuntu VM before calling Phase 7 done.

---

## 7. Phases and checklist

### Phase 0: Setup ✅ DONE
- [x] Choose tool name and command (`anicursor`)
- [x] Create folder structure
- [x] `git init`, `.gitignore`, first commit
- [x] Write the "fully works" definition into `docs/PLAN.md`
- [x] Confirm session type (Wayland)
- [x] Push the project to GitHub (remote `origin`)
- [x] Default branch is `main` (renamed from `master`)

### Phase 1: Bash and dependency check ⬅ CURRENT (branch `phase-1-bash`)
Goal: `bin/anicursor` runs `check-dependencies.sh`, which either passes silently or reports exactly what is missing and how to install it.

- [x] Practice Bash basics in a scratch file; run `shellcheck`
- [x] `check-dependencies.sh` Layer 1: command check, collecting all missing items
- [x] Layer 2: PATH fix (**moved to the launcher**, not in the checker)
- [x] Layer 3: GTK 4 import test
- [x] Layer 4: `libmagickwand-dev` check with `dpkg -s`
- [x] Layer 5: lookup table, install hints, report to stderr
- [x] Layer 6: exit `0` / `1`
- [x] Checker passes all test cases (see test recipes below) and `shellcheck`
- [x] Commit the checker
- [ ] `notify_error()` in `bin/anicursor` (zenity with stderr fallback)
- [ ] Launcher: call `check_path` quietly, locate project via `readlink -f`, run the checker with the `if ! output=$(...)` pattern, export `PYTHONPATH`, `exec python3 -m anicursor "$@"`
- [ ] Placeholder in `anicursor/__main__.py`: `print("anicursor starting")` (optionally print `sys.argv` to test argument forwarding)
- [ ] Launcher tests pass (below)
- [ ] `shellcheck bin/anicursor scripts/*.sh` reports no warnings
- [ ] Tick the boxes here, commit, merge `phase-1-bash` into `main`, then `git switch -c phase-2-python-core`

**Launcher tests**

| Scenario | Command | Expected |
|---|---|---|
| All present | `bin/anicursor; echo "exit: $?"` | `anicursor starting`, `exit: 0` |
| Called from elsewhere | `cd ~ && /path/to/anicursor/bin/anicursor` | Same output |
| Through a symlink | `ln -s "$PWD/bin/anicursor" /tmp/anicursor-link && /tmp/anicursor-link; rm /tmp/anicursor-link` | Same output (tests `readlink -f`) |
| Dependency missing, terminal | `( dpkg() { return 1; }; export -f dpkg; bin/anicursor; echo "exit: $?" )` | Report on the terminal, `exit: 1`, no "starting" |
| Dependency missing, graphical | Same command with `2>/dev/null` | A Zenity dialog appears |
| No graphical session | `env -u WAYLAND_DISPLAY -u DISPLAY bin/anicursor` with the fake `dpkg` | Falls back to stderr, no dialog |
| Arguments forwarded | `bin/anicursor --test` | Python receives `--test` |

Note: the launcher always re-adds `~/.local/bin`, so a restricted `PATH` no longer simulates a missing `win2xcur` through the launcher. Use the checker test recipes for that.

**Checker test recipes (none uninstall anything)**

Run from the project root. `PATH="$HOME/.local/bin:$PATH"` stands in for the launcher's PATH fix.

| # | Case | Trick | Expected |
|---|---|---|---|
| 1 | All present | `PATH="$HOME/.local/bin:$PATH" bash scripts/check-dependencies.sh; echo "exit: $?"` | No output, exit `0` |
| 2 | Fake command | `sed` a copy with `fakecmd` added to `commands`, run the copy from `/tmp` | Unknown-dependency warning, exit `1` |
| 3 | `win2xcur` missing | `env PATH=/usr/bin:/bin bash scripts/check-dependencies.sh` | pipx block, exit `1` |
| 4 | Library missing | Subshell with a fake `dpkg() { return 1; }` exported via `export -f dpkg` | apt block with `libmagickwand-dev`, no stray dpkg message |
| 5 | GTK missing | Subshell with a fake `python3() { return 1; }` exported | apt block with `python3-gi gir1.2-gtk-4.0` |
| 6 | Several missing | Combine fakes plus restricted PATH | One apt block, the pipx block, correct count |
| 7 | `pipx` and `win2xcur` both missing | Temp bin folder with symlinks to only `python3`, `gsettings`, `dpkg`; run with `env PATH="$d" /usr/bin/bash ...` | `pipx` in the apt line, then the pipx block with the `ensurepath` note |
| 8 | Report only | `bash -c 'source scripts/check-dependencies.sh; print_install python3 gtk4 win2xcur'` | Full hints, no system checks |

Always check the exit code as well as the output (`echo "exit: $?"`). Debug with `bash -x`; lint with `shellcheck`. Note that `bash -n` only checks syntax and misses runtime errors.

**Command / module to package lookup**

| Command / module | How to install on Ubuntu |
|---|---|
| `win2xcur` | `pipx install win2xcur` (not apt) |
| `python3` | `python3` |
| GTK bindings | `python3-gi`, `gir1.2-gtk-4.0` |
| ImageMagick library (needed by win2xcur) | `libmagickwand-dev` (a library: check with `dpkg -s`, not `command -v`) |
| `gsettings` | `libglib2.0-bin` |
| pipx | `pipx` (then `pipx ensurepath` and reopen the terminal) |

### Phase 2: Python CLI core (Milestone M1)
- [ ] Entry point (`__main__.py`, `cli.py`)
- [ ] `detector.py`: Path A (raw `.ani`/`.cur`) vs Path B (converted or finished theme)
- [ ] `converter.py`: run `win2xcur`, flatten nested output
- [ ] `theme_builder.py`: create `~/.local/share/icons/THEME_NAME/cursors`, create `index.theme` only if missing, generate symlinks
- [ ] `data/cursor_roles.json`: role to alias table
- [ ] `settings.py`: **save the current theme first**, apply with `gsettings`, provide a restore command
- [ ] Clear messages, including "conversion skipped" for Path B
- [ ] Test the Herta pack on both paths
- [ ] Verify `gsettings` works on the real Wayland session

**M1 done when:** one terminal command sets up Herta and one command undoes it.

### Phase 3: Mapping logic (still CLI)
- [ ] JSON mapping format (role to filename)
- [ ] `mapper.py`: auto-suggest from filename keywords (`normal` to `left_ptr`, `link` to `pointer`, `load`/`busy` to `watch`)
- [ ] Save and reload mappings
- [ ] `validator.py`: warn about missing core roles (normal, link, text, loading)

### Phase 4: GTK 4 GUI shell
- [ ] Learn window, button, signal handler basics
- [ ] Folder chooser dialog
- [ ] Theme name entry and size selector
- [ ] Connect to the Python core (call functions directly)
- [ ] Show progress and errors in the window; run conversion in a background thread so the window never freezes

### Phase 5: Mapping screen (Milestone M2)
- [ ] List converted cursors
- [ ] Assign roles per cursor
- [ ] Pre-fill with auto-suggest
- [ ] Save the mapping and build the theme

**M2 done when:** the user can browse, map and apply without typing paths.

### Phase 6: Live preview
- [ ] Static image first
- [ ] Animate with frame delays (timer)
- [ ] Show the hotspot
- [ ] Link the preview to the list selection

Preview options, easiest first: (1) convert to GIF or PNG frames with ImageMagick or `xcur2png`; (2) read the Xcursor file directly in Python; (3) apply temporarily and let the user hover.

### Phase 7: Packaging and polish (Milestone M3)
- [ ] `install.sh` and `uninstall.sh` (symlink `bin/anicursor` into `~/.local/bin`; the launcher must resolve symlinks)
- [ ] Optional opt-in `--install-deps` in `install.sh` (see rules in the decision log)
- [ ] `.desktop` entry
- [ ] Edge cases (empty folder, bad names, conversion failures, missing permissions)
- [ ] Optional system-wide install, opt-in only (`/usr/share/icons`)
- [ ] README
- [ ] Test on a second machine or fresh VM

**M3 done when:** the full tool, with live preview, launches from one command.

---

## 8. Technical notes and gotchas

### Cursor and desktop

- **Spaces in filenames** (e.g. `05-Text Select`): quote every variable in Bash; prefer `find ... -print0` over bare globs; in Python use `pathlib` and pass argument lists to `subprocess`.
- **Theme location:** use `~/.local/share/icons/`, not the legacy `~/.icons/`.
- **Hardcoded mapping is the old way.** The manual guide maps names like `01-Normal` to `left_ptr`. The tool needs a user or preset-driven mapping step instead.
- **Symlink aliases** each role needs (examples from the manual guide):
  - Normal: `left_ptr`, `default`, `arrow`
  - Link: `pointer`, `hand2`, plus the hashed name `9d801198da01da15a616a15302036096`
  - Loading: `watch`, `left_ptr_watch`, `progress`, `wait`, `half-busy`, plus `00000000000000020000000000000000`
  - Text: `xterm`, `text`
  - Precision: `crosshair`, `cross`
  - Help: `help`, `question_arrow`, plus `5c6cd8ed9d305da6f1c6c04b2777b2d1`
  - Move: `move`, `fleur`, `all-scroll`
  - Unavailable: `not-allowed`, `forbidden`
  - Vertical resize: `ns-resize`, `v_double_arrow`, `n-resize`, `s-resize`
  - Horizontal resize: `ew-resize`, `h_double_arrow`, `e-resize`, `w-resize`
  - Diagonal 1: `nwse-resize`, `fd_double_arrow`, `nw-resize`, `se-resize`
  - Diagonal 2: `nesw-resize`, `bd_double_arrow`, `ne-resize`, `sw-resize`
  - Handwriting: `pencil`
  - Alternate select: `right_ptr`
- **`index.theme`** minimal content:
  ```
  [Icon Theme]
  Name=THEME_NAME
  Comment=Converted for Linux
  Inherits=core
  ```
- **Applying the theme:**
  ```
  gsettings set org.gnome.desktop.interface cursor-theme "THEME_NAME"
  gsettings set org.gnome.desktop.interface cursor-size 32
  ```
  Size guide: 24 (1080p default), 32 (1440p), 48 (4K), 64 (extra large). Some older GTK or Electron apps may need a re-login to pick up the change.
- **Undo is mandatory in Phase 2:** read the current values with `gsettings get` and save them before changing anything.
- **Cursor packs are often someone else's artwork.** `.gitignore` excludes `*.ani`, `*.cur` and `/samples/`; keep test packs in a local `samples/` folder.
- **Zenity limits:** fine for simple dialogs, but it cannot show animated previews or a custom mapping screen. That is why the GUI uses Python + GTK 4.
- **PYTHONPATH:** `python3 -m anicursor` only finds the package from the project root or with `PYTHONPATH` set. The launcher exports it for now; Phase 7 packaging replaces this.

### Bash lessons learned (mistakes made so far, worth remembering)

| Gotcha | Rule |
|---|---|
| `local` outside a function | Only valid inside functions; at the top level it errors and `set -e` ends the script |
| Passing an array | `"${arr[@]}"` expands to one argument per element (and nothing if empty); `"$arr"` is only the first element and fails under `set -u` when empty |
| Array lookup | `${ARR[$key]}` needs braces; `$ARR[$key]` is wrong. Use `${ARR[$key]:-}` for keys that may be absent under `set -u` |
| Assigning | `var=value`, never `$var=value` |
| Spacing in tests | `[[ "$a" == "b" ]]` needs spaces around `==`; without them the test is a non-empty string and always true |
| Counting an array | `(( ${#arr[@]} > 0 ))`; `( "${arr[@]}" > 0 )` runs the array as a command and creates a file named `0` |
| Negation | `if ! cmd >/dev/null 2>&1; then` is simpler than `(! cmd) ...` and avoids a subshell. Silence stdout **and** stderr together |
| `set -e` | A command used as an `if` condition is exempt; a bare failing command is not. Capture output with `if ! out=$(cmd); then` |
| Functions are not calls | Defining `check_path` does nothing until a line calls it |
| Comment-only function body | A function with only comments is a syntax error; put `:` or `return 0` in it temporarily |
| Dynamic scope | A called function can see its caller's `local` variables; avoid relying on it, pass data as arguments |
| `export` | Changes affect only the script process and its children; the launcher's `export PATH` is inherited by the checker and by Python |
| Sourcing a script | `source` runs `set -euo pipefail` in your interactive shell; wrap tests in `bash -c '...'`. Use the `BASH_SOURCE` guard so sourcing loads functions without running them |
| Exported functions | `export -f name` makes a function visible to child Bash processes (used to fake `dpkg` and `python3` in tests) |
| Stray files | Pasting terminal output into the shell can create junk files (`master`, `phase-1-bash`, `0`). Paste only commands |

---

## 9. Bash concepts to learn (via this project)

Variables, quoting, functions, `if` / `case`, arrays and associative arrays, `for` / `while` loops, `command -v`, `"$@"`, `trap`, exit codes, `getopts`, `mktemp`, brace expansion, `set -euo pipefail`, `readlink -f`, `BASH_SOURCE`, `export -f`, `shellcheck`, `bash -x`.

## 10. Python / GTK concepts to learn

`pathlib`, `subprocess`, `json`, dicts, GTK 4 windows and signals, file chooser dialogs, list widgets, timers for animation, pixbuf / texture display, threads (background conversion).

---

## 11. Git workflow

```bash
git add <files>
git commit -m "What changed"
git push
git switch -c phase-2-python-core      # one branch per phase
git switch main && git merge phase-1-bash
git log --oneline --all --graph
```

- Default branch is `main` (`git config --global init.defaultBranch main`).
- Commit after each finished checkbox; write messages that say what changed; keep samples out of Git; run `git status` before committing.
- **Fix the last commit message:** `git commit --amend -m "New message"`. An older one: `git rebase -i HEAD~N` and mark it `reword`.
- **After pushing a rewritten commit:** `git push --force-with-lease` (safe on your own branches that nobody else uses; avoid on shared branches).
- `git reflog` shows previous states if a rewrite goes wrong.
- If a branch name also exists as a file, Git reports "both revision and filename"; delete the stray file or add `--` after the name.
- Authentication: GitHub CLI (`gh auth login`) or an SSH key; passwords are not accepted.

---

## 12. Current status

- **Done:** Phase 0 (names, folders, Git, environment verified, pushed to GitHub, branch renamed to `main`). The dependency checker (Phase 1 Layers 1 to 6) is finished, tested and committed.
- **Now:** Phase 1, writing the launcher: `notify_error()`, then the locate and check steps, then the launch step.
- **Where the launcher stands:** the skeleton exists with `notify_error` as an empty stub and `check_path` written but never called (and it still prints "already in PATH", which must be removed). The locate, check and launch sections are still TODO.
- **Next action:** fill in `notify_error()` and test it alone, call `check_path` quietly, add the locate step, then the `if ! output=$(...)` block, then the launch. Review each piece before moving on.
- **Branch:** `phase-1-bash`

## 13. Working agreement with the AI helper

- Explain the concept, give a skeleton and a list of things to look up; the user writes the code.
- Review pasted code by pointing out bugs and unclear spots, ordered by severity, without rewriting it (a comment-only cleanup copy is fine if asked).
- Give test commands that do not uninstall anything.
- Do not write the whole product at once.

## 14. Decision log

| Decision | Reason |
|---|---|
| Hybrid Bash + Python GTK | Lightweight yet convenient; Zenity alone cannot do preview or mapping UI |
| Python is the core; Bash limited to launcher and system scripts | Better for JSON, mapping, file parsing and GUI; Bash still gets real learning tasks |
| GTK 4 | Current toolkit on Ubuntu 26.04 / GNOME 50 |
| PyGObject via apt, `win2xcur` via pipx | Matches system Python 3.14; pipx keeps conversion isolated |
| `gui/` inside the Python package | Cleaner imports |
| Per-user install, theme in `~/.local/share/icons/` | No root needed; modern path |
| System-wide install is opt-in only | Avoid unnecessary `sudo` |
| Undo built into Phase 2 | Changing the system cursor without a way back is the riskiest step |
| Target Ubuntu 26.04 LTS only for v1 | Keeps scope realistic; 26.10 and other distros later |
| PATH fix lives in the launcher, not the checker | An exported variable is inherited by the checker and by Python; a fix inside the checker would die with that process |
| The checker only reports; it never installs | Needs sudo, no terminal on `.desktop` launches, hard to handle failures. Automatic install is opt-in in `install.sh` (confirm first, group apt vs pipx, check each exit code, stop on required failures, re-run the checker to verify, never retry silently) |
| `pipx` is not a required dependency | It is only needed to install `win2xcur`, not to run it |
| Lookup table + `missing` holds table keys | Removes translation code and key-mismatch bugs |
| `notify_error()` lives in the launcher | The launcher decides terminal vs dialog; move to `scripts/lib.sh` only when a second script needs it |
| Stay in Python (no C++ rewrite) | Time goes to `win2xcur`, disk and user waiting, not the language. Measure first (`time`, `python3 -X importtime`, `cProfile`) and fix with lazy imports, background threads, caching |
| Keep modules swappable | A future native `.ani` parser could replace `win2xcur`, `pipx` and `libmagickwand-dev` |
|`zenity` is not a checked dependency | notify_error() detects it at runtime and falls back to notify-send, then stderr and a log file. There’s also nothing to change in the checker or its tests.|
## 15. Open questions

- Which preview approach to use first (PNG frames vs reading Xcursor directly)?
- Does `gsettings` apply correctly on this Wayland session? (Verify early in Phase 2.)
- Should the happy path get a `--verbose` flag (a good `getopts` exercise)?

## 16. Future ideas

- Native `.ani` / `.cur` parser to remove the `win2xcur`, pipx and ImageMagick dependencies (language decided after profiling, likely still Python)
- Packaging as a `.deb`, Flatpak or Snap
- Support for Ubuntu 26.10, other flavors and other distros
- Opt-in `--install-deps`

## 17. Changelog

| Date | Change |
|---|---|
| 2026-11-03 | Plan v1.0 locked. Phase 0 completed. Phase 1 started. |
| 2026-11-04 | Project pushed to GitHub. Commit message typo fixed with `--amend` and `--force-with-lease`. Default branch renamed from `master` to `main`; stray junk files removed. |
| 2026-11-06 | Dependency checker finished and tested (lookup table, `print_install`, `BASH_SOURCE` guard, all 8 test cases pass). PATH fix moved to the launcher. Launcher design settled; `notify_error()` and launcher in progress. C++ rewrite considered and rejected for now. |

---

## Prompt to give another AI

> I am building a lightweight Ubuntu tool called `anicursor` (Animated Cursor Setup). Below is the full plan and process log. I am currently on the phase listed under "Current status". Please help with the next action. Keep to the architecture and decisions in the plan, do not write the whole product at once, explain concepts I need to learn, and review my code by pointing out issues rather than rewriting it.