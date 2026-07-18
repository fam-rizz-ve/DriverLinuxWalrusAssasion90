#!/usr/bin/env bash
# ============================================================================
# uninstall.sh — Walrus Assassin 90 LCD Driver Uninstaller
# ============================================================================
# Stops the service, removes the udev rule, service file, and installed files.
#
# Usage: bash uninstall.sh
# ============================================================================

set -euo pipefail

# ---- Constants -----------------------------------------------------------
INSTALL_DIR="${HOME}/.local/share/walrus-lcd"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_NAME="cooler-lcd.service"

# ---- Colors --------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

# ---- Step 1: Stop & Disable Service --------------------------------------
stop_service() {
    info "Stopping and disabling service..."
    systemctl --user stop "${SERVICE_NAME}" 2>/dev/null || true
    systemctl --user disable "${SERVICE_NAME}" 2>/dev/null || true
    ok "Service stopped"
}

# ---- Step 2: Remove Service File -----------------------------------------
remove_service() {
    info "Removing service file..."
    rm -f "${SERVICE_DIR}/${SERVICE_NAME}"
    systemctl --user daemon-reload 2>/dev/null || true
    ok "Service file removed"
}

# ---- Step 3: Remove udev Rule --------------------------------------------
remove_udev_rule() {
    info "Removing udev rule (requires sudo)..."
    sudo rm -f /etc/udev/rules.d/99-cooler-lcd.rules
    sudo udevadm control --reload-rules 2>/dev/null || true
    sudo udevadm trigger 2>/dev/null || true
    ok "Udev rule removed"
}

# ---- Step 4: Remove Installed Files --------------------------------------
remove_install_dir() {
    info "Removing ${INSTALL_DIR}..."
    rm -rf "${INSTALL_DIR}"
    ok "Install directory removed"
}

# ---- Main ----------------------------------------------------------------
main() {
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║  🐋 Walrus Assassin 90 LCD Driver Uninstaller  ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    stop_service
    remove_service
    remove_udev_rule
    remove_install_dir

    echo ""
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✅ Uninstall complete!${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  The display will show 0°C or blank until you"
    echo -e "  reconnect it or install another driver."
    echo ""
}

main "$@"
