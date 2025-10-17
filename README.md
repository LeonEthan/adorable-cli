<div align="center">

# 🐱 Adorable CLI

### Command-line Super Agents built on Agno

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
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

<a id="quick-start"></a>
## ⚡ Quick Start

| Method | Command | Best For |
|:------:|---------|----------|
| **🐍 pipx** | `pipx install adorable-cli` | **✅ Recommended** - Linux/macOS |
| **🚗 auto** | `curl -fsSL https://leonethan.github.io/adorable-cli/install.sh \| bash` | non-programmer - Linux/macOS |
| **📦 pip** | `pip install adorable-cli` | Traditional Python environments |

</div>

> On first run you will be guided to set `API_KEY`, `BASE_URL`, `MODEL_ID`, `TAVILY_API_KEY` into `~/.adorable/config` (KEY=VALUE). You can run `adorable config` anytime to update.

<div align="center">

<a id="usage"></a>
## 🚀 Usage

</div>

```
# Start interactive session
adorable

# Configure required settings (API_KEY/BASE_URL/MODEL_ID/TAVILY_API_KEY)
adorable config

# Show help
adorable --help
```

Exit keywords: `exit` / `quit` / `q` / `bye`

<div align="center">

## 🔧 Configuration

</div>

- Default model: `gpt-4o-mini`
- Sources:
  - Interactive: `adorable config` (writes to `~/.adorable/config`)
  - Environment: `API_KEY` or `OPENAI_API_KEY`; `BASE_URL` or `OPENAI_BASE_URL`; `TAVILY_API_KEY`; `ADORABLE_MODEL_ID`

Example (`~/.adorable/config`):

```
API_KEY=sk-xxxx
BASE_URL=https://api.openai.com/v1
TAVILY_API_KEY=tvly_xxxx
MODEL_ID=gpt-4o-mini
```

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
uv run -m adorable_cli.main
# 或：uv run src/adorable_cli/main.py
```

Note: To pin Python version, use `uv sync -p 3.11`.

Using venv:

```
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip setuptools wheel
pip install -r requirements.txt
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

<div align="center">

## 🔒 Privacy & Security

</div>

- The agent may read/write files under the current working directory; review changes in production
- Local memory is stored at `~/.adorable/memory.db`; remove it if not needed

<div align="center">

## 🧭 Developer Guide

</div>

- Style & config: Ruff/Black in `pyproject.toml`, line width `100`
- CLI entrypoints: `src/adorable_cli/__main__.py`, `src/adorable_cli/main.py`
- System prompt: `src/adorable_cli/prompt.py`

<div align="center">

## 📜 License

</div>

- MIT