[![Discord](https://img.shields.io/badge/Discord-Join%20Server-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/DEINLINK)
# 🤖 Jarvis

> 🎬 A cinematic local AI desktop assistant for Windows with 🎤 voice control, 🧠 natural language understanding, 🖥️ desktop automation, and a modern 🤖 agent-style architecture.

![Platform](https://img.shields.io/badge/Platform-Windows-0A84FF?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![UI](https://img.shields.io/badge/UI-PySide6-41CD52?style=for-the-badge)
![Voice](https://img.shields.io/badge/Voice-Local%20Vosk-111827?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Active%20Project-22C55E?style=for-the-badge)

## ✨ Overview

**Jarvis** is a fully local 🖥️ Windows desktop assistant built in 🐍 **Python** with 🎨 **PySide6**.  
It combines a sleek futuristic interface with a practical local AI core that can:

- 🧠 understand flexible natural language  
- 📁 create files and folders  
- 🌐 open apps and websites  
- 🎤 handle microphone input and 🔊 text-to-speech  
- 🖱️ control parts of the desktop safely  
- 🧰 route requests through an extensible tool system  
- 🛡️ apply confirmations and guardrails for sensitive actions  

This project is focused on **legitimate personal desktop automation only**.

## 🚀 Why This Project Is Cool

Jarvis is not just a static command launcher.

It has been upgraded into a more modern 🤖 **agent-style assistant** with:

- 🧠 intent recognition  
- 🔍 entity extraction  
- 🪄 action planning  
- 🧰 tool selection  
- 🧾 lightweight memory and context  
- 🛡️ guardrails and confirmations  
- 📈 traceable execution flow  

That means Jarvis can handle natural phrasing like:

- `open discord`
- `can you launch discord for me`
- `please start spotify`
- `open youtube`
- `and search for lofi music`
- `copy that to clipboard`
- `focus discord`

## 🖥️ Main Features

### 🎨 Modern Desktop UI

- ✨ Futuristic dark interface  
- 🟢 Animated assistant orb  
- 💬 Chat-style interaction panel  
- 📜 Activity log and command history  
- 🧠 Agent trace and memory view  
- ⚙️ Dedicated settings overlay  
- 🎤 Microphone controls with stop button while recording  

### 🧠 Local AI Command Understanding

- 💬 Flexible natural language input  
- 🌍 English + German command understanding  
- 🔄 Synonym handling  
- 🧹 Filler word cleanup  
- 🔁 Follow-up command support  
- 🧠 Context-aware references like `there`, `it`, `das`, `dort`  
- ❓ Clarification prompts when confidence is low  

### 🧰 Desktop Automation Tools

- 🚀 Open apps  
- 🌐 Open websites  
- 🔎 Search Google  
- ▶️ Search YouTube  
- 📁 Create folders  
- 📄 Create files  
- 📸 Take screenshots  
- ⏰ Get time and date  
- 🔊 Volume control  
- ⚡ Shutdown / restart / lock PC  
- ⌨️ Type text  
- 🖱️ Move mouse  
- 👆 Click mouse  
- 🪟 Focus windows  
- 📋 Read clipboard  
- ✍️ Write clipboard  

### 🔍 Windows App Discovery

Jarvis can find installed apps across the PC by scanning:

- 🧷 Start Menu shortcuts  
- 🖥️ Desktop shortcuts  
- 📂 `Program Files`  
- 📂 `Program Files (x86)`  
- 📂 `LocalAppData`  
- 🧠 Windows app shortcuts where accessible  

It builds a local cache and supports:

- 🔍 fuzzy app matching  
- 🏷️ alias matching  
- ⚙️ shell fallback launching  
- 💡 helpful suggestions when no strong match is found  

### 🛡️ Safety Features

- ⚠️ Confirmation dialogs for dangerous actions  
- 🔒 Guardrails for shutdown and restart  
- 🚫 Protected path denylist  
- 📏 Mouse distance safety limits  
- 📦 Clipboard payload limits  
- 📜 Activity logging and execution trace  

## 🧠 Agent Architecture

Jarvis uses a modular local architecture instead of one rigid command parser.

### Core Layers

- 🧠 `AgentCore`  
  Central orchestrator for command handling, planning, tool selection, guardrails, execution, response generation, and memory updates.

- ⚙️ `JarvisBrainService`  
  Builds structured plans from user intent and context.

- 🔍 `NLUService`  
  Handles multilingual normalization, synonym replacement, scoring, and fallback recognition.

- 🧰 `ToolRegistry`  
  Registers capabilities as structured tools instead of hardcoded routing logic.

- 🛡️ `Guardrails`  
  Applies confirmation rules and execution constraints.

- 🧾 `ConversationContextService`  
  Stores recent state such as the last app, last website, last created path, last workflow, and previous replies.

  # 🤖 Jarvis
