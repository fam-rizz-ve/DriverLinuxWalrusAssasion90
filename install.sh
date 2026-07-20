#!/usr/bin/env bash
# ============================================================================
# install.sh — Walrus Assassin 90 LCD Driver Installer
# ============================================================================
# Detects your Linux distro, installs dependencies, sets up a venv,
# installs the udev rule, and enables the systemd user service.
#
# Usage: bash install.sh
# ============================================================================

set -euo pipefail

# ---- Constants -----------------------------------------------------------
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DRIVER="${REPO_DIR}/src/walrus_lcd.py"
SRC_CONFIG_TOOL="${REPO_DIR}/src/config_walrus.py"
SRC_CONFIG_EXAMPLE="${REPO_DIR}/src/config.example.toml"
UDEV_RULE="${REPO_DIR}/udev/99-cooler-lcd.rules"
SERVICE_TEMPLATE="${REPO_DIR}/systemd/cooler-lcd.service"
INSTALL_DIR="${HOME}/.local/share/walrus-lcd"
BIN_DIR="${HOME}/.local/bin"
CONFIG_PATH="${INSTALL_DIR}/config.toml"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_NAME="cooler-lcd.service"

# ---- Colors --------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'  # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ---- Guard Clauses -------------------------------------------------------
[[ -f "${SRC_DRIVER}" ]]    || fail "Driver not found: ${SRC_DRIVER}"
[[ -f "${SRC_CONFIG_TOOL}" ]] || fail "Config tool not found: ${SRC_CONFIG_TOOL}"
[[ -f "${SRC_CONFIG_EXAMPLE}" ]] || fail "Config example not found: ${SRC_CONFIG_EXAMPLE}"
[[ -f "${UDEV_RULE}" ]]     || fail "Udev rule not found: ${UDEV_RULE}"
[[ -f "${SERVICE_TEMPLATE}" ]] || fail "Service template not found: ${SERVICE_TEMPLATE}"

# ---- Step 1: Detect Distro & Install System Deps -------------------------
detect_and_install_deps() {
    info "Detecting Linux distribution..."

    if command -v pacman &>/dev/null; then
        PKG_MGR="pacman"
        info "Detected Arch/CachyOS (pacman)"
        sudo pacman -S --needed --noconfirm python python-pip hidapi lm-sensors 2>/dev/null \
            || warn "Some packages may already be installed"
    elif command -v apt &>/dev/null; then
        PKG_MGR="apt"
        info "Detected Ubuntu/Debian (apt)"
        sudo apt update -qq
        sudo apt install -y python3 python3-pip python3-venv hidapi lm-sensors 2>/dev/null \
            || warn "Some packages may already be installed"
    elif command -v dnf &>/dev/null; then
        PKG_MGR="dnf"
        info "Detected Fedora (dnf)"
        sudo dnf install -y python3 python3-pip hidapi lm-sensors 2>/dev/null \
            || warn "Some packages may already be installed"
    else
        warn "Unknown package manager. Install manually: python3, pip, hidapi, lm-sensors"
        PKG_MGR="unknown"
    fi

    ok "System dependencies ready"
}

# ---- Step 2: Create Install Directory & Copy Driver ----------------------
install_driver() {
    info "Installing driver to ${INSTALL_DIR}..."
    mkdir -p "${INSTALL_DIR}"
    cp "${SRC_DRIVER}" "${INSTALL_DIR}/walrus_lcd.py"
    chmod +x "${INSTALL_DIR}/walrus_lcd.py"
    ok "Driver installed: ${INSTALL_DIR}/walrus_lcd.py"
}

# ---- Step 2b: Install Config Tool & Symlink ------------------------------
install_config_tool() {
    info "Installing config tool to ${INSTALL_DIR}..."
    cp "${SRC_CONFIG_TOOL}" "${INSTALL_DIR}/config_walrus.py"
    chmod +x "${INSTALL_DIR}/config_walrus.py"
    cp "${SRC_CONFIG_EXAMPLE}" "${INSTALL_DIR}/config.example.toml"

    mkdir -p "${BIN_DIR}"
    ln -sf "${INSTALL_DIR}/config_walrus.py" "${BIN_DIR}/walrus-config"

    if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
        warn "~/.local/bin is not in your PATH"
        warn "Add this to your ~/.bashrc:"
        warn "  export PATH=\"${HOME}/.local/bin:\${PATH}\""
    else
        ok "Config tool installed: ${BIN_DIR}/walrus-config"
    fi
}

# ---- Step 3: Create Virtual Environment & Install Python Deps ------------
setup_venv() {
    info "Creating virtual environment..."
    python3 -m venv "${INSTALL_DIR}/venv" 2>/dev/null \
        || python3 -m venv "${INSTALL_DIR}/venv" --without-pip 2>/dev/null \
        || fail "Failed to create venv. Install python3-venv."

    local VENV_PIP="${INSTALL_DIR}/venv/bin/pip"
    local VENV_PY="${INSTALL_DIR}/venv/bin/python"

    # Ensure pip is available
    if [[ ! -f "${VENV_PIP}" ]]; then
        warn "pip not found in venv, bootstrapping..."
        "${VENV_PY}" -m ensurepip --upgrade 2>/dev/null \
            || curl -sS https://bootstrap.pypa.io/get-pip.py | "${VENV_PY}" 2>/dev/null \
            || fail "Cannot install pip in venv"
    fi

    info "Installing Python packages..."
    "${VENV_PIP}" install --quiet psutil pynvml 2>/dev/null \
        || fail "Failed to install Python packages"

    ok "Virtual environment ready: ${INSTALL_DIR}/venv"
}

# ---- Step 4: Install udev Rule -------------------------------------------
install_udev_rule() {
    info "Installing udev rule (requires sudo)..."
    sudo cp "${UDEV_RULE}" /etc/udev/rules.d/99-cooler-lcd.rules
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    ok "Udev rule installed and reloaded"
}

# ---- Step 5: Install & Enable systemd User Service -----------------------
install_systemd_service() {
    info "Installing systemd user service..."
    mkdir -p "${SERVICE_DIR}"

    local VENV_PY="${INSTALL_DIR}/venv/bin/python"

    # Substitute placeholders in service template
    sed \
        -e "s|__INSTALL_DIR__|${INSTALL_DIR}|g" \
        -e "s|__VENV_PYTHON__|${VENV_PY}|g" \
        "${SERVICE_TEMPLATE}" > "${SERVICE_DIR}/${SERVICE_NAME}"

    systemctl --user daemon-reload
    systemctl --user enable --now "${SERVICE_NAME}" 2>/dev/null \
        || warn "Service enable failed — you may need to log out and back in"

    ok "Service installed and started"
}

# ---- Step 5b: Interactive Configuration ----------------------------------
interactive_config() {
    echo ""
    info "You can now configure the driver interactively."
    info "Settings: temperature source (CPU/GPU/auto), refresh interval, clamp max."
    echo ""
    read -r -p "Configure now? [Y/n] " reply < /dev/tty
    if [[ "${reply}" =~ ^[Nn]([Oo][Ee])?$ ]]; then
        info "Skipping. Configure later with: ${CYAN}walrus-config${NC}"
        return
    fi
    python3 "${INSTALL_DIR}/config_walrus.py" < /dev/tty || \
        warn "Config tool exited with error — you can retry later with: walrus-config"
}

# ---- Step 6: Enable Lingering (optional, for headless sessions) ----------
enable_lingering() {
    if command -v loginctl &>/dev/null; then
        info "Enabling loginctl lingering for user service persistence..."
        sudo loginctl enable-linger "${USER}" 2>/dev/null \
            || warn "Could not enable lingering (non-critical)"
    fi
}

# ---- Main ----------------------------------------------------------------
main() {
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║   🐋 Walrus Assassin 90 LCD Driver Installer   ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    detect_and_install_deps
    install_driver
    install_config_tool
    setup_venv
    install_udev_rule
    install_systemd_service
    interactive_config
    enable_lingering

    echo ""
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✅ Installation complete!${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Driver:     ${CYAN}${INSTALL_DIR}/walrus_lcd.py${NC}"
    echo -e "  Venv:       ${CYAN}${INSTALL_DIR}/venv${NC}"
    echo -e "  Service:    ${CYAN}${SERVICE_NAME}${NC}"
    echo -e "  Config tool: ${CYAN}${BIN_DIR}/walrus-config${NC}"
    echo ""
    echo -e "  ${BOLD}Configure anytime:${NC} ${CYAN}walrus-config${NC}"
    echo ""
    echo -e "  ${BOLD}Quick commands:${NC}"
    echo -e "    Check status:  ${CYAN}make status${NC}"
    echo -e "    View logs:     ${CYAN}make logs${NC}"
    echo -e "    Test manually: ${CYAN}make test${NC}"
    echo -e "    Stop:          ${CYAN}make stop${NC}"
    echo ""
}

main "$@"
