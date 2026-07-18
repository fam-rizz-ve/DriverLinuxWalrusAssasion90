#!/bin/bash
# =============================================================================
# setup-cooler-lcd.sh — Installazione e configurazione driver display dissipatore
# UPSIREN Walrus Assassin 90 (USB HID 5131:2007)
# Esegui: sudo bash setup-cooler-lcd.sh
# =============================================================================
set -euo pipefail

echo "=========================================="
echo "  Cooler LCD Linux — Setup Completo"
echo "=========================================="
echo ""

# --- PASSO 1: Pacchetti Arch/CachyOS ---
echo ">>> [1/4] Installazione dipendenze di sistema..."
pacman -S --noconfirm hidapi python-hidapi python-psutil python-pip
echo "[OK] Pacchetti di sistema installati."
echo ""

# --- PASSO 2: Pacchetti pip (opzionali) ---
echo ">>> [2/4] Installazione pacchetti pip (pynvml per NVIDIA)..."
pip install --user pynvml 2>&1 || echo "[WARN] pynvml non installato (GPU NVIDIA non disponibile o già installato)"
echo "[OK] Pacchetti pip processati."
echo ""

# --- PASSO 3: Regola udev ---
echo ">>> [3/4] Creazione regola udev per accesso non-root..."
RULES_FILE="/etc/udev/rules.d/99-cooler-lcd.rules"
cat > "$RULES_FILE" << 'UDEV_RULE'
# Cooler LCD display (UPSIREN Walrus Assassin 90 / Vevor AIO)
# VID 0x5131, PID 0x2007
KERNEL=="hidraw*", ATTRS{idVendor}=="5131", ATTRS{idProduct}=="2007", MODE="0666", TAG+="uaccess"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="5131", ATTRS{idProduct}=="2007", MODE="0666", TAG+="uaccess"
UDEV_RULE
echo "[OK] Regola scritta in $RULES_FILE"

echo ">>> Ricarica regole udev..."
udevadm control --reload-rules
udevadm trigger
echo "[OK] Regole udev ricaricate."

# Trova il nodo attuale del dispositivo
HIDRAW=$(ls /dev/hidraw* 2>/dev/null | while read dev; do
    vid=$(udevadm info --query=property --name="$dev" 2>/dev/null | grep "^ID_VENDOR_ID=5131" && true)
    if [ -n "$vid" ]; then
        basename "$dev"
        break
    fi
done)

if [ -n "$HIDRAW" ]; then
    chmod 666 "/dev/$HIDRAW" 2>/dev/null || true
    echo "[OK] Permessi aggiornati per /dev/$HIDRAW"
else
    echo "[WARN] Dispositivo non trovato. Riprova dopo il ricaricamento udev."
fi
echo ""

# --- PASSO 4: Verifica ---
echo ">>> [4/4] Verifica installazione..."
echo "--- Pacchetti ---"
pacman -Qi hidapi python-hidapi python-psutil python-pip 2>&1 | grep -E "^(Name|Version)" || true
echo ""
echo "--- Python modules ---"
python3 -c "import hid; print(f'  hid (pyhidapi): {hid.__version__}') 2>/dev/null" || echo "  hid: NON DISPONIBILE"
python3 -c "import psutil; print(f'  psutil: {psutil.__version__}')" 2>/dev/null || echo "  psutil: NON DISPONIBILE"
python3 -c "import pynvml; print('  pynvml: OK')" 2>/dev/null || echo "  pynvml: NON DISPONIBILE (opzionale)"
echo ""
echo "--- Dispositivo HID ---"
lsusb 2>/dev/null | grep -i "5131" || echo "  Dispositivo non trovato via lsusb"
ls -la /dev/hidraw5 2>/dev/null || echo "  /dev/hidraw5 non trovato"
echo ""
echo "=========================================="
echo "  Setup completato!"
echo "  Per avviare il driver:"
echo "    python3 /home/andrea/Progetti/DisplayDissipatoreAssassin90/vevor_lcd_linux.py"
echo "  Per debug (mostra valori):"
echo "    python3 /home/andrea/Progetti/DisplayDissipatoreAssassin90/vevor_lcd_linux.py --print"
echo "=========================================="
