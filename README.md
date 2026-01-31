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
- **Claude Code-Inspired Architecture**: Streaming-first async generator loop, parallel tool execution, smart context compression.
- **Interleaved Thinking**: Continuous **Think → Act → Analyze** loop—reasons before every step, never guesses, verifies all assumptions.
- **Persistent Memory**: Uses SQLite (`~/.adorable/memory.db`) and session summaries to maintain context across long sessions.
- **Smart Context Management**: Priority-based context assembly with `normalize_to_size` for token limit handling.
- **Multi-Modal Toolset**:
  - **Planning**: Reasoning engine & Todo list management.
  - **File Operations**: Read-before-edit safety, batch operations with `MultiEditTool`, line number prefix validation.
  - **Web Search**: Deep web search (DuckDuckGo) & web content fetching (Fetch MCP).
  - **Coding**: Python scripting & Shell commands.
  - **Vision**: Vision capabilities for image analysis.
  - **Hierarchical Agents**: `AgentTool` for task decomposition with sub-agents.
- **Streaming-First UI**: Real-time response streaming with Rich terminal interface.
- **ANR Detection**: Worker thread monitors event loop responsiveness (5000ms threshold) with automatic stack capture.
- **Line Number Validation**: Detects and warns about line number prefixes in edit operations (e.g., "2\tcontent" → "content").
- **Bash Sandbox**: macOS `sandbox-exec` integration with generated profiles for secure command execution.

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

> On first run you will be guided to set `API_KEY`, `BASE_URL`, `MODEL_ID` into `~/.adorable/config.json` (and a legacy `~/.adorable/config` is also maintained for compatibility). You can run `ador config` anytime to update.

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

- **Config File**: `~/.adorable/config.json` (legacy: `~/.adorable/config`)
- **Environment Variables**:
  - `OPENAI_API_KEY` / `API_KEY`
  - `OPENAI_BASE_URL` / `BASE_URL`
  - `DEEPAGENTS_MODEL_ID` / `MODEL_ID`

### Advanced Configuration

- **Database Path**: set `ADORABLE_DB_PATH` (or `db.path` in `config.json`) for persistent memory storage.

Example (`~/.adorable/config.json`):

```json
{
  "openai": {
    "api_key": "sk-xxxx",
    "base_url": "https://api.openai.com/v1"
  },
  "models": {
    "default": "gpt-4o",
    "fast": "gpt-4o-mini",
    "vlm": "gpt-4o"
  },
  "confirm_mode": "ask",
  "server": {
    "host": "0.0.0.0",
    "port": 7777
  }
}
```

<div align="center">

## 🧠 Capabilities

</div>

- **Planning**: `ReasoningTools` for strategy with `think()`/`analyze()`; `TodoTools` for task tracking.
- **Context Management**: `ContextAssembler` with priority-based truncation; `normalize_to_size` for token limits.
- **Research**: `DuckDuckGoTools` for search; Fetch MCP for web content; `FileTools` with read-before-edit safety.
- **Execution**: `PythonTools` for logic/data; `ShellTools` with confirmation for destructive commands.
- **Tool Orchestration**: `ParallelToolExecutor` with side-effect categorization; batch read-only operations.
- **Hierarchical Agents**: `AgentTool` for task decomposition; `ResultSynthesizer` for combining sub-agent outputs.
- **Memory**: `SessionSummarizer` for long-term context; `WorkingMemory` for high-priority items; `CompressionManager` for tool results.
- **Perception**: `ImageUnderstandingTool` for visual inputs.
- **Prompt Engineering**: Aggressive conciseness enforcement; confidence calibration; "never guess" uncertainty handling.

See `src/adorable_cli/agent/prompts.py` for the full system prompt and guidelines.

<div align="center">

## 🏗 Architecture

</div>

Adorable CLI is rebuilt with Claude Code's architectural patterns:

### Core Components

| Component | Description | Location |
|-----------|-------------|----------|
| **Agent Loop** | Six-phase async generator (`tt` function) with streaming-first design | `core/loop.py` |
| **Message Models** | Three-stage representation (CliMessage → APIMessage → StreamAccumulator) | `models/messages.py` |
| **Context Management** | Priority-based assembly + `normalize_to_size` for token limits | `context/` |
| **Tool Execution** | Parallel batch execution with side-effect categorization | `tools/executor.py` |
| **File Safety** | Read-before-edit enforcement with `MultiEditTool` | `tools/file_safety.py` |
| **Streaming JSON** | Progressive parser with recovery strategies | `utils/streaming_json.py` |
| **AgentTool** | Hierarchical task decomposition with sub-agents | `tools/agent_tool.py` |
| **Memory** | Session summarization + working memory + compression | `memory/` |
| **Prompts** | Aggressive conciseness + psychological techniques | `prompts/` |
| **ANR Detection** | Event loop monitoring with heartbeat and stack capture | `core/anr_detector.py` |

### Key Design Patterns

1. **Streaming-First**: All operations use async generators for real-time UI updates
2. **Interleaved Reasoning**: `think()` → action → `analyze()` loop prevents tool hallucination
3. **Safety-First**: File edits require read-before-edit validation
4. **Parallel Execution**: Read-only tools run in parallel; write operations are serialized
5. **Smart Compression**: Context automatically compresses when approaching token limits

<div align="center">

## 🧪 Example Prompts

</div>

- "Research the current state of quantum computing and write a summary markdown file."
- "Clone the 'requests' repo, analyze the directory structure, and create a diagram."
- "Plan and execute a data migration script for these CSV files."
