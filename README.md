<div align="center">

# 🐋 Walrus Assassin 90 — Linux LCD Driver

**Native Linux driver for the UPSIREN Walrus Assassin 90 CPU cooler display.**

*Zero dependencies on Windows. Pure Python. Runs as a systemd service.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-orange.svg)](docs/HARDWARE.md)
[![Language: Python](https://img.shields.io/badge/Language-Python-3776AB.svg)](src/walrus_lcd.py)

</div>

---

## 🎯 What Is This?

The **UPSIREN Walrus Assassin 90** is an AIO liquid cooler with a built-in LCD temperature display. The official software only works on Windows.

**This project changes that.** A lightweight Python driver that reads your CPU/GPU temperature and streams it to the cooler's display — on Linux. Runs as a background service, auto-starts on login, and gets out of your way.

---

## ✨ Features

- ✅ **Real-time CPU temperature** on the cooler's LCD display
- ✅ **Automatic GPU temperature** display (NVIDIA via `pynvml`)
- ✅ **Alternating mode** — toggles between CPU and GPU every 6 seconds
- ✅ **Systemd service** — starts on login, restarts on failure
- ✅ **udev rule** — no `sudo` needed for HID device access
- ✅ **Multi-distro** — works on Arch, Ubuntu, Fedora, and more
- ✅ **Zero Windows** — no .NET, no Windows apps, no Wine

---

## 📦 Quick Start

```bash
git clone https://github.com/fam-rizz-ve/DriverLinuxWalrusAssassin90.git
cd DriverLinuxWalrusAssassin90
make install
```

That's it. The display will show your CPU temperature within seconds.

### Common Commands

| Command | Description |
|---------|-------------|
| `walrus-config` or `make config` | 🐋 Interactive configuration tool |
| `make status` | Show service status |
| `make logs` | Follow service logs |
| `make restart` | Restart the service |

---

## 🔧 Manual Installation

Prefer to do it step by step? Here's what `make install` does under the hood:

### 1. Install System Dependencies

```bash
# Arch / CachyOS
sudo pacman -S --needed python python-pip hidapi lm-sensors

# Ubuntu / Debian
sudo apt install python3 python3-pip python3-venv hidapi lm-sensors

# Fedora
sudo dnf install python3 python3-pip hidapi lm-sensors
```

### 2. Create Virtual Environment & Install Python Deps

```bash
python3 -m venv venv
source venv/bin/activate
pip install psutil pynvml
```

### 3. Install udev Rule (one-time, needs sudo)

```bash
sudo cp udev/99-cooler-lcd.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 4. Run the Driver

```bash
# Foreground test
python3 src/walrus_lcd.py --print

# Or as a background service (see below)
```

---

## 🔧 Configuration

The driver is **fully configurable** — no need to edit Python code.

### Interactive configuration

```bash
walrus-config
```

—or if installed from source:

```bash
make config
```

You'll be prompted for each setting (press **Enter** to keep current value):

```
🐋 Walrus LCD Configuration

Current configuration:
  temp_source     = auto    (CPU<->GPU alternating)
  switch_seconds = 6
  refresh_ms     = 200
  clamp_max      = 89

Edit values (press Enter to keep current):

  Temperature source [auto] (cpu|gpu|auto): cpu
  Switch seconds [6]:
  Refresh ms [200] (min 50):
  Clamp max [89] (1-100): 85

Save? [Y/n] y

✅ Saved to /home/andrea/.local/share/walrus-lcd/config.toml
🔄 Service restarted.
```

### Non-interactive flags

| Flag | Description |
| ---- | ----------- |
| `--show` | Print current configuration and exit |
| `--reset` | Reset to defaults (with confirmation prompt) |
| `--help` | Print usage |

### Manual configuration

The config file is plain TOML at `~/.local/share/walrus-lcd/config.toml`. Edit it directly if you prefer:

```toml
# Walrus Assassin 90 LCD driver configuration

# Temperature source to display
#   "cpu"  — show CPU temperature only
#   "gpu"  — show GPU temperature only (requires NVIDIA + pynvml)
#   "auto" — alternate between CPU and GPU every switch_seconds
temp_source = "auto"

# Seconds between CPU↔GPU alternation (only used when temp_source = "auto")
switch_seconds = 6

# HID refresh interval in milliseconds (50ms minimum to avoid bus spam)
refresh_ms = 200

# Maximum temperature to send to display
# Display valid range is 0-89; 90+ blinks (alarm), 120+ shows "h1"
# Lower this if you want to cap the displayed temperature
clamp_max = 89
```

After manual edit, restart the service:

```bash
make restart
# or
systemctl --user restart cooler-lcd.service
```

### Config keys reference

| Key | Type | Default | Valid | Description |
| --- | ---- | ------- | ----- | ----------- |
| `temp_source` | string | `"auto"` | `cpu` / `gpu` / `auto` | Which temperature to display |
| `switch_seconds` | integer | `6` | `>= 1` | Seconds between CPU↔GPU alternation (when `temp_source="auto"`) |
| `refresh_ms` | integer | `200` | `>= 50` | HID refresh interval in milliseconds |
| `clamp_max` | integer | `89` | `1` to `100` | Max temperature before clamping (display firmware: 90+ alarm, 120+ "h1" error) |

### Custom config path

Set the `WALRUS_LCD_CONFIG` environment variable to use a different file. Useful for testing or multi-user setups:

```bash
WALRUS_LCD_CONFIG=/etc/walrus-lcd.toml python3 walrus_lcd.py
```

When unset, config search order:
1. `${WALRUS_LCD_CONFIG}` env var (if set)
2. `~/.local/share/walrus-lcd/config.toml` (installed location)
3. `<script_dir>/config.toml` (dev mode)
4. Built-in defaults (no error if no file exists)

> **Note:** The `walrus-config` symlink is installed at `~/.local/bin/walrus-config`. If `~/.local/bin` is not in your `$PATH`, `make config` will still work, or add it manually (your install script will print a warning if this is needed).

---

## 🔬 How It Works

The cooler uses a **USB HID** interface (VID `0x5131`, PID `0x2007`). The driver sends a 64-byte frame over `/dev/hidraw*` every 200ms. The only meaningful byte is **byte[2]**, which holds the temperature as an integer.

```
┌─────────────────────────────────────────────────────────┐
│  Byte  │  0    │  1    │  2     │  3-63          │  64  │
│  Value │ 0x00  │ 0x00  │ TEMP   │ 0x00           │ 0x00 │
│  Role  │ RPT   │ ign   │ °C     │ pad            │ pad  │
└─────────────────────────────────────────────────────────┘
```

- **byte[0]** = Report ID (always `0x00`, unused)
- **byte[1]** = Ignored by firmware (confirmed via probing — not an opcode)
- **byte[2]** = Temperature integer (0–89 = valid, 90+ = alarm, 120+ = "h1" error)
- **bytes[3–63]** = Padding, all zeros, ignored

**Logo UPSIREN** is baked into the firmware — it cannot be changed, hidden, or replaced via HID.

> Full protocol documentation: [docs/PROTOCOL.md](docs/PROTOCOL.md)

---

## 🖥️ Hardware Compatibility

| Cooler | Status | Notes |
|--------|--------|-------|
| **UPSIREN Walrus Assassin 90** | ✅ Confirmed | Primary target — tested |
| UPSIREN Walrus Guard 120 | 🟡 Likely | Same VID:PID `5131:2007` |
| UPSIREN Walrus Glacier 120 | 🟡 Likely | Same VID:PID `5131:2007` |
| Various Vevor/HT AIOs | 🟡 Likely | Shared OEM HID chip |

**Check your cooler:**

```bash
lsusb | grep 5131
# Expected: Bus 001 Device 005: ID 5131:2007
```

> Full compatibility info: [docs/HARDWARE.md](docs/HARDWARE.md)

---

## 🛠️ Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install driver, udev rule, and systemd service |
| `make uninstall` | Remove driver and all configuration |
| `make config` | Interactive configuration tool (temperature source, refresh, etc.) |
| `make status` | Show service status |
| `make logs` | Follow service logs (Ctrl-C to exit) |
| `make restart` | Restart the service |
| `make stop` | Stop the service |
| `make test` | Run driver in foreground with debug output |
| `make clean` | Remove venv and cache files |

---

## 🚨 Troubleshooting

| Problem | Solution |
|---------|----------|
| Display shows 0°C always | Run `sensors` — check if `lm-sensors` is installed |
| "Permission denied" on `/dev/hidraw*` | Re-run `make install` to install udev rule |
| GPU temp shows 0 | Install `pynvml` and NVIDIA drivers |
| Service not starting | Run `make status` and `make logs` |
| Display shows "h1" error | Temperature >120°C — check your system cooling |

> Full troubleshooting guide: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## 🤝 Contributing

Contributions are welcome! Here's how:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b my-feature`
3. **Commit** your changes: `git commit -m "Add my feature"`
4. **Push** to your fork: `git push origin my-feature`
5. **Open** a Pull Request

### Ideas for Contributions

- 📸 Add photos of the display in action to `screenshots/`
- 🔌 Test on other UPSIREN/Vevor/HT cooler models
- 🧪 Add unit tests for `build_walrus_frame()`
- 📊 Add fan speed or pump RPM display (if protocol supports it)
- 🌍 Improve translations or add localization support

---

## 🙏 Acknowledgments

- **[coldwelderx/cooler-lcd-linux](https://github.com/coldwelderx/cooler-lcd-linux)** — Original research and reverse engineering of the USB HID protocol
- **UPSIREN** — Manufacturer of the Walrus Assassin 90 cooler
- **[psutil](https://github.com/giampaolo/psutil)** — Cross-platform system monitoring
- **[pynvml](https://github.com/gpuopenanalytics/pynvml)** — NVIDIA Management Library Python bindings

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 AndreHolly / fam-rizz-ve
