#!/usr/bin/env python3
"""
Calibration v2 - Try different frame header formats for Walrus Assassin 90.
"""
import os
import time
import signal
import sys

HIDRAW_PATH = "/dev/hidraw5"

def send_frame(frame_bytes):
    """Write frame to /dev/hidraw5."""
    fd = os.open(HIDRAW_PATH, os.O_RDWR)
    written = os.write(fd, frame_bytes)
    os.close(fd)
    return written

# Test patterns: all use v[0]=88, v[10]=42 to identify where temp is read
# v[0] = 88, v[10] = 42, v[11] = 0, v[30] = 50
v88 = [0]*33
v88[0] = 88
v88[10] = 42
v88[30] = 50

def main():
    print("=" * 60)
    print("CALIBRAZIONE V2 - WALRUS ASSASSIN 90 (formati frame)")
    print("=" * 60)
    print("Il display mostra 1°C -> il formato frame Vevor non è compatibile.")
    print("Proviamo diversi formati. Guarda il display per '88°C'/'42°C'/'50'.")
    print("Premi Ctrl+C quando vedi qualcosa di diverso da '1°C'.")
    print()

    formats = []

    # Format 1: RAW 33 bytes, no header, padded to 64
    formats.append(("1. Raw 33vals+pad64", bytes(v88) + b'\x00' * 31))

    # Format 2: Just 33 bytes, no padding
    formats.append(("2. Raw 33vals only", bytes(v88)))

    # Format 3: header 0x00,0x01,0x02 (standard Vevor) NO report ID
    f3 = bytes([0x00, 0x01, 0x02]) + bytes(v88) + b'\x00' * 28
    formats.append(("3. Vevor header no RID", f3))

    # Format 4: report_id=0x00 + Vevor header (current format)
    f4 = bytes([0x00, 0x00, 0x01, 0x02]) + bytes(v88) + b'\x00' * 28
    formats.append(("4. Curr format RID=0", f4))

    # Format 5: Different header: 0x00,0x00,0x01,0x00
    f5 = bytes([0x00, 0x00, 0x01, 0x00]) + bytes(v88) + b'\x00' * 28
    formats.append(("5. Sub-opcode=0", f5))

    # Format 6: 0x00,0x00,0x02,0x02 (different opcode)
    f6 = bytes([0x00, 0x00, 0x02, 0x02]) + bytes(v88) + b'\x00' * 28
    formats.append(("6. Opcode=2", f6))

    # Format 7: report_id=0x01
    f7 = bytes([0x01, 0x00, 0x01, 0x02]) + bytes(v88) + b'\x00' * 28
    formats.append(("7. RID=1", f7))

    # Format 8: send only first 8 bytes (no 33-byte array)
    f8 = bytes([0x00, 0x00, 0x01, 0x02, 88, 0, 0, 0]) + b'\x00' * 56
    formats.append(("8. Only 8 vals + pad", f8))

    # Format 9: 0x00,0x01,0x01,0x01 (different sub-opcode)
    f9 = bytes([0x00, 0x01, 0x01, 0x01]) + bytes(v88) + b'\x00' * 28
    formats.append(("9. Sub-opcode=1", f9))

    # Format 10: 0x00,0x01,0x03,0x02
    f10 = bytes([0x00, 0x01, 0x03, 0x02]) + bytes(v88) + b'\x00' * 28
    formats.append(("A. Opcode=3", f10))

    # Format 11: 64 bytes of ALL 88 (every byte = 88)
    f11 = bytes([88] * 64)
    formats.append(("B. All bytes=88", f11))

    # Format 12: Vevor shutdown frame variation (opcode 15) then data
    f12 = bytes([0x00, 0x00, 0x0F, 0x00]) + b'\x00' * 60
    formats.append(("C. Shutdown frame (test)", f12))

    # Format 13: Try all zeros then v[0]=88 (clear the display first)
    f13_clear = bytes([0x00, 0x00, 0x01, 0x02]) + b'\x00' * 60
    f13_data = bytes([0x00, 0x00, 0x01, 0x02]) + bytes(v88) + b'\x00' * 28
    formats.append(("D. Clear then data", (f13_clear, f13_data)))

    running = True
    def handler(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, handler)

    try:
        for name, frame in formats:
            if not running:
                break
            print(f"\n=== {name} ===")
            print(f"  Length: {len(frame) if isinstance(frame, bytes) else 'multi'} bytes")

            if isinstance(frame, tuple):
                # Multi-step format
                for step_frame in frame:
                    for _ in range(5):
                        if not running:
                            break
                        written = send_frame(step_frame)
                        time.sleep(0.2)
                    time.sleep(0.3)
            else:
                for i in range(10):
                    if not running:
                        break
                    written = send_frame(frame)
                    if i == 0:
                        print(f"  First write: {written} bytes sent", end="")
                    time.sleep(0.2)
                print(f"  (sent 10 frames)")

            print(f"  -> Display dovrebbe mostrare 88°C o 42°C o 50")
            time.sleep(1.5)  # Pause to observe display

    except KeyboardInterrupt:
        pass

    print("\n\n✅ Calibrazione v2 completata.")
    print("Quale formato ha fatto cambiare il display da '1°C'?")

if __name__ == "__main__":
    main()
