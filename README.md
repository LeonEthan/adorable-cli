<div align="center">

<img src="assets/adorable-ai-logo.png" alt="adorable logo" width="220" />

# Adorable CLI - A universal autonomous agent for deep work

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
</p>

<p align="center">
  <a href="#quick-install">Quick Install</a> •
  <a href="#features">Features</a> •
  <a href="#usage">Usage</a> •
  <a href="#build">Build</a> •
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/EN-English-blue" alt="English"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/🇨🇳_中文-red" alt="中文"></a>
</p>

</div>

---

**Adorable** is a command-line autonomous agent built for complex, long-horizon tasks. Built by [Agno](https://github.com/agno-agi/agno), it follows a disciplined **Plan → Execute → Record → Verify** loop to handle research, coding, and system automation deeply and reliably.

> Supports OpenAI-compatible APIs.

---

<div align="center">

<a id="features"></a>
## 🧩 Features

</div>

- **Universal Autonomous Agent**: Capable of planning, research, coding, and complex execution.
- **Deep Work Loop**: Systematically plans, executes, records findings, and verifies outputs.
- **Persistent Memory**: Uses the local file system and SQLite (`~/.adorable/memory.db`) to maintain state across long sessions.
- **Multi-Modal Toolset**:
  - **Planning**: Reasoning engine & Todo list management.
  - **Research**: Deep web search (Tavily) & crawling (Crawl4AI).
  - **Execution**: Python scripting & Shell commands.
  - **Perception**: Vision capabilities for image analysis.
- **Interactive UI**: Rich terminal interface with history, autocompletion, and shortcuts.

<div align="center">

<a id="quick-install"></a>
## ⚡ Quick Install

| Method | Command | Best For |
|:------:|---------|----------|
| **🚗 auto** | `curl -fsSL https://leonethan.github.io/adorable-cli/install.sh | bash` | **✅ Recommended** - Linux/macOS |
| **🐍 pipx** | `pipx install adorable-cli` | Isolated CLI envs - Linux/macOS |
| **📦 pip** | `pip install adorable-cli` | Traditional Python environments |

</div>

> On first run you will be guided to set `API_KEY`, `BASE_URL`, `MODEL_ID`, `TAVILY_API_KEY` into `~/.adorable/config`. You can run `ador config` anytime to update.

<div align="center">
  <a id="platform"></a>
  
  ## 🖥 Platform Support
</div>

- OS: macOS, Linux x86_64
- Arch: `x86_64`; Linux `arm64` currently not supported
- Python: `>= 3.10` (recommended `3.11`)
- Linux glibc: `>= 2.28` (e.g., Debian 12, Ubuntu 22.04+, CentOS Stream 9)

<div align="center">

<a id="usage"></a>
## 🚀 Usage

</div>

```bash
# Start interactive session
adorable
# Or use alias
ador

# Configure settings
ador config

# Show help
ador --help
```

### CLI Commands

- `ador` / `adorable`: Start interactive chat
- `ador config`: Configure API keys and models
- `ador version`: Print CLI version

### Interactive Shortcuts
- `Enter`: Submit message
- `Alt+Enter` / `Ctrl+J`: Insert newline
- `@`: File path completion
- `/`: Command completion (e.g., `/help`, `/clear`)
- `Ctrl+Q`: Quick exit

### Global Options

- `--model <ID>`: Primary model ID (e.g., `gpt-4o`)
- `--base-url <URL>`: OpenAI-compatible base URL
- `--api-key <KEY>`: API key
- `--debug`: Enable debug logging
- `--plain`: Disable color output

Example:

```bash
ador --api-key sk-xxxx --model gpt-4o chat
```

<div align="center">

## 🔧 Configuration

</div>

- **Config File**: `~/.adorable/config`
- **Environment Variables**:
  - `DEEPAGENTS_API_KEY` / `API_KEY`
  - `DEEPAGENTS_BASE_URL` / `BASE_URL`
  - `DEEPAGENTS_MODEL_ID`
  - `TAVILY_API_KEY`

Example (`~/.adorable/config`):

```ini
API_KEY=sk-xxxx
BASE_URL=https://api.openai.com/v1
TAVILY_API_KEY=tvly_xxxx
MODEL_ID=gpt-4o
```

<div align="center">

## 🧠 Capabilities

</div>

- **Planning**: `ReasoningTools` for strategy; `session_state.todos` for task tracking.
- **Research**: `TavilyTools` for search; `Crawl4aiTools` for scraping; `FileTools` for local context.
- **Execution**: `PythonTools` for logic/data; `ShellTools` for system ops.
- **Perception**: `ImageUnderstandingTool` for visual inputs.

See `src/adorable_cli/prompt.py` for the full system prompt and guidelines.

<div align="center">

## 🧪 Example Prompts

</div>

- "Research the current state of quantum computing and write a summary markdown file."
- "Clone the 'requests' repo, analyze the directory structure, and create a diagram."
- "Plan and execute a data migration script for these CSV files."

