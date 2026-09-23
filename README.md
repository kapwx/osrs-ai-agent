# OSRS AI Agent 🎮🤖

An experimental autonomous AI agent architecture for **Old School RuneScape (OSRS)** combining **RuneLite** telemetry, **Google Gemini API** (`gemini-3.8-flash`) reasoning, and a **humanized input driver**.

---

## 🏗️ Architecture

```text
+-----------------------+           HTTP POST (JSON)          +-------------------------------+
|  RuneLite Plugin      | --------------------------------->  |   Brain Middleware            |
|  (Java 11)            |   (Health, Stats, Inventory,        |   (FastAPI + Python)          |
|                       |    Nearby NPCs & Game Objects)      +-------------------------------+
+-----------------------+                                                     |
                                                                              | Game State Analysis
                                                                              v
+-----------------------+           Pulls Decision            +-------------------------------+
|  Input Executor       | <---------------------------------- |   Google Gemini API           |
|  (PyAutoGUI + Bézier) |   {"action": "ATTACK_NPC", ...}     |   (gemini-3.8-flash)          |
+-----------------------+                                     +-------------------------------+
           |
           v (Human-like curved mouse clicks)
     [ OSRS Client ]
```

---

## 📁 Repository Structure

```text
osrs-ai-agent/
├── plugin/                               # RuneLite Java Plugin
│   ├── build.gradle                      # Gradle build file for RuneLite
│   └── src/main/java/com/agent/
│       ├── AgentPlugin.java              # Gathers telemetry & streams via HTTP
│       └── AgentConfig.java              # In-game plugin settings
├── brain/                                # AI Decision Engine
│   ├── requirements.txt                  # FastAPI, google-genai, Pydantic
│   ├── main.py                           # FastAPI middleware & endpoint router
│   ├── gemini_client.py                  # Gemini 3.8 Flash structured reasoning
│   └── .env.example                      # API key and server environment config
├── executor/                             # Physical Action Simulation
│   ├── requirements.txt                  # PyAutoGUI, pygetwindow, requests
│   └── input_driver.py                   # Bézier-curved, human-timed input executor
├── .gitignore
└── README.md
```

---

## 🚀 Getting Started

### 1. Prerequisites
* **Java 11 or higher**
* **Python 3.10 or higher**
* **RuneLite Client**
* **Google Gemini API Key** (Get one at [Google AI Studio](https://aistudio.google.com))

---

### 2. Setting Up the Brain (Python Backend)

1. Navigate to the `brain` folder:
   ```bash
   cd brain
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure your `.env` file:
   ```bash
   cp .env.example .env
   ```
   Add your `GEMINI_API_KEY`:
   ```env
   GEMINI_API_KEY=AIzaSy...
   ```
5. Launch the server:
   ```bash
   python main.py
   ```
   The server will start at `http://localhost:8000`.

---

### 3. Setting Up the RuneLite Plugin

1. Open the `plugin/` directory in IntelliJ IDEA or your preferred Java IDE.
2. Build the plugin jar using Gradle:
   ```bash
   ./gradlew build
   ```
3. Add the plugin to your RuneLite client or run it via RuneLite's plugin test launcher.
4. In RuneLite settings, locate **OSRS AI Agent Bridge** and verify the backend URL (`http://localhost:8000/api/state`).

---

### 4. Running the Input Executor

1. In a separate terminal, navigate to `executor/`:
   ```bash
   cd executor
   pip install -r requirements.txt
   ```
2. Start the driver:
   ```bash
   python input_driver.py
   ```
> [!IMPORTANT]
> **Safety Fail-Safe**: Move your mouse cursor immediately into the top-left corner `(0, 0)` of your screen to abort the executor at any time.

---

## 🛡️ Research Disclaimer & Anti-Cheat

> [!WARNING]
> This project is designed purely for **academic research into LLM game environment perception, decision logic, and agentic workflows**.
> * Automating inputs in Old School RuneScape violates Jagex's Terms of Service and Anti-Bot rules.
> * Always test on a throwaway sandbox account.
