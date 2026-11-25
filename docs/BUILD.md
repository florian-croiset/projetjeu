# Building Echo

## Requirements

- Python 3.10+
- pip
- The project dependencies (`pip install -r requirements.txt`)

PyInstaller is installed automatically by the scripts.

---

## Linux

```bash
./packaging/build_linux.sh          # release build (DEV_MODE disabled)
./packaging/build_linux.sh --dev    # build with DEV_MODE enabled
./packaging/build_linux.sh --clean  # remove previous builds, then build
```

Output: `dist/Echo`, a single self-contained executable (run it with `./dist/Echo`).

---

## Windows

```bat
packaging\build_windows.bat          :: release build (DEV_MODE disabled)
packaging\build_windows.bat --dev    :: build with DEV_MODE enabled
packaging\build_windows.bat --clean  :: remove previous builds, then build
```

Arguments can be combined in any order:

```bat
packaging\build_windows.bat --clean --dev
```

Output: `dist\Echo.exe`, a single self-contained executable.

---

## Distribution

Send the single `dist/Echo` (`Echo.exe` on Windows) file: assets, libraries and the Python runtime are all embedded, nothing else is required on the target machine. The first launch is a bit slower because the file unpacks itself into a temporary folder.

Do not ship `slot_*.json` or `user_settings.json` (nor the legacy `parametres.json`): they are per-player files, created on first launch in:

- **Linux**: `~/.local/share/Echo/`
- **Windows**: `%LOCALAPPDATA%\Echo\`

Network ports to open on a host: `5555/TCP` and `5556/UDP` (UDP is optional, the game falls back to TCP).

---

## Release vs dev

| | Release (default) | `--dev` |
|---|---|---|
| `DEV_MODE` | `False` | `True` |
| FPS counter | no | yes |
| Orbs unlocked automatically | no | yes |
| Debug overlay | no | yes |

> `settings.py` is patched temporarily during the build and restored automatically (even on error).

If an interrupted build leaves a `settings.py.bak_build` file behind, copy it back over `settings.py`.

---

## Checking a build

`Echo --selftest result.txt` hosts a throw-away game headless (saves go to a temporary folder), plays a few seconds and writes `OK` (or the error) to `result.txt`. Copy the executable alone into an empty folder and run it there to check that it is really self-contained:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./Echo.exe --selftest result.txt
```
