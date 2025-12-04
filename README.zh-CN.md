<div align="center">

<img src="assets/adorable-ai-logo.png" alt="deepagents logo" width="220" />

# DeepAgents CLI - 一个通用的“深度工作”智能体

<p align="center">
  <a href="#quick-install">快速安装</a> •
  <a href="#features">特性</a> •
  <a href="#usage">用法</a> •
  <a href="#build">构建</a> •
  <a href="#contributing">贡献</a>
  <br />
  <br />
  <a href="README.md"><img src="https://img.shields.io/badge/EN-English-blue" alt="English"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/🇨🇳_中文-red" alt="中文"></a>
</p>

</div>

---

**DeepAgents** 是一个专为复杂、长周期任务设计的命令行自主智能体。它基于 [Agno](https://github.com/agno-agi/agno) 构建，遵循严格的 **计划 → 执行 → 记录 → 验证** 闭环，能够可靠地处理深度研究、代码开发和系统自动化任务。

> 支持 OpenAI 兼容 API。

<div align="center">
  <a id="features"></a>
  
  ## 🧩 特性
</div>

- **通用自主智能体**：具备规划、研究、编程和复杂执行能力。
- **深度工作闭环**：系统化地制定计划、执行任务、记录发现并验证结果。
- **持久化记忆**：利用本地文件系统和 SQLite (`~/.deepagents/memory.db`) 在长会话中保持状态。
- **多模态工具集**：
  - **规划**：推理引擎与待办清单（Todo list）管理。
  - **研究**：深度联网搜索 (Tavily) 与网页抓取 (Crawl4AI)。
  - **执行**：Python 脚本编写与 Shell 命令执行。
  - **感知**：图像分析视觉能力。
- **交互式 UI**：功能丰富的终端界面，支持历史记录、自动补全和快捷键。

<div align="center">
  <a id="quick-install"></a>
  
  ## ⚡ 快速安装

  | 方法 | 命令 | 适用场景 |
  |---|---|---|
  | **🚗 一键** | `curl -fsSL https://leonethan.github.io/deepagents-cli/install.sh | bash` | **✅ 首推** - Linux/macOS |
  | **🐍 pipx** | `pipx install deepagents-cli` | 隔离 CLI 环境 - Linux/macOS |
  | **📦 pip** | `pip install deepagents-cli` | 传统 Python 环境 |
</div>

> 首次运行会引导配置 `API_KEY`、`BASE_URL`、`MODEL_ID`、`TAVILY_API_KEY`，保存到 `~/.deepagents/config`。随时可运行 `da config` 修改。

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
deepagents
# 或使用别名
da

# 配置设置
da config

# 查看帮助
da --help
```

### CLI 命令

- `da` / `deepagents`：进入交互聊天
- `da config`：配置 API 密钥和模型
- `da version`：显示 CLI 版本

### 交互快捷键
- `Enter`：提交消息
- `Alt+Enter` / `Ctrl+J`：插入换行
- `@`：文件路径补全
- `/`：命令补全（如 `/help`，`/clear`）
- `Ctrl+Q`：快速退出

### 全局选项

- `--model <ID>`：主模型 ID（例如 `gpt-4o`）
- `--base-url <URL>`：OpenAI 兼容的 Base URL
- `--api-key <KEY>`：API 密钥
- `--debug`：启用调试日志
- `--plain`：禁用彩色输出

示例：

```bash
da --api-key sk-xxxx --model gpt-4o chat
```

<div align="center">
  <a id="config"></a>
  
  ## 🔧 配置
</div>

- **配置文件**：`~/.deepagents/config`
- **环境变量**：
  - `DEEPAGENTS_API_KEY` / `API_KEY`
  - `DEEPAGENTS_BASE_URL` / `BASE_URL`
  - `DEEPAGENTS_MODEL_ID`
  - `TAVILY_API_KEY`

示例（`~/.deepagents/config`）：

```ini
API_KEY=sk-xxxx
BASE_URL=https://api.openai.com/v1
TAVILY_API_KEY=tvly_xxxx
MODEL_ID=gpt-4o
```

<div align="center">
  <a id="capabilities"></a>
  
  ## 🧠 能力矩阵
</div>

- **规划**：`ReasoningTools` 用于策略思考；`session_state.todos` 用于任务追踪。
- **研究**：`TavilyTools` 用于搜索；`Crawl4aiTools` 用于抓取；`FileTools` 用于本地上下文。
- **执行**：`PythonTools` 用于逻辑/数据处理；`ShellTools` 用于系统操作。
- **感知**：`ImageUnderstandingTool` 用于视觉输入。

完整系统提示词与指南见 `src/deepagents_cli/prompt.py`。

<div align="center">
  <a id="examples"></a>
  
  ## 🧪 示例提示词
</div>

- “调研量子计算的现状并撰写一份 Markdown 总结报告。”
- “克隆 'requests' 仓库，分析目录结构并绘制图表。”
- “为这些 CSV 文件规划并执行数据迁移脚本。”

<div align="center">
  <a id="source"></a>
  
  ## 🛠️ 源码运行（uv/venv）
</div>
