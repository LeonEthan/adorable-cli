#!/bin/bash

set -e

# Colored output
green() { echo -e "\033[32m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }
red() { echo -e "\033[31m$1\033[0m"; }

# ======================
# 1. Check Python version >= 3.10
# ======================
check_python_version() {
    if command -v python3 &>/dev/null; then
        local ver
        ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
        local major minor
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -gt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -ge 10 ]); then
            green "✅ Current Python version $ver meets >= 3.10"
            return 0
        else
            yellow "⚠️  Current Python version $ver < 3.10, a newer version is required"
            return 1
        fi
    else
        yellow "⚠️  python3 not found"
        return 1
    fi
}

# ======================
# 2. Initialize pyenv (make it available in this script)
# ======================
init_pyenv() {
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"

    if command -v pyenv >/dev/null 2>&1; then
        eval "$(pyenv init --path 2>/dev/null || true)"
        eval "$(pyenv init - 2>/dev/null || true)"
        return 0
    fi

    if [ -d "$PYENV_ROOT" ] && [ -f "$PYENV_ROOT/bin/pyenv" ]; then
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init --path 2>/dev/null || true)"
        eval "$(pyenv init - 2>/dev/null || true)"
        return 0
    fi

    return 1
}

# ======================
# 3. Install and configure pyenv
# ======================
install_pyenv() {
    if [ -d "$HOME/.pyenv" ]; then
        green "✅ pyenv is already installed"
    else
        yellow "📦 Installing pyenv (user-level, no sudo)..."
        curl -fsSL https://pyenv.run | bash
    fi

    if ! init_pyenv; then
        red "❌ Failed to initialize pyenv"
        exit 1
    fi

    # Configure shell
    local shell_rc
    if [ -n "$ZSH_VERSION" ]; then
        shell_rc="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        shell_rc="$HOME/.bashrc"
        [ -f "$HOME/.bash_profile" ] && shell_rc="$HOME/.bash_profile"
    else
        shell_rc="$HOME/.profile"
    fi

    if ! grep -q 'PYENV_ROOT' "$shell_rc" 2>/dev/null; then
        cat >> "$shell_rc" <<EOF

# >>> pyenv initialize >>>
export PYENV_ROOT="\$HOME/.pyenv"
export PATH="\$PYENV_ROOT/bin:\$PATH"
eval "\$(pyenv init --path)"
eval "\$(pyenv init -)"
# <<< pyenv initialize <<<
EOF
        green "✅ Added pyenv configuration to $shell_rc"
    fi
}

# ======================
# 4. Install Python >= 3.10
# ======================
setup_python_with_pyenv() {
    local pyver="3.11.9"  # You can adjust to 3.10.13, 3.12.7, etc.

    yellow "⏳ Installing Python $pyver via pyenv (this may take a few minutes)..."
    pyenv install --skip-existing "$pyver"
    pyenv global "$pyver"

    export PATH="$PYENV_ROOT/shims:$PATH"
    green "✅ Switched to Python $(python3 --version)"
}

# ======================
# 5. Install/Upgrade adorable-cli
# ======================
install_or_upgrade_adorable_cli() {
    # 🔁 Choose the installation source here:
    # Option A: install from PyPI (default)
    local PACKAGE="adorable-cli"

    # Option B: install from GitHub (uncomment the next line and comment the above)
    # local PACKAGE="git+https://github.com/LeonEthan/adorable-cli.git"

    yellow "🔍 Checking if adorable-cli is installed..."

    if pipx list --short 2>/dev/null | grep -q "^adorable-cli\$"; then
        yellow "🔄 adorable-cli is installed; upgrading..."
        if ! pipx upgrade adorable-cli; then
            red "⚠️  Upgrade failed; attempting reinstall..."
            pipx uninstall adorable-cli
            pipx install "$PACKAGE"
        fi
    else
        yellow "📥 Installing adorable-cli..."
        pipx install "$PACKAGE"
    fi
}

# ======================
# 6. Warm up adorable-cli to avoid cold-start slowness
# ======================
warmup_adorable_cli() {
    yellow "🔥 Warming up adorable-cli (--help)..."

    # Ensure PATH contains pipx-installed binaries
    export PATH="$HOME/.local/bin:$PATH"

    if command -v adorable >/dev/null 2>&1; then
        local start_ts end_ts dur
        start_ts=$(date +%s)
        if adorable --help >/dev/null 2>&1; then
            end_ts=$(date +%s)
            dur=$((end_ts - start_ts))
            green "✅ Warm-up complete in ${dur}s"
        else
            yellow "⚠️  Warm-up failed via 'adorable'; trying 'pipx run'"
            pipx run adorable-cli --help >/dev/null 2>&1 || yellow "⚠️  Warm-up via pipx run failed (ignored)"
        fi
    else
        yellow "⚠️  'adorable' not found on PATH; trying 'pipx run'"
        pipx run adorable-cli --help >/dev/null 2>&1 || yellow "⚠️  Warm-up via pipx run failed (ignored)"
    fi
}

# ======================
# Main flow
# ======================
main() {
    green "🚀 Starting automatic install/upgrade of adorable-cli..."

    # 1. Ensure Python >= 3.10
    if ! check_python_version; then
        install_pyenv
        setup_python_with_pyenv
    fi

    # 2. Ensure correct Python and PATH
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/shims:$HOME/.local/bin:$PATH"

    # 3. Install pipx (user-level)
    yellow "📦 Ensuring pipx is installed..."
    python3 -m pip install --user --upgrade pipx
    python3 -m pipx ensurepath
    export PATH="$HOME/.local/bin:$PATH"

    # 4. Install or upgrade adorable-cli
    install_or_upgrade_adorable_cli

    # 5. Warm up adorable-cli to reduce user's first-run latency
    warmup_adorable_cli

    green "🎉 adorable-cli installed or upgraded successfully!"
    yellow "💡 Run the following commands to apply the environment (or reopen your terminal):"
    if [ -f "$HOME/.zshrc" ]; then
        echo "   source ~/.zshrc"
    else
        echo "   source ~/.bashrc"
    fi
    echo "   Then run: adorable --help"
}

main "$@"