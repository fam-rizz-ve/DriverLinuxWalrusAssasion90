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

## ⚙️ Configuration

The driver reads two environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TEMP_MODE` | `"auto"` | `"auto"` = alternate CPU/GPU. Only mode currently supported. |
| `TEMP_SWITCH_S` | `6` | Seconds between CPU ↔ GPU alternation |

To customize, edit `~/.config/systemd/user/cooler-lcd.service` and add:

```ini
Environment=TEMP_SWITCH_S=10
```

Then restart:

```bash
systemctl --user daemon-reload
systemctl --user restart cooler-lcd.service
```

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
