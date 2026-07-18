# Walrus Assassin 90 LCD Display — Reverse-Engineered USB HID Protocol

> This document describes the USB HID protocol used by the **UPSIREN Walrus Assassin 90** CPU cooler's built-in LCD display, as determined through empirical reverse engineering.

---

## 📋 Device Identification

| Property   | Value              |
|------------|--------------------|
| USB VID    | `0x5131` (UPSIREN) |
| USB PID    | `0x2007`           |
| Interface  | USB HID (Raw)      |
| Device     | `/dev/hidraw*`     |
| Report Size| 65 bytes           |

---

## 📐 Frame Structure

The display accepts **65-byte** HID output reports:

- **1 byte** Report ID (`0x00`)
- **64 bytes** Payload

```
┌─────────────────────────────────────────────────────────┐
│  Byte  │  0    │  1    │  2     │  3-63          │  64  │
│  Value │ 0x00  │ 0x00  │ TEMP   │ 0x00           │ 0x00 │
│  Role  │ RPT   │ ign   │ °C     │ pad            │ pad  │
└─────────────────────────────────────────────────────────┘
```

| Byte(s) | Name  | Description                                         |
|---------|-------|-----------------------------------------------------|
| 0       | RPT   | Report ID — always `0x00`                           |
| 1       | ign   | Ignored by firmware — confirmed via opcode probing  |
| 2       | TEMP  | Temperature as unsigned integer (see range below)   |
| 3–63    | pad   | Padding — always `0x00`, ignored by firmware        |

### Temperature Range

| Value    | Display Behaviour              |
|----------|--------------------------------|
| 0–89     | Shows the integer value (°C)   |
| 90–119   | Blinking alarm (⚠️ warning)    |
| 120–255  | Shows **"h1"** error code      |

---

## 🔍 What Was Probed

During reverse engineering, the following was empirically confirmed:

| Area                | Finding                                                       |
|---------------------|---------------------------------------------------------------|
| **byte[1]**         | NOT an opcode — sending varied values has **no visible effect** |
| **Logo**            | UPSIREN logo is **firmware-baked**, not controllable via HID  |
| **Layout changes**  | No opcodes found to alter display layout                      |
| **Shutdown**        | No real shutdown command — writing `0` to byte[2] blanks to 0°C |
| **Refresh rate**    | Device accepts updates every ~200ms                           |

### Tools Used for Probing

| Script              | Purpose                                                |
|---------------------|--------------------------------------------------------|
| `probe_frame.py`    | Send known frame patterns, observe display reaction    |
| `probe_byte1.py`    | Systematically test all 256 values for byte[1]        |
| `probe_opcode.py`   | Sweep for layout-changing commands                     |

---

## 🔄 Data Flow

```
┌────────────────┐       64 bytes        ┌────────────────┐
│  walrus_lcd.py │ ──────────────────────▶│  /dev/hidraw*  │──▶ LCD
│  (CPU/GPU temp)│                        │  (USB HID)     │
└────────────────┘                        └────────────────┘
```

1. Driver reads CPU temperature via `psutil.sensors_temperatures()`
2. Driver reads GPU temperature via `pynvml` (NVIDIA only, optional)
3. Temperatures alternate every 6 seconds (configurable)
4. Frame is built with `byte[2]` = integer temperature
5. 64-byte frame is written to the HID device every 200ms
6. On exit, a blank frame (0°C) is sent to release the display

---

## ⚠️ Important Notes

- The **UPSIREN logo** on the display is part of the firmware. No HID command can change it, hide it, or replace it with a custom image.
- The display only accepts a **single integer** for temperature. There is no way to display text, units, fan speed, or other data.
- The temperature range 0–89 is the only safe range. Values above 89 trigger visual warnings (blinking or error codes).
- The driver polls sensors at 200ms intervals. The USB HID device itself may have its own internal refresh rate.
