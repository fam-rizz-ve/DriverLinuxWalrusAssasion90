#!/usr/bin/env python3
"""
Calibration v3 - Find the correct frame format for Walrus Assassin 90.
The display shows "1°C" = opcode 0x01, proving the Walrus reads temp from
a DIFFERENT byte position than the Vevor.

This test sends frames with known patterns to find which byte position(s)
the firmware reads as temperature.
"""
import os
import time
import signal
import sys

HIDRAW = "/dev/hidraw5"

def send(frame, label=""):
    fd = os.open(HIDRAW, os.O_RDWR)
    os.write(fd, frame)
    os.close(fd)
    print(f"  {label}: sent {len(frame)} bytes")

def test_all_64_positions():
    """
    Send frames where EVERY byte has a unique value (0-63 counting).
    The display will show whatever byte position the firmware reads.
    """
    print("=" * 60)
    print("TEST: Counting frame 0-63 across all 64 positions")
    print("=" * 60)
    print("Il display MOSTRERA' il numero alla posizione che legge.")
    print("Se mostra '0'  -> legge byte[0]")
    print("Se mostra '1'  -> legge byte[1] (sub-opcode Vevor)")
    print("Se mostra '2'  -> legge byte[2] (opcode Vevor - già sospetto)")
    print("Se mostra '17' -> legge byte[17]")
    print()

    # Frame 1: 64 bytes counting 0-63
    f1 = bytes(range(64))
    print("Frame 1: 64 bytes counting 0-63")
    for _ in range(20):  # 4 seconds
        send(f1, "counting 0-63")
        time.sleep(0.2)
    print("  >> Guarda il display: che numero mostra?")
    time.sleep(3)

    # Frame 2: Just first 33 bytes counting (no padding)
    f2 = bytes(range(33))
    print("\nFrame 2: 33 bytes counting 0-32 (no padding)")
    for _ in range(20):
        send(f2, "33 bytes 0-32")
        time.sleep(0.2)
    print("  >> Guarda il display: che numero mostra?")
    time.sleep(3)

    # Frame 3: TEST IPOTESI WALRUS - temperature starts at byte[1]
    # [0x00, cpu_temp, cpu_temp_dec, usage, power, ...]
    # v[0]=88 at byte[1], v[1]=0 at byte[2], v[2]=unit at byte[3]
    print("\nFrame 3: HYPOTHESIS - Walrus format (temp starts at byte[1])")
    v = [0]*33
    v[0] = 88  # CPU temp int - at byte[1]
    v[1] = 0   # CPU temp dec - at byte[2]
    v[2] = 0   # unit C - at byte[3]
    v[3] = 30  # CPU usage
    v[10] = 42 # GPU temp
    v[30] = 50 # RAM
    f3 = bytes([0x00]) + bytes(v) + b'\x00'*30  # 1 header + 33 vals + pad = 64
    print(f"  Frame: [{f3[0]:02x}, {f3[1]:02x}(temp={f3[1]}), {f3[2]:02x}, ...")
    for _ in range(20):
        send(f3, "walrus-hypothesis")
        time.sleep(0.2)
    print("  >> Il display mostra 88°C?")
    time.sleep(3)

    # Frame 4: TEST - Vevor format, but v[0] at diff pos
    # Try placing v[0]=88 at byte[2] (where opcode was)
    print("\nFrame 4: HYPOTHESIS - temp starts at byte[2] (opcode pos)")
    v2 = [0]*33
    v2[2] = 88  # Put 88 at v[2] position (frame byte 6 in Vevor, byte 2 in simple) 
    v2[10] = 42
    v2[30] = 50
    f4 = bytes([0x00]) + bytes(v2) + b'\x00'*30
    for _ in range(20):
        send(f4, "temp-at-byte2")
        time.sleep(0.2)
    print("  >> Il display mostra 88°C?")
    time.sleep(2)

    # Frame 5: Try putting 88 in EVERY position, one at a time
    # 64 frames sent, each with 88 at a different position
    print("\nFrame 5: SCAN - 88 at each byte position (0-63)")
    print("  Looking for which position makes display show '88°C'")
    for pos in range(64):
        frame = bytearray(64)
        frame[pos] = 88  # Put 88 at current position only
        send(bytes(frame), f"88 at pos {pos}")
        time.sleep(0.15)
    print("  >> Se a un certo punto vedi '88°C', DIMI a che posizione eravamo!")
    time.sleep(2)

    print("\n✅ Calibration v3 done!")
    print("Cosa ha mostrato il display? ('0', '1', '2', '17', '88'...)")


if __name__ == "__main__":
    test_all_64_positions()
