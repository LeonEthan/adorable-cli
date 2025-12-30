<div align="center">

<img src="assets/adorable-ai-logo.png" alt="adorable logo" width="220" />

# Adorable CLI - Deep Agent built on Agno

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
</p>

<p align="center">
  <a href="#quick-install">Quick Install</a> •
  <a href="#features">Features</a> •
  <a href="#usage">Usage</a> •
  <a href="#configuration">Configuration</a>
</p>

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/EN-English-blue" alt="English"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/🇨🇳_中文-red" alt="中文"></a>
</p>

</div>

---

**Adorable** is a deep agent for complex, long-horizon tasks, powered by the [Agno](https://github.com/agno-agi/agno) framework. It operates through continuous **interleaved reasoning and action**—thinking before every step, executing with precision, and analyzing results—to handle research, coding, and system automation reliably.

> Built on Agno's agent architecture with persistent memory, tool orchestration, and OpenAI-compatible APIs.

---

<div align="center">

<a id="features"></a>
## 🧩 Features

</div>

- **Deep Agent**: Built on Agno framework for planning, web search, coding, and file operations.
- **Interleaved Thinking**: Continuous **Think → Act → Analyze** loop—reasons before every step, never guesses, verifies all assumptions.
- **Persistent Memory**: Uses SQLite (`~/.adorable/memory.db`) and session summaries to maintain context across long sessions.
- **Multi-Modal Toolset**:
  - **Planning**: Reasoning engine & Todo list management.
  - **File Operations**: File reading, writing, and directory navigation.
  - **Web Search**: Deep web search (DuckDuckGo) & web content fetching (Fetch MCP).
  - **Coding**: Python scripting & Shell commands.
  - **Vision**: Vision capabilities for image analysis.
- **Interactive UI**: Rich terminal interface with history, autocompletion, and shortcuts.

<div align="center">

<a id="quick-install"></a>
## ⚡ Quick Install

We recommend using [uv](https://github.com/astral-sh/uv) to install and manage Adorable CLI.

### Install

```bash
uv tool install --python 3.13 adorable-cli
```

### Upgrade

```bash
uv tool upgrade adorable-cli --no-cache
```

If you run into missing dependencies after upgrading, force a reinstall:

```bash
uv tool upgrade adorable-cli --reinstall --no-cache
```

</div>

> On first run you will be guided to set `API_KEY`, `BASE_URL`, `MODEL_ID` into `~/.adorable/config`. You can run `ador config` anytime to update.

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
- `Ctrl+D` / `exit`: Quit session
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
  - `OPENAI_API_KEY` / `API_KEY`
  - `OPENAI_BASE_URL` / `BASE_URL`
  - `DEEPAGENTS_MODEL_ID` / `MODEL_ID`

Example (`~/.adorable/config`):

```ini
API_KEY=sk-xxxx
BASE_URL=https://api.openai.com/v1
MODEL_ID=gpt-4o
```

<div align="center">

## 🧠 Capabilities

</div>

- **Planning**: `ReasoningTools` for strategy; `TodoTools` for task tracking.
- **Research**: `DuckDuckGoTools` for search; Fetch MCP for web content extraction; `FileTools` for local context.
- **Execution**: `PythonTools` for logic/data; `ShellTools` for system ops.
- **Perception**: `ImageUnderstandingTool` for visual inputs.

See `src/adorable_cli/agent/prompts.py` for the full system prompt and guidelines.

<div align="center">

## 🧪 Example Prompts

</div>

- "Research the current state of quantum computing and write a summary markdown file."
- "Clone the 'requests' repo, analyze the directory structure, and create a diagram."
- "Plan and execute a data migration script for these CSV files."
