<div align="center">

# 🐱 Adorable CLI

### 基于 Agno 的命令行智能体

<p align="center">
  <a href="#quick-start">快速安装</a> •
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

基于 Agno 的命令行智能体。面向“以任务为中心”的交互：你提出目标，智能体按“信息收集 → 执行 → 验证”闭环推进，必要时用待办清单（todos）管理复杂任务。

> 支持 OpenAI 兼容 API。

<div align="center">
  <a id="features"></a>
  
  ## 🧩 特性
</div>

- 交互式会话，支持 Markdown 输出与流式显示
- 计划 → 执行 → 验证闭环，适配多步骤任务
- 多工具协作：网页检索、网页抓取、文件读写、计算、记忆
- 本地持久化记忆（`~/.adorable/memory.db`），跨会话延续上下文
- 简单配置即用，支持自定义模型与兼容服务

<div align="center">
  <a id="quick-start"></a>
  
  ## ⚡ 快速安装

  | 方法 | 命令 | 适用场景 |
  |---|---|---|
  | **🐍 pipx** | `pipx install adorable-cli` | **✅ 推荐** - Linux/macOS |
  | **🚗 一键** | `curl -fsSL https://leonethan.github.io/adorable-cli/install.sh \| bash` | 非程序员 - Linux/macOS |
  | **📦 pip** | `pip install adorable-cli` | 传统 Python 环境 |
</div>

> 首次运行会引导配置四个变量：`API_KEY`、`BASE_URL`、`MODEL_ID`、`TAVILY_API_KEY`，保存到 `~/.adorable/config`（KEY=VALUE）。随时可运行 `adorable config` 修改。

<div align="center">
  <a id="usage"></a>
  
  ## 🚀 用法速览
</div>

```
# 进入交互式会话
adorable

# 配置四个必需项（API_KEY/BASE_URL/MODEL_ID/TAVILY_API_KEY）
adorable config

# 查看帮助
adorable --help
```

退出指令：`exit` / `quit` / `q` / `bye`

<div align="center">
  <a id="config"></a>
  
  ## 🔧 配置
</div>

- 默认模型：`gpt-4o-mini`
- 配置来源：
  - 交互式：`adorable config`（写入 `~/.adorable/config`）
  - 环境变量：`API_KEY` 或 `OPENAI_API_KEY`；`BASE_URL` 或 `OPENAI_BASE_URL`；`TAVILY_API_KEY`；`ADORABLE_MODEL_ID`

示例（`~/.adorable/config`）：

```
# OpenAI 兼容的通用变量
API_KEY=sk-xxxx
BASE_URL=https://api.openai.com/v1

# 指定模型（可覆盖默认）
MODEL_ID=gpt-4o-mini

# 可选：使能联网检索
TAVILY_API_KEY=tvly-xxxx
```

<div align="center">
  <a id="capabilities"></a>
  
  ## 🧠 能力矩阵
</div>

- 推理与规划：`ReasoningTools`（结构化推理、计划步骤）
- 计算校验：`CalculatorTools`（数值计算与结果校验）
- 网页检索：`TavilyTools`（联网检索，需要 `TAVILY_API_KEY`）
- 网页抓取：`Crawl4aiTools`（访问网址并抽取内容）
- 文件操作：`FileTools`（搜索/读取/写入；作用域限定为启动目录 `cwd`）
- 记忆存储：`MemoryTools` + `SqliteDb`（`~/.adorable/memory.db`）

系统提示与待办清单规范见 `src/adorable_cli/prompt.py`。

<div align="center">
  <a id="examples"></a>
  
  ## 🧪 示例提示词
</div>

- “帮我总结最近 Python 的新特性并列出示例代码”
- “从当前项目的 `src` 目录读取代码，生成一份详细的 README 并保存到项目根目录”

<div align="center">
  <a id="source"></a>
  
  ## 🛠️ 源码运行（uv/venv）
</div>

使用 uv（推荐）：

```
uv sync
uv run adorable --help
uv run adorable
```

备注：如需指定 Python 版本，可使用 `uv sync -p 3.11`。

使用 venv：

```
python -m venv .venv
source .venv/bin/activate
pip install -e .
adorable --help
```

<div align="center">
  <a id="build"></a>
  
  ## 📦 构建与发布
</div>

- 入口点：见 `pyproject.toml`（`adorable`、`ador`）
- PyPI 发布：推送 `v*` 标签或手动触发后在 CI 构建并发布
  - 发布命令：`git tag vX.Y.Z && git push origin vX.Y.Z`
- 自动版本管理：`release-please` 基于约定式提交生成发布 PR，合并后打标签
  - 常见类型：`feat:`、`fix:`、`perf:`、`refactor:`、`docs:`
- 本地构建与安装：
  - `python -m build`（输出 `dist/*.tar.gz`、`dist/*.whl`）
  - `python -m pip install dist/*.whl`

<div align="center">
  <a id="contributing"></a>
  
  ## 🤝 贡献指南
</div>

- 欢迎提交 PR 与 Issue；建议遵循约定式提交（Conventional Commits），以便 `release-please` 自动生成发布记录。
- 开发建议：
  - 使用 `pipx` 或虚拟环境进行开发；
  - 按 `pyproject.toml` 的风格配置（Ruff/Black，行宽 `100`）。
  - 运行 `adorable --help` 快速核对命令行为。

<div align="center">
  <a id="faq"></a>
  
  ## 💡 常见问题与排错
</div>

- 鉴权失败/模型不可用：
  - 检查 `API_KEY`/`BASE_URL`；确认 `MODEL_ID` 可用
- 检索质量低：
  - 设置 `TAVILY_API_KEY`；在指令中明确检索目标与范围
- PEP 668（系统环境不允许写入）：
  - 使用 `pipx` 安装以获得隔离环境；这是跨平台 CLI 的最佳实践

<div align="center">
  <a id="privacy"></a>
  
  ## 🔒 隐私与安全
</div>

- 智能体可能读取/写入当前工作目录（启动目录）下的文件；生产环境谨慎使用并审核改动
- 本地记忆存储在 `~/.adorable/memory.db`；不需要时可手动删除

<div align="center">
  <a id="dev-guide"></a>
  
  ## 🧭 开发者指南
</div>

- 风格与配置：已在 `pyproject.toml` 配置 Ruff/Black，行宽 `100`
- CLI 入口：`src/adorable_cli/__main__.py`、`src/adorable_cli/main.py`
- 系统提示：`src/adorable_cli/prompt.py`

<div align="center">
  <a id="license"></a>
  
  ## 📜 许可证
</div>

- MIT