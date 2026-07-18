# Troubleshooting

## 🔍 Common Issues

---

### ❌ "Cannot find /dev/hidraw* for 0x5131:0x2007"

**Cause:** The cooler is not detected as a USB HID device.

**Solutions:**
1. **Check USB connection:**
   ```bash
   lsusb | grep 5131
   ```
   If nothing appears, try a different USB port or cable.

2. **Check hidraw devices:**
   ```bash
   ls /dev/hidraw*
   ```
   If no hidraw devices exist, the kernel may not have loaded the HID driver.

3. **Reload HID module:**
   ```bash
   sudo modprobe hid-generic
   ```

---

### ❌ "Permission denied" when opening /dev/hidraw*

**Cause:** The udev rule is not installed or not active.

**Solutions:**
1. **Re-run install.sh** (installs udev rule):
   ```bash
   make install
   ```

2. **Manual udev setup:**
   ```bash
   sudo cp udev/99-cooler-lcd.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

3. **Check rule is active:**
   ```bash
   udevadm info --query=all --name=/dev/hidraw0 | grep MODE
   ```
   Should show `MODE="0666"`.

---

### ❌ Display shows 0°C always

**Cause:** Temperature sensor is not being read correctly.

**Solutions:**
1. **Check sensors:**
   ```bash
   sensors
   ```
   You should see CPU temperature data. If not, install `lm-sensors` and run `sudo sensors-detect`.

2. **Check psutil:**
   ```bash
   python3 -c "import psutil; print(psutil.sensors_temperatures())"
   ```
   Should return a dictionary with temperature data.

3. **Run in debug mode:**
   ```bash
   make test
   ```
   Watch the output for sensor reading errors.

---

### ❌ Display shows "h1" error

**Cause:** The driver is sending a temperature value ≥ 120°C.

**Solutions:**
1. **Check your system temperature:**
   ```bash
   sensors
   ```
   If your CPU is genuinely over 120°C, check your cooling setup immediately.

2. **Check the driver:**
   ```bash
   make test
   ```
   Verify the temperature values being sent are sane.

---

### ❌ Service not starting

**Cause:** Systemd user service is not enabled or has errors.

**Solutions:**
1. **Check service status:**
   ```bash
   make status
   ```

2. **Check logs:**
   ```bash
   make logs
   ```

3. **Enable lingering** (for services to run without an active login session):
   ```bash
   sudo loginctl enable-linger $USER
   ```

4. **Reload and restart:**
   ```bash
   systemctl --user daemon-reload
   systemctl --user restart cooler-lcd.service
   ```

---

### ❌ Wrong temperature or erratic readings

**Cause:** Sensor driver conflict or incorrect sensor selection.

**Solutions:**
1. **Run debug mode:**
   ```bash
   make test
   ```
   Check which sensor is being used and its values.

2. **Check available sensors:**
   ```bash
   python3 -c "import psutil; [print(k, v) for k,v in psutil.sensors_temperatures().items() for s in v]"
   ```

3. **Install proper sensor drivers:**
   - AMD: `zenpower` or `k10temp`
   - Intel: `coretemp`
   ```bash
   # Arch/CachyOS
   sudo pacman -S zenpower   # AMD
   sudo pacman -S coretemp   # Intel (may need modprobe)
   ```

---

### ❌ GPU temperature shows 0

**Cause:** `pynvml` is not installed or no NVIDIA GPU is present.

**Solutions:**
1. **Install pynvml:**
   ```bash
   pip install pynvml
   ```

2. **Check NVIDIA driver:**
   ```bash
   nvidia-smi
   ```
   If this fails, install NVIDIA drivers first.

3. **Non-NVIDIA GPUs:** GPU temperature reading is not supported. The driver will fall back to CPU-only mode.

---

## 🛠️ Still Stuck?

1. Run the driver in debug mode: `make test`
2. Check the [PROTOCOL.md](PROTOCOL.md) for protocol details
3. Open an issue on GitHub with:
   - Output of `lsusb | grep 5131`
   - Output of `make test`
   - Your distro and kernel version (`uname -a`)
