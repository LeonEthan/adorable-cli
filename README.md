<div align="center">

<img src="assets/adorable-ai-logo.png" alt="adorable.ai logo" width="220" />

# Adorable CLI - A powerful cli agents assistant

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

Command-line agent built on Agno. Task-centric interaction: you set goals, the agent drives a "collect → act → verify" loop, and uses a todo list when tasks get complex.

> Supports OpenAI-compatible APIs.

---

<div align="center">

<a id="features"></a>
## 🧩 Features

</div>

- Interactive sessions with Markdown output and streaming
- Plan → Execute → Verify loop designed for multi-step tasks
- Multi-tool orchestration: web search, crawl, file I/O, math, memory
- Local persistent memory (`~/.adorable/memory.db`) across sessions
- Simple configuration; supports custom models and compatible API providers

<div align="center">

<a id="quick-install"></a>
## ⚡ Quick Install

| Method | Command | Best For |
|:------:|---------|----------|
| **🚗 auto** | `curl -fsSL https://leonethan.github.io/adorable-cli/install.sh \| bash` | **✅ Recommended** - Linux/macOS |
| **🐍 pipx** | `pipx install adorable-cli` | Isolated CLI envs - Linux/macOS |
| **📦 pip** | `pip install adorable-cli` | Traditional Python environments |

</div>

> On first run you will be guided to set `API_KEY`, `BASE_URL`, `MODEL_ID`, `TAVILY_API_KEY` into `~/.adorable/config` (KEY=VALUE). You can run `adorable config` anytime to update.

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

```
# Start interactive session
adorable
# Or use alias
ador

# Configure required settings (API_KEY/BASE_URL/MODEL_ID/TAVILY_API_KEY)
adorable config

# Show help
adorable --help
# Alias help
ador --help
```

Exit keywords: `exit` / `quit` / `q` / `bye`

<div align="center">

## 🔧 Configuration

</div>

- Default model: `gpt-5-mini`
- Sources:
  - Interactive: `adorable config` (writes to `~/.adorable/config`)
  - Environment: `API_KEY` or `OPENAI_API_KEY`; `BASE_URL` or `OPENAI_BASE_URL`; `TAVILY_API_KEY`; `ADORABLE_MODEL_ID`; `FAST_MODEL_ID`

Example (`~/.adorable/config`):

```
API_KEY=sk-xxxx
BASE_URL=https://api.openai.com/v1
TAVILY_API_KEY=tvly_xxxx
MODEL_ID=gpt-5-mini
FAST_MODEL_ID=gpt-5-mini
```

### Context Window Guard

To prevent model context overflow, Adorable includes a context guard with safe defaults. You can tune it via environment variables:

- `ADORABLE_CONTEXT_WINDOW`: Override the model context window in tokens (e.g., `131072`).
- `ADORABLE_CTX_MARGIN`: Safety margin in tokens (default `1024`). Supports percentages like `"5%"`.
- `ADORABLE_CTX_AVG_RUN_TOKENS`: Approximate tokens per history run for budgeting (default `512`).
- `ADORABLE_CTX_HISTORY_STRATEGY`: History budgeting strategy: `avg_only` (default) or `exact_when_possible` to estimate recent runs using actual messages when accessible.
- `ADORABLE_CTX_INPUT_STRATEGY`: Input compression strategy when needed: `tail_head` (default), `hybrid` (preserve first fenced code block), or `summarize` (currently falls back to tail/head without external calls).
- `ADORABLE_VLM_IMAGE_TOKENS_PER_IMAGE`: Per-image token budget for VLM inputs (default `0` – disabled). Set a conservative value (e.g., `4096`) to account for image payloads.

These settings help the agent trim history or lightly compress very long inputs before a run so that `(system + input + history) + max_tokens` remains within the model window.

#### Session Summary Integration

Agno 内置会话摘要可在历史较长时生成精炼摘要，并可选择加入上下文以替代大段历史，从而降低 token 压力并保持语义连续性。

- 在 Agent 配置中启用并加入摘要：
  - `enable_session_summaries=True`
  - `add_session_summary_to_context=True`
- 当以上选项开启时，Adorable 的 `context_guard` 会在预算预览中包含当前会话摘要文本，以更准确估算上下文体积；随后仍按既定策略优先削减历史、必要时轻量压缩输入。
- 建议与 `ADORABLE_CTX_HISTORY_STRATEGY=exact_when_possible` 配合使用，以获得更精确的历史体积估算。

注意：若摘要不可用或获取失败，`context_guard` 将自动回退到占位估算，保证稳健性。

自定义会话摘要（Customize Session Summaries）
- 使用 `FAST_MODEL_ID` 为摘要选择更快的模型（OpenAI 兼容，`OpenAILike`）；未设置时默认与主模型一致。
- 可在 `adorable config` 中设置 `FAST_MODEL_ID`，或通过环境变量注入；摘要模型只用于 SessionSummaryManager，不影响主回复模型。

<div align="center">

## 🧠 Capabilities

</div>

- Reasoning & planning: `ReasoningTools` (structured reasoning and step planning)
- Calculation & checks: `CalculatorTools` (numeric operations and validation)
- Web search: `TavilyTools` (requires `TAVILY_API_KEY`)
- Web crawling: `Crawl4aiTools` (visit URLs and extract content)
- File operations: `FileTools` (search/read/write; scope limited to the launch directory `cwd`)
- Memory storage: `MemoryTools` + `SqliteDb` (`~/.adorable/memory.db`)

System prompt and TODO list guidelines: see `src/adorable_cli/prompt.py`.

Execution tools: `PythonTools` and `ShellTools` (Agno defaults) are used for code and command execution, returning `str` outputs.
Interfaces: `execute_python_code(code: str, variable_to_return: Optional[str] = None) -> str`, `run_shell_command(command: str, tail: int = 100) -> str`.

<div align="center">

## 🧪 Example Prompts

</div>

- "Summarize the latest Python features and provide example code"
- "Read code from the project's `src` directory and generate a detailed README saved to the repo root"

<div align="center">

## 🛠️ Run from Source (uv/venv)

</div>

Using uv (recommended):

```
uv sync
uv run adorable --help
uv run adorable
```

Note: To pin Python version, use `uv sync -p 3.11`.

Using venv:

```
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e .
adorable --help
adorable
```

Alternative module invocation:

```
python -m adorable_cli.main
```

<div align="center">

<a id="build"></a>
## 📦 Build & Release

</div>

- Entry points: see `pyproject.toml` (`adorable`, `ador`)
- PyPI release: push `v*` tags or trigger manually; CI builds and publishes
  - Release command: `git tag vX.Y.Z && git push origin vX.Y.Z`
- Automated versioning: `release-please` based on Conventional Commits
  - Common types: `feat:` `fix:` `perf:` `refactor:` `docs:`
- Local build & install:
  - `python -m build` (outputs `dist/*.tar.gz` and `dist/*.whl`)
  - `python -m pip install dist/*.whl`

<div align="center">

<a id="contributing"></a>
## 🤝 Contributing

</div>

- PRs and issues welcome; follow Conventional Commits so `release-please` can generate changelogs.
- Dev tips:
  - Use `pipx` or virtualenv;
  - Follow `pyproject.toml` style (Ruff/Black, line width `100`).
  - Run `adorable --help` to quickly validate CLI behavior.

<div align="center">

## 💡 FAQ & Troubleshooting

</div>

- Auth failure / model unavailable:
  - Check `API_KEY` / `BASE_URL`; ensure `MODEL_ID` is supported
- Poor search quality:
  - Set `TAVILY_API_KEY`; be explicit about search goals and scope
- PEP 668 (system env disallows writes):
  - Prefer `pipx` to get an isolated, cross-platform CLI environment
- Linux arm64 currently not supported:
  - Use `x86_64` or macOS; or run via WSL2

<div align="center">

## 🔒 Privacy & Security

</div>

- The agent may read/write files under the current working directory; review changes in production
- Local memory is stored at `~/.adorable/memory.db`; remove it if not needed

### Safety Strategy: Confirmation Modes + Hard Ban Layer

- Modes
  - `normal`: prompts before Python, Shell, and file write operations.
  - `auto`: pauses Python/Shell for hard-ban checks, then auto-confirms.
- Hard bans (always blocked)
  - `rm -rf /` or equivalents targeting root
  - any `sudo` command
- Scope & outputs
  - File operations are limited to the current working directory (`cwd`)
  - Execution tools return `str` outputs only
- Configuration
  - No external `security.yaml`. Behavior is built-in and enforced by the confirmation layer.

<div align="center">

## 🧭 Developer Guide

</div>

- Style & config: Ruff/Black in `pyproject.toml`, line width `100`
- CLI entrypoints: `src/adorable_cli/__main__.py`, `src/adorable_cli/main.py`
- System prompt: `src/adorable_cli/prompt.py`
- Default model: `gpt-5-mini`

<div align="center">

## 📜 License

</div>

- MIT