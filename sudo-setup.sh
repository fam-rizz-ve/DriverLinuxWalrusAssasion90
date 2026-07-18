#!/bin/bash
# =============================================================================
# sudo-setup.sh — Esegui: sudo bash sudo-setup.sh
# Crea regola udev e imposta permessi per il display dissipatore
# =============================================================================
set -euo pipefail

echo "=== Installazione pacchetti di sistema ==="
pacman -S --noconfirm python-hidapi 2>&1 || echo "[WARN] python-hidapi già installato o non disponibile"

echo ""
echo "=== Creazione regola udev ==="
cat > /etc/udev/rules.d/99-cooler-lcd.rules << 'EOF'
# Cooler LCD display (UPSIREN Walrus Assassin 90 / Vevor AIO)
# VID 0x5131, PID 0x2007
KERNEL=="hidraw*", ATTRS{idVendor}=="5131", ATTRS{idProduct}=="2007", MODE="0666", TAG+="uaccess"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="5131", ATTRS{idProduct}=="2007", MODE="0666", TAG+="uaccess"
EOF
echo "[OK] Regola scritta in /etc/udev/rules.d/99-cooler-lcd.rules"

echo ""
echo "=== Ricarica regole udev ==="
udevadm control --reload-rules
udevadm trigger
echo "[OK] Regole udev ricaricate"

echo ""
echo "=== Verifica ==="
cat /etc/udev/rules.d/99-cooler-lcd.rules
echo ""
ls -la /dev/hidraw5 2>&1 || echo "/dev/hidraw5 non trovato"
echo ""
echo "=== Fatto! Ora prova: ==="
echo "  timeout 10 python3 /home/andrea/Progetti/DisplayDissipatoreAssassin90/vevor_lcd_linux.py --print"
