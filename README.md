# Adorable CLI

一个基于 Agno 的命令行智能体工具，支持交互式对话、计划/执行/验证闭环、多工具协作（网页检索、网页抓取、文件读写、计算、记忆）。通过 NPM 提供跨平台单文件二进制，也支持源码运行。

## 快速开始

- 全局安装并运行：
  - `npm i -g adorable-cli`
  - 运行 `adorable` 或 `ador`
- 一次性运行（无需全局安装）：
  - `npx -p adorable-cli adorable`

首次运行会提示配置 `API_KEY` 与 `BASE_URL`，保存到 `~/.adorable_config`（KEY=VALUE 格式）。你也可以随时运行 `adorable config` 修改配置。

## 用法

- `adorable`：进入交互式会话（支持 Markdown 输出、流式显示、输入历史上/下箭头回溯），退出指令：`exit`/`quit`/`q`/`bye`
- `adorable config`：配置 `API_KEY`、`BASE_URL`、`TAVILY_API_KEY`、`MODEL_ID`
- `adorable --help`：查看帮助

### 示例

- 问答类：
  - “帮我总结最近 Python 的新特性并列出示例代码”
- 多步骤任务：
  - “从当前项目的 `src` 目录读取代码，生成一份详细的 README 并保存到项目根目录”
  - 智能体会按“信息收集 → 执行操作 → 验证结果”的流程进行，并在需要时基于待办清单（todos）管理步骤。

## 模型与配置

- 默认模型：`gpt-4o-mini`
- 支持使用 OpenAI 兼容的 API 服务（例如官方 OpenAI、兼容的第三方或自建服务）。
- 配置方式：
  - 运行 `adorable config` 按提示输入，保存到 `~/.adorable_config`
  - 或使用环境变量：
    - `API_KEY` 或 `OPENAI_API_KEY`
    - `BASE_URL` 或 `OPENAI_BASE_URL`
    - `TAVILY_API_KEY`（可选，用于提升网页检索质量）
    - `ADORABLE_MODEL_ID`（可选，覆盖默认模型）

示例配置文件（`~/.adorable_config`）：

```
API_KEY=sk-xxxx
BASE_URL=https://api.openai.com/v1
TAVILY_API_KEY=tvly_xxxx
MODEL_ID=gpt-4o-mini
```

说明：若环境变量已设置，运行时也会识别（两者皆可）。

## 能力与工具

- 推理与规划：`ReasoningTools`（结构化推理、计划步骤）
- 计算校验：`CalculatorTools`（数值计算与结果校验）
- 网页检索：`TavilyTools`（联网检索，建议设置 `TAVILY_API_KEY`）
- 网页抓取：`Crawl4aiTools`（访问网址并抽取内容）
- 文件操作：`FileTools`（搜索/读取/写入文件；作用域限定为启动目录 `cwd`）
- 记忆存储：`MemoryTools` + `SqliteDb`（本地持久化用户记忆，路径：`~/.adorable_memory.db`）

CLI 的系统提示（system prompt）在 `src/adorable_cli/prompt.py` 中，并包含“何时使用待办清单（todos）”的规范与示例。复杂任务会在会话中以清单形式进行管理。

## 平台支持

- 支持：
  - macOS：`darwin-arm64`、`darwin-x64`
  - Linux：`linux-x64`
  - Windows：`win32-x64`
- 不支持：
  - Linux arm64（如 Ubuntu/CentOS on ARM、AWS Graviton、树莓派 64 位）

在不支持的平台上运行时，CLI 会提示“不支持当前平台”。

## 源码运行（Python ≥ 3.10）

适用于需要在不支持平台或开发环境下运行：

```
# 使用 uv（推荐）
uv venv .venv -p 3.11
uv pip install -p .venv/bin/python -U pip setuptools wheel
uv export --format requirements-txt -o requirements.lock.txt
uv pip sync -p .venv/bin/python requirements.lock.txt
.venv/bin/python -m adorable_cli.main
# 或：.venv/bin/python src/adorable_cli/main.py
```

不使用 uv 时：

```
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip setuptools wheel
pip install -r requirements.txt  # 如无锁文件，可直接 pip 安装
python -m adorable_cli.main
```

## Docker（替代方案）

目前仓库未提供官方 Dockerfile。你可在 x64 宿主/容器中按“源码运行”方式执行，确保容器内具备 Python 3.10+、网络与必要环境变量（`API_KEY`、`BASE_URL` 等）。

## 发布与构建

- 发布工作流仅在推送 `v*` 标签时触发。
- 平台二进制通过各自的子包发布到 NPM：
  - `adorable-cli-darwin-arm64`
  - `adorable-cli-darwin-x64`
  - `adorable-cli-linux-x64`
  - `adorable-cli-win32-x64`

主包 `adorable-cli` 暴露可执行：

- `adorable`、`ador`（都指向同一入口 `bin/adorable.js`）

## 常见问题与排错

- 二进制未找到：
  - 请确认安装了主包，并且运行的是受支持的平台；或在源码模式下运行。
- 鉴权失败/模型不可用：
  - 检查 `API_KEY`/`BASE_URL` 是否正确；`MODEL_ID` 是否可用。
- 网页检索质量低：
  - 设置 `TAVILY_API_KEY`，并在指令中明确检索目标与范围。
- 不支持的架构：
  - Linux arm64 不支持。请使用 x64 环境或按“源码运行”方式运行。

## 隐私与安全

- 智能体可能读取/写入当前工作目录下的文件（作用域：启动目录）。请在生产环境谨慎使用，并审核其输出与改动。
- 本地记忆存储于 `~/.adorable_memory.db`，用于跨会话保留关键信息。若不需要可手动删除该文件。

## 许可证

MIT