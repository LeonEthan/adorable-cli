#!/usr/bin/env bash
set -euo pipefail

# 默认安装的包名，可通过环境变量覆盖：PKG_NAME="your-package"
PKG_NAME=${PKG_NAME:-adorable-cli}

log_info() { printf "\033[1;34m[i]\033[0m %s\n" "$*"; }
log_warn() { printf "\033[1;33m[!]\033[0m %s\n" "$*"; }
log_err()  { printf "\033[1;31m[x]\033[0m %s\n" "$*"; }

ensure_path_local_bin() {
  # 确保当前会话可以找到 pipx 安装到 ~/.local/bin 的命令
  if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    export PATH="$HOME/.local/bin:$PATH"
  fi
}

install_pipx_if_needed() {
  if command -v pipx >/dev/null 2>&1; then
    log_info "pipx 已存在"
    return 0
  fi

  uname_s=$(uname -s 2>/dev/null || echo "")

  case "$uname_s" in
    Darwin)
      if command -v brew >/dev/null 2>&1; then
        log_info "使用 Homebrew 安装 pipx"
        brew install pipx
      else
        log_warn "未检测到 Homebrew，改用 pip 用户安装 pipx"
        python3 -m pip install --user -U pipx
        ensure_path_local_bin
      fi
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        log_info "使用 apt 安装 pipx"
        sudo apt-get update -y
        sudo apt-get install -y pipx
      elif command -v dnf >/dev/null 2>&1; then
        log_info "使用 dnf 安装 pipx"
        sudo dnf install -y pipx
      elif command -v yum >/dev/null 2>&1; then
        log_info "使用 yum 安装 pipx"
        sudo yum install -y pipx || true
      elif command -v pacman >/dev/null 2>&1; then
        log_info "使用 pacman 安装 pipx"
        sudo pacman -Sy --noconfirm pipx
      else
        log_warn "未检测到常见包管理器，改用 pip 用户安装 pipx"
        python3 -m pip install --user -U pipx
        ensure_path_local_bin
      fi
      ;;
    *)
      log_warn "未识别的系统类型（$uname_s），尝试使用 pip 用户安装 pipx"
      python3 -m pip install --user -U pipx
      ensure_path_local_bin
      ;;
  esac

  if ! command -v pipx >/dev/null 2>&1; then
    # 作为兜底：pipx 可能已安装但 PATH 未更新
    ensure_path_local_bin
  fi

  if command -v pipx >/dev/null 2>&1; then
    log_info "执行 pipx ensurepath（可能需要重新打开终端）"
    pipx ensurepath || true
  else
    log_err "pipx 安装失败，请手动安装后重试： https://pypa.github.io/pipx/"
    exit 1
  fi
}

install_or_upgrade_package() {
  # 在严格模式下，使用带默认值的参数展开以防未绑定变量
  local pkg="${PKG_NAME:-adorable-cli}"

  if pipx list 2>/dev/null | grep -q "$pkg"; then
    log_info "检测到已安装，执行升级： pipx upgrade $pkg"
    pipx upgrade "$pkg" || {
      log_warn "升级失败，尝试重新安装（卸载后安装）"
      pipx uninstall "$pkg" || true
      pipx install "$pkg"
    }
  else
    log_info "安装 $pkg（隔离环境，推荐方式）"
    pipx install "$pkg"
  fi
}

post_install_hint() {
  cat <<'EOF'

安装完成！可用命令：

  adorable           # 进入交互式会话
  adorable config    # 设置 API_KEY/BASE_URL/MODEL_ID/TAVILY_API_KEY
  adorable --help    # 查看帮助

注意：首次安装后如命令不可用，尝试重新打开终端或执行：
  export PATH="$HOME/.local/bin:$PATH"

更多信息见 README：配置默认模型（gpt-4o-mini）、本地记忆路径 ~/.adorable/memory.db 等。
EOF
}

main() {
  log_info "检查/安装 pipx"
  install_pipx_if_needed

  log_info "安装或升级 adorable-cli"
  install_or_upgrade_package

  # 显示已安装版本信息（优先使用命令名，其次使用 pipx run）
  if command -v adorable >/dev/null 2>&1; then
    log_info "已安装版本：$(adorable --version || echo '未知')"
  else
    log_info "已安装版本：$(pipx run "${PKG_NAME:-adorable-cli}" --version || echo '未知')"
  fi

  post_install_hint
}

main "$@"