#!/usr/bin/env python3
"""
Calibration v4 - Confirm Walrus frame format.
Byte[2] = CPU temp int (confirmed).
Test each position systematically.
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

def pause(sec):
    time.sleep(sec)

print("=" * 60)
print("CALIBRAZIONE V4 - WALRUS ASSASSIN 90")
print("=" * 60)
print("Abbiamo scoperto: byte[2] = CPU temp (integer)")
print("Verifichiamo e mappiamo le altre posizioni.")
print("Guarda il display e dimmi cosa vedi!")
print()

# ---- TEST 1: Confirm byte[2] = CPU temp integer ----
print("=== TEST 1: Confirm byte[2] = CPU temp ===")
frame = bytearray(64)
frame[2] = 88  # Only byte[2] = 88, everything else 0
for _ in range(15):
    send(bytes(frame), "88 at byte[2]")
    time.sleep(0.2)
print(">> Dovresti vedere 88C (se byte[2] e' la temperatura)")
pause(2)

# ---- TEST 2: byte[1] = CPU temp decimal? ----
print("\n=== TEST 2: Find decimal place ===")
frame = bytearray(64)
frame[2] = 57  # CPU temp int
frame[1] = 50  # Try decimal = 0.50
for _ in range(15):
    send(bytes(frame), "57.50 at byte[2].[1]")
    time.sleep(0.2)
print(">> Mostra 57C o 57.50C?")
pause(2)

# ---- TEST 3: Find CPU usage ----
print("\n=== TEST 3: Find CPU usage (%) ===")
candidates = [0, 1, 3, 4, 5, 6, 7, 8]
for pos in candidates:
    frame = bytearray(64)
    frame[2] = 57  # Known: CPU temp
    frame[pos] = 99  # Try this position for usage
    for _ in range(10):
        send(bytes(frame), f"57C + 99% at pos {pos}")
        time.sleep(0.15)
    print(f"  Test pos {pos}: usage=99 -> display mostra '99%'?")
    pause(0.5)

# ---- TEST 4: Find GPU temp ----
print("\n=== TEST 4: Find GPU temp position ===")
gpu_candidates = [10, 11, 12, 13, 14, 15, 16, 17, 18]
for pos in gpu_candidates:
    frame = bytearray(64)
    frame[2] = 57  # CPU temp
    frame[pos] = 42  # GPU temp candidate
    for _ in range(10):
        send(bytes(frame), f"57C CPU + 42C GPU at pos {pos}")
        time.sleep(0.15)
    print(f"  Test pos {pos}: GPU=42 -> display mostra '42C'?")
    pause(0.5)

# ---- TEST 5: Find date/time position ----
print("\n=== TEST 5: Find date/time positions ===")
frame = bytearray(64)
frame[2] = 57  # CPU temp
# Set positions 20-39 to calendar values
for pos in range(20, 40):
    frame[pos] = 99
for _ in range(15):
    send(bytes(frame), "57C + date/time markers")
    time.sleep(0.2)
print(">> Vedi '99' da qualche parte (anno/mese/giorno/ora)?")
pause(2)

# ---- TEST 6: Try alternate: 3-byte header then 33 values ----
print("\n=== TEST 6: What is byte[0]? ===")
frame = bytearray(64)
frame[0] = 0xAA  # Try a distinctive marker in byte[0]
frame[2] = 57    # CPU temp
for _ in range(15):
    send(bytes(frame), "AA at byte[0], 57 at byte[2]")
    time.sleep(0.2)
print(">> Byte[0]=0xAA causa differenza? O e' ignorato?")
pause(2)

# ---- TEST 7: What if the frame is 65 bytes (with report ID)? ----
print("\n=== TEST 7: 65-byte frames (with report ID byte) ===")
# 65-byte frame: report_id at [0], then 64 data bytes
frame65 = bytearray(65)
frame65[0] = 0x00   # report ID
frame65[3] = 57     # CPU temp (data byte 2)
for _ in range(15):
    fd = os.open(HIDRAW, os.O_RDWR)
    os.write(fd, bytes(frame65))
    os.close(fd)
    time.sleep(0.2)
print(">> Con report ID 0x00 + 64-byte data, mostra 57C?")
pause(2)

print("\n✅ Calibration v4 done!")
print("")
print("RISULTATI:")
print("- Test 1: byte[2]=88 -> display mostra 88C?")
print("- Test 2: byte[1]=50 -> mostra decimale?")
print("- Test 3: quale pos ha fatto vedere 99%?")
print("- Test 4: quale pos ha fatto vedere 42C GPU?")
print("- Test 5: mostra 99 da qualche parte?")
print("- Test 6: 0xAA in byte[0] fa differenza?")
print("- Test 7: 65-byte funziona?")
