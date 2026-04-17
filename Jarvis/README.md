# Jarvis

Jarvis is a local Windows desktop assistant built with Python and PySide6. It now uses a hybrid local NLU pipeline, a cached Windows app index, fuzzy app matching, and a richer UI that shows what the assistant understood before and during execution.

## Highlights

- Cinematic dark desktop UI with animated orb, chat view, activity log, history, and settings
- Hybrid intent recognition:
  normalization, wake-word stripping, filler-word cleanup, synonym replacement, intent scoring, entity extraction, and legacy-pattern fallback
- Clarification prompts when confidence is too low
- Windows-wide app discovery across Start Menu shortcuts, Desktop shortcuts, Local AppData, Program Files, Program Files (x86), and WindowsApps when accessible
- Cached app index stored locally in `data/app_index.json`
- Fuzzy app matching and multiple launch fallbacks
- UI feedback for detected intent, target, confidence, and launch method
- Safe local automation with confirmations for shutdown and restart

## Folder Structure

```text
Jarvis/
├── app/
│   ├── assets/
│   ├── commands/
│   │   ├── handlers/
│   │   │   ├── applications.py
│   │   │   ├── filesystem.py
│   │   │   ├── info.py
│   │   │   ├── system.py
│   │   │   └── web.py
│   │   ├── base.py
│   │   ├── parser.py
│   │   ├── registry.py
│   │   └── router.py
│   ├── core/
│   │   ├── config_manager.py
│   │   ├── history_store.py
│   │   ├── logger.py
│   │   ├── models.py
│   │   └── paths.py
│   ├── services/
│   │   ├── app_discovery_service.py
│   │   ├── app_launcher_service.py
│   │   ├── nlu_service.py
│   │   ├── speech_service.py
│   │   ├── system_service.py
│   │   └── tts_service.py
│   └── ui/
│       ├── widgets/
│       │   ├── chat_bubble.py
│       │   ├── confirmation_dialog.py
│       │   └── glow_orb.py
│       ├── main_window.py
│       └── styles.py
├── config/
│   ├── settings.example.json
│   └── settings.json
├── data/
│   ├── app_index.json
│   └── history.json
├── logs/
├── main.py
├── README.md
└── requirements.txt
```

## New Intent Pipeline

Jarvis no longer depends on exact command phrasing as the main path.

1. Raw input is cleaned and normalized.
2. Wake-word and filler phrases are stripped.
3. Common verb synonyms are collapsed.
4. Candidate intents are scored from keywords, patterns, and extracted entities.
5. App-like targets are checked against the local app index to raise or lower confidence.
6. The highest-confidence intent is selected.
7. If confidence is too low, Jarvis asks a short clarification question in the UI.
8. The old regex parser remains only as a fallback layer.

## App Discovery

Jarvis builds a local app index and caches it in `data/app_index.json`.

Discovery sources:

- Current user Start Menu
- Common Start Menu
- Current user Desktop
- Public Desktop
- `%LOCALAPPDATA%\\Programs`
- `%LOCALAPPDATA%`
- `%ProgramFiles%`
- `%ProgramFiles(x86)%`
- `%LOCALAPPDATA%\\Microsoft\\WindowsApps`

Indexed items:

- `.lnk` shortcuts
- `.url` shortcuts
- `.exe` files

The app launcher then tries, in order:

1. Explicit config aliases
2. Direct file paths
3. Cached app index exact or fuzzy matches
4. Common shell command fallbacks
5. Helpful suggestions if no candidate is strong enough

## Flexible Phrases That Now Work Better

All of these should resolve to the same app intent for Discord when the index or aliases can support it:

- `open discord`
- `Jarvis open discord`
- `can you open discord for me`
- `please start discord`
- `launch my discord app`
- `I want to go into discord`
- `bring up discord`
- `open the discord program`
- `start dc`
- `open disc`
- `launch disscord`

Strong app-opening examples:

- `open visual studio code`
- `open vscode`
- `bring up chrome`
- `launch spotify`
- `open my browser`
- `start calculator`
- `open file explorer`

## Commands Included

- `Jarvis, open Google`
- `Jarvis, open Discord`
- `Can you launch Discord for me?`
- `Start dc`
- `Open disc`
- `Open visual studio code`
- `Open vscode`
- `Open my browser`
- `Search YouTube for lo-fi music`
- `Create a folder on desktop called Projects`
- `Create a file in documents called notes.txt`
- `Tell me the time`
- `Tell me the date`
- `Take a screenshot`
- `Volume up`
- `Set volume to 40`
- `Mute`
- `Shutdown the PC`
- `Restart the PC`
- `Cancel shutdown`
- `Type Hello from Jarvis`
- `Move the mouse right 120`
- `Left click`

## UI Improvements

- The right-side panel now shows:
  detected intent, detected target, confidence score, and chosen launch method
- Settings now include:
  app index stats and a `Refresh App Index` button
- Jarvis logs app discovery, matching, and launch attempts to the Activity tab and `logs/jarvis.log`

## Safety Model

- Shutdown and restart require an on-screen confirmation dialog
- Shutdown and restart can be disabled globally from Settings
- Protected folders are denylisted in `config/settings.json`
- Mouse movement is capped by `mouse_max_distance`
- Typing waits for a configurable delay so you can focus the correct window
- Windows shutdown uses a delay so you can still abort it with `cancel shutdown`
- No destructive file operations are performed automatically

## Windows Setup

1. Install Python 3.11 or newer.
2. Open PowerShell in the project folder.
3. Create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

4. Install dependencies:

```powershell
pip install -r requirements.txt
```

5. Start Jarvis:

```powershell
python main.py
```

## Voice Input

Voice input is local and optional. Jarvis uses `vosk` when a model path is configured.

1. Download an English model from [Vosk Models](https://alphacephei.com/vosk/models).
2. Extract it somewhere on disk.
3. Set `vosk_model_path` in `config/settings.json` or in the Settings tab.
4. Use the Mic button or press `Ctrl+Space`.

If no Vosk model is configured, Jarvis still works fully through text input.

## Notes About App Launching

- Manual aliases in `config/settings.json` still work and remain the highest-priority override
- The app index improves best after one refresh on your machine
- Some Microsoft Store apps only expose indirect shortcuts; Jarvis will still try to launch them through shortcuts or shell fallbacks where possible
- If an app is found in multiple places, Jarvis prefers Start Menu shortcuts and stronger fuzzy matches first

## Extending Jarvis

1. Add or update a handler under `app/commands/handlers/`.
2. Add a new scoring rule or entity extraction path in `app/services/nlu_service.py`.
3. Register the handler in `app/commands/router.py`.
4. If the command opens software, consider improving aliases or discovery behavior in `app/services/app_launcher_service.py` or `app/services/app_discovery_service.py`.
