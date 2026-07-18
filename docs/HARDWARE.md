# Hardware Compatibility

## ✅ Confirmed

| Cooler                        | USB VID:PID   | Status      | Notes                          |
|-------------------------------|---------------|-------------|--------------------------------|
| **UPSIREN Walrus Assassin 90**| `5131:2007`   | ✅ Confirmed | Primary target — tested        |

## 🟡 Likely Compatible

These coolers appear to share the same USB HID controller (`5131:2007`):

| Cooler                        | USB VID:PID   | Status      | Notes                          |
|-------------------------------|---------------|-------------|--------------------------------|
| UPSIREN Walrus Guard 120      | `5131:2007`   | 🟡 Likely   | Same brand, same VID:PID       |
| UPSIREN Walrus Glacier 120    | `5131:2007`   | 🟡 Likely   | Same brand, same VID:PID       |
| Various Vevor-branded AIOs    | `5131:2007`   | 🟡 Likely   | Uses same OEM HID chip         |
| Various HT-branded AIOs       | `5131:2007`   | 🟡 Likely   | Uses same OEM HID chip         |

## ❌ Known Incompatible

| Cooler / Device                | USB VID:PID   | Status      | Notes                          |
|-------------------------------|---------------|-------------|--------------------------------|
| Generic USB HID devices       | Any           | ❌          | Wrong protocol                 |
| Coolers without LCD displays  | N/A           | ❌          | No display to drive            |

---

## How to Check Your Cooler

### 1. Verify USB VID:PID

Connect your cooler and run:

```bash
lsusb | grep 5131
```

Expected output:
```
Bus 001 Device 005: ID 5131:2007
```

### 2. Check HID Device

```bash
ls /dev/hidraw*
cat /sys/class/hidraw/hidraw*/device/uevent | grep -A3 "5131"
```

Expected output should show:
```
HID_ID=0003:00005131:00002007
```

### 3. Run the Driver in Debug Mode

```bash
python3 src/walrus_lcd.py --print
```

If the display shows temperature values, your cooler is compatible.

---

## 🏭 About the HID Chip

The UPSIREN Walrus series uses a **shared OEM HID chip** manufactured by the same supplier used by Vevor, HT, and other rebranded AIO liquid coolers. This chip:

- Reports as USB HID (VID `0x5131`, PID `0x2007`)
- Accepts 64-byte raw HID frames via `/dev/hidraw*`
- Uses a simple protocol: `byte[2]` = temperature integer
- Has a firmware-baked UPSIREN logo

The same chip is used across multiple brands, which is why several non-UPSIREN coolers may also work with this driver.
