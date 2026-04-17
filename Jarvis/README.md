# 🤖 Jarvis

Jarvis is a local 🖥️ Windows desktop assistant built with 🐍 Python and 🎨 PySide6.
It now uses a hybrid 🧠 local NLU pipeline, a cached 📦 Windows app index, 🔍 fuzzy app matching, and a richer UI that shows what the assistant understood before and during execution.

---

## ✨ Highlights

* 🎬 Cinematic dark desktop UI with animated orb, 💬 chat view, 📜 activity log, history, and ⚙️ settings
* 🧠 Hybrid intent recognition: normalization, wake-word stripping, filler-word cleanup, synonym replacement, intent scoring, entity extraction, and legacy-pattern fallback
* ❓ Clarification prompts when confidence is too low
* 🖥️ Windows-wide app discovery across Start Menu, Desktop, Local AppData, Program Files, Program Files (x86), and WindowsApps
* 📦 Cached app index stored locally in `data/app_index.json`
* 🔍 Fuzzy app matching and multiple launch fallbacks
* 📊 UI feedback for detected intent, target, confidence, and launch method
* 🛡️ Safe local automation with confirmations for shutdown and restart

---

## 📂 Folder Structure

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
├── data/
├── logs/
├── main.py
├── README.md
└── requirements.txt
```

---

## 🧠 New Intent Pipeline

Jarvis no longer depends on exact command phrasing as the main path.

1. 🧹 Raw input is cleaned and normalized
2. 🎤 Wake-word and filler phrases are stripped
3. 🔄 Common verb synonyms are collapsed
4. 📊 Candidate intents are scored from keywords, patterns, and extracted entities
5. 🖥️ App-like targets are checked against the local app index
6. 🏆 The highest-confidence intent is selected
7. ❓ Low confidence → Jarvis asks a clarification
8. 🔙 Regex parser remains as fallback

---

## 🖥️ App Discovery

Jarvis builds a local 📦 app index and caches it in `data/app_index.json`.

### 🔍 Discovery sources

* 🧷 Current user Start Menu
* 🧷 Common Start Menu
* 🖥️ Current user Desktop
* 🖥️ Public Desktop
* 📂 `%LOCALAPPDATA%\\Programs`
* 📂 `%LOCALAPPDATA%`
* 📂 `%ProgramFiles%`
* 📂 `%ProgramFiles(x86)%`
* 🧠 `%LOCALAPPDATA%\\Microsoft\\WindowsApps`

### 📦 Indexed items

* 🔗 `.lnk` shortcuts
* 🌐 `.url` shortcuts
* ⚙️ `.exe` files

### ⚡ Launch strategy

1. 🏷️ Explicit config aliases
2. 📍 Direct file paths
3. 🔍 Cached index (exact + fuzzy)
4. ⚙️ Shell fallback
5. 💡 Suggestions

---

## 💬 Flexible Phrases That Now Work Better

All resolve to the same intent:

* `open discord`
* `Jarvis open discord`
* `can you open discord for me`
* `please start discord`
* `launch my discord app`
* `bring up discord`
* `start dc`
* `open disc`

---

## ⚡ Commands Included

* 🤖 `Jarvis, open Google`
* 💬 `Can you launch Discord for me?`
* 🎵 `Start spotify`
* 🌐 `Search YouTube for lo-fi music`
* 📁 `Create a folder`
* 📄 `Create a file`
* ⏰ `Tell me the time`
* 📸 `Take a screenshot`
* 🔊 `Volume up`
* ⚡ `Shutdown the PC`
* ⌨️ `Type Hello from Jarvis`
* 🖱️ `Move the mouse`
* 👆 `Left click`

---

## 🎨 UI Improvements

* 📊 Right-side panel shows:

  * intent
  * target
  * confidence
  * launch method
* ⚙️ Settings include:

  * app index stats
  * refresh button
* 📜 Logs in Activity tab + `logs/jarvis.log`

---

## 🛡️ Safety Model

* ⚠️ Confirmation dialogs for shutdown/restart
* 🔒 Global disable via settings
* 🚫 Protected folder denylist
* 📏 Mouse movement limits
* ⌨️ Typing delay safety
* ⏳ Shutdown delay (cancel possible)
* ❌ No destructive actions

---

## ⚙️ Windows Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

---

## 🎤 Voice Input

Jarvis supports local voice recognition with 🎤 Vosk.

1. 📥 Download model
2. 📦 Extract
3. ⚙️ Set path
4. 🎤 Start mic

---

## 🧠 Notes About App Launching

* 🏷️ Aliases override everything
* 🔄 Refresh index improves results
* 🧠 Store apps need fallback handling
* 🎯 Strong matches prioritized

---

## 🔧 Extending Jarvis

1. ➕ Add handler
2. 🧠 Update NLU
3. 🔗 Register in router
4. ⚙️ Improve discovery if needed
