<div align="center">

<img src="assets/adorable-ai-logo.png" alt="adorable logo" width="220" />

# Adorable CLI - 基于 Agno 构建的 Deep Agent

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
</p>

<p align="center">
  <a href="#quick-install">快速安装</a> •
  <a href="#features">特性</a> •
  <a href="#usage">用法</a> •
  <a href="#configuration">配置</a>
</p>
  <a href="README.md"><img src="https://img.shields.io/badge/EN-English-blue" alt="English"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/🇨🇳_中文-red" alt="中文"></a>
</p>

</div>

---

**Adorable** 是一个专为复杂、长周期任务设计的 Deep Agent，基于 [Agno](https://github.com/agno-agi/agno) 框架构建。它通过持续的**交叉推理与行动**模式运行——每一步之前先思考，精确执行，分析结果——从而可靠地处理研究、编程和系统自动化任务。

> 基于 Agno 的智能体架构，具备持久化记忆、工具编排能力，支持 OpenAI 兼容 API。

---

<div align="center">
  <a id="features"></a>
  
  ## 🧩 特性
</div>

- **Deep Agent**：基于 Agno 框架构建，具备规划、网络搜索、编程和文件操作能力。
- **交叉思维**：持续的**思考 → 行动 → 分析**循环——每步之前先推理，从不猜测，验证所有假设。
- **持久化记忆**：使用 SQLite (`~/.adorable/memory.db`) 和会话摘要在长会话中保持上下文。
- **多模态工具集**：
  - **规划**：推理引擎与待办清单管理。
  - **文件操作**：文件读取、编辑与搜索。
  - **网络搜索**：深度网络搜索 (DuckDuckGo) 与网页抓取 (Crawl4AI)。
  - **编程**：Python 脚本与 Shell 命令。
  - **视觉**：图像分析视觉能力。
- **交互式 UI**：功能丰富的终端界面，支持历史记录、自动补全和快捷键。

<div align="center">
  <a id="quick-install"></a>
  
  ## ⚡ 快速安装

  我们推荐使用 [uv](https://github.com/astral-sh/uv) 来安装和管理 Adorable CLI。

  ### 安装

  ```bash
  uv tool install --python 3.13 adorable-cli
  ```

  ### 升级

  ```bash
  uv tool upgrade adorable-cli --no-cache
  ```

  如果升级后遇到依赖缺失（如 `ModuleNotFoundError`），可强制重装：

  ```bash
  uv tool upgrade adorable-cli --reinstall --no-cache
  ```
</div>

> 首次运行会引导配置 `API_KEY`、`BASE_URL`、`MODEL_ID`，保存到 `~/.adorable/config`。随时可运行 `ador config` 修改。

<div align="center">
  <a id="platform"></a>
  
  ## 🖥 平台支持
</div>

- 系统：macOS、Linux x86_64
- 架构：`x86_64`；Linux `arm64` 暂不支持
- Python：`>= 3.10`（建议 `3.11`）
- Linux glibc：`>= 2.28`（例如 Debian 12、Ubuntu 22.04+、CentOS Stream 9）

<div align="center">
  <a id="usage"></a>
  
## 🚀 用法速览
</div>

```bash
# 进入交互式会话
adorable
# 或使用别名
ador

# 配置设置
ador config

# 查看帮助
ador --help
```

### CLI 命令

- `ador` / `adorable`：进入交互聊天
- `ador config`：配置 API 密钥和模型
- `ador version`：显示 CLI 版本

### 交互快捷键
- `Enter`：提交消息
- `Alt+Enter` / `Ctrl+J`：插入换行
- `@`：文件路径补全
- `/`：命令补全（如 `/help`，`/clear`）
- `Ctrl+D` / `exit`：退出会话
- `Ctrl+Q`：快速退出

### 全局选项

- `--model <ID>`：主模型 ID（例如 `gpt-4o`）
- `--base-url <URL>`：OpenAI 兼容的 Base URL
- `--api-key <KEY>`：API 密钥
- `--debug`：启用调试日志
- `--plain`：禁用彩色输出

示例：

```bash
ador --api-key sk-xxxx --model gpt-4o chat
```

<div align="center">

## 🔧 配置

</div>

- **配置文件**：`~/.adorable/config`
- **环境变量**：
  - `OPENAI_API_KEY` / `API_KEY`
  - `OPENAI_BASE_URL` / `BASE_URL`
  - `DEEPAGENTS_MODEL_ID` / `MODEL_ID`

示例（`~/.adorable/config`）：

```ini
API_KEY=sk-xxxx
BASE_URL=https://api.openai.com/v1
MODEL_ID=gpt-4o
```

<div align="center">

## 🧠 Capabilities

</div>

- **规划**：`ReasoningTools` 用于策略思考；`TodoTools` 用于任务追踪。
- **研究**：`DuckDuckGoTools` 用于搜索；`Crawl4aiTools` 用于抓取；`FileTools` 用于本地上下文。
- **执行**：`PythonTools` 用于逻辑/数据处理；`ShellTools` 用于系统操作。
- **感知**：`ImageUnderstandingTool` 用于视觉输入。

完整系统提示词与指南见 `src/adorable_cli/agent/prompts.py`。

<div align="center">

## 🧪 示例提示词

</div>

- “调研量子计算的现状并撰写一份 Markdown 总结报告。”
- “克隆 'requests' 仓库，分析目录结构并绘制图表。”
- “为这些 CSV 文件规划并执行数据迁移脚本。”

<div align="center">
  <a id="source"></a>
  
  ## 🛠️ 源码运行（uv/venv）
</div>
