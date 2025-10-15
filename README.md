# Adorable CLI

Adorable CLI 提供跨平台的单文件二进制，通过 NPM 安装并运行。

## 支持平台

- macOS: `darwin-arm64`、`darwin-x64`
- Linux: `linux-x64`
- Windows: `win32-x64`

当前不支持：

- Linux arm64（如 Ubuntu/CentOS on ARM、AWS Graviton、树莓派 64 位）

如果你在 Linux arm64 上使用，请选择以下替代方式：

- 使用 x64 环境（桌面或云主机）；或
- 使用 Docker 运行：在 x64 容器/宿主上运行；或
- 从源码运行：在本地创建虚拟环境并安装依赖

示例（源码运行）：

```
uv venv .venv -p 3.11
uv pip install -p .venv/bin/python -U pip setuptools wheel
uv export --format requirements-txt -o requirements.lock.txt
uv pip sync -p .venv/bin/python requirements.lock.txt
.venv/bin/python src/adorable_cli/main.py
```

## 发布与构建

- 发布工作流仅在推送 `v*` 标签时触发。
- 平台二进制通过各自的子包发布到 NPM：
  - `adorable-cli-darwin-arm64`
  - `adorable-cli-darwin-x64`
  - `adorable-cli-linux-x64`
  - `adorable-cli-win32-x64`

## 常见问题

- 在不支持的平台上运行时，CLI 会提示“未找到平台二进制”或“不支持当前平台”，请参考上面替代方式。