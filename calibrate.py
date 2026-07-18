#!/usr/bin/env python3
"""
Calibration tool for Walrus Assassin 90 display byte layout.
Sends known temperature values (88°C) to different byte positions
to discover where the firmware reads CPU temperature.
"""
import os
import time
import signal
import sys

HIDRAW_PATH = "/dev/hidraw5"

def send_frame(data_bytes):
    """Write raw 65-byte frame to /dev/hidraw5."""
    try:
        fd = os.open(HIDRAW_PATH, os.O_RDWR)
        os.write(fd, bytes(data_bytes))
        os.close(fd)
        return True
    except OSError as e:
        print(f"  Write error: {e}")
        return False

def build_frame(value_bytes):
    """Build standard 65-byte frame: [0x00, 0x00, 0x01, 0x02, 33vals, padding]."""
    data = [0x00, 0x01, 0x02] + list(value_bytes)
    data += [0x00] * (64 - len(data))
    return [0x00] + data[:64]

def test_position(pos, label):
    """Send 88°C to a specific byte position. Return True if write OK."""
    v = [0] * 33
    v[pos] = 88  # Temperature value
    # Set date/time to something fixed to avoid confusion
    v[22] = 20   # year 20
    v[23] = 26   # year 26
    v[24] = 7    # month 7
    v[25] = 16   # day 16
    v[26] = 12   # hour 12
    v[27] = 0    # minute 0
    v[28] = 0    # second 0
    v[29] = 3    # weekday
    frame = build_frame(v)
    ok = send_frame(frame)
    if ok:
        print(f"  Sent: v[{pos:2d}]={88:3d} ({label:20s}) -> display should show '88°C'")
    return ok

def main():
    print("=" * 60)
    print("CALIBRAZIONE DISPLAY WALRUS ASSASSIN 90")
    print("=" * 60)
    print()
    print("Osserva il display del dissipatore.")
    print("Lo script invia 88°C a diverse posizioni byte.")
    print("Quando vedi '88°C' sul display, PREMI Ctrl+C e dimmi qual era la posizione.")
    print()

    # Phase 1: Test individual byte positions for CPU temp
    print("FASE 1: Trova la posizione della temperatura")
    print("-" * 40)

    # Test most likely positions first
    candidates = [
        (0,  "Vevor CPU temp int"),
        (10, "Vevor GPU temp int"),
        (8,  "Vevor CPU voltage int"),
        (3,  "Vevor CPU usage"),
        (6,  "Vevor CPU freq /100"),
        (30, "Vevor RAM %"),
        (4,  "Vevor CPU power %100"),
        (31, "Vevor CPU power /100"),
        (16, "Vevor GPU freq /100"),
        (1,  "temp decimal (unlikely main)"),
        (13, "GPU usage (unlikely main)"),
        (18, "Fan RPM /100 (unlikely main)"),
        (20, "Pump RPM /100 (unlikely main)"),
        (5,  "power decimal (unlikely)"),
        (7,  "freq %100 (unlikely)"),
        (9,  "voltage dec (unlikely)"),
        (2,  "unit byte (unlikely)"),
        (12, "GPU unit (unlikely)"),
    ]

    running = True
    def handler(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, handler)

    try:
        for pos, label in candidates:
            if not running:
                break
            print(f"\nTest posizione v[{pos}]:")
            # Send 5 frames over 1 second
            for _ in range(5):
                if not running:
                    break
                test_position(pos, label)
                time.sleep(0.2)
            time.sleep(1.0)  # Pause to observe display

            # Now send different value to confirm
            v = [0] * 33
            v[pos] = 42  # Different value
            v[22] = 20; v[23] = 26; v[24] = 7; v[25] = 16
            v[26] = 12; v[27] = 0; v[28] = 0; v[29] = 3
            frame = build_frame(v)
            for _ in range(3):
                if not running:
                    break
                send_frame(frame)
                time.sleep(0.2)
            print(f"  Then sent: v[{pos}]={42} -> display should show '42°C'")
            time.sleep(0.5)

    except KeyboardInterrupt:
        pass

    print("\n\nCalibrazione completata.")
    print("Quale posizione mostrava '88°C' sul display?")

if __name__ == "__main__":
    main()
