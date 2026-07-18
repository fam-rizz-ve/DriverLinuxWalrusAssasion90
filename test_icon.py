#!/usr/bin/env python3
"""
Test: Scoprire se il logo/icona del Walrus Assassin 90 può essere controllato
via byte specifici nel frame (oltre a byte[2] che è la temperatura).
"""
import os
import time

HIDRAW = "/dev/hidraw5"

def send_bytes(data):
    fd = os.open(HIDRAW, os.O_RDWR)
    os.write(fd, data)
    os.close(fd)

print("=" * 60)
print("TEST ICONA - WALRUS ASSASSIN 90")
print("=" * 60)
print("Il display mostra un logo/simbolo del produttore sopra la temperatura.")
print("Proviamo a cambiarlo inviando valori diversi in vari byte.")
print("Guarda il LOGO (non la temperatura) e dimmi se cambia!")
print()

# ---- TEST A: byte[0] control ----
print("=== TEST A: byte[0] da 0 a 9 ===")
for val in range(10):
    frame = bytearray(64)
    frame[0] = val
    frame[2] = 57  # temp fissa
    send_bytes(bytes(frame))
    print(f"  byte[0] = {val} -> logo cambia?")
    time.sleep(1)

# ---- TEST B: byte[1] control ----
print("\n=== TEST B: byte[1] da 0 a 9 ===")
for val in range(10):
    frame = bytearray(64)
    frame[1] = val
    frame[2] = 57
    send_bytes(bytes(frame))
    print(f"  byte[1] = {val} -> logo cambia?")
    time.sleep(1)

# ---- TEST C: byte[3] ----
print("\n=== TEST C: byte[3] da 0 a 9 ===")
for val in range(10):
    frame = bytearray(64)
    frame[2] = 57
    frame[3] = val
    send_bytes(bytes(frame))
    print(f"  byte[3] = {val} -> logo cambia?")
    time.sleep(1)

# ---- TEST D: byte[4] ----
print("\n=== TEST D: byte[4] da 0 a 9 ===")
for val in range(10):
    frame = bytearray(64)
    frame[2] = 57
    frame[4] = val
    send_bytes(bytes(frame))
    print(f"  byte[4] = {val} -> logo cambia?")
    time.sleep(1)

# ---- TEST E: byte[5] ----
print("\n=== TEST E: byte[5] da 0 a 9 ===")
for val in range(10):
    frame = bytearray(64)
    frame[2] = 57
    frame[5] = val
    send_bytes(bytes(frame))
    print(f"  byte[5] = {val} -> logo cambia?")
    time.sleep(1)

# ---- TEST F: byte[30..40] ----
print("\n=== TEST F: byte[30..40] tutti = 99 ===")
frame = bytearray(64)
frame[2] = 57
for pos in range(30, 41):
    frame[pos] = 99
send_bytes(bytes(frame))
time.sleep(2)
print("  byte[30-40]=99 -> logo cambia?")

# ---- TEST G: byte[50..63] ----
print("\n=== TEST G: byte[50..63] tutti = 99 ===")
frame = bytearray(64)
frame[2] = 57
for pos in range(50, 64):
    frame[pos] = 99
send_bytes(bytes(frame))
time.sleep(2)
print("  byte[50-63]=99 -> logo cambia?")

print("\n✅ Test completato!")
print("Se il logo NON è mai cambiato -> l'icona è fissa nel firmware.")
print("Se il logo è cambiato -> dimmi a che byte/test!")
