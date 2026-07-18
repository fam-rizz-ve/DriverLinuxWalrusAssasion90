#!/usr/bin/env python3
"""
Walrus Assassin 90 — byte[1] Temperature Confirmation Probe

Background:
  Tests 5.10–5.18 in probe_frame.py revealed that byte[1] controls the
  temperature display when non-zero, taking priority over byte[2].
  This script runs focused confirmation tests to map the exact behavior.

Device: /dev/hidraw5, 65-byte HID output reports
Frame:  byte[0]=0x00 (report ID), byte[1..64]=payload (64 bytes)

Tests:
  A — Confirm byte[1] is the real temperature slot (fallback to byte[2])
  B — Priority rule: does byte[1] ALWAYS win, or only when non-zero?
  C — Is byte[1] actually a different field (not temp)?
  D — Sweep byte[1] range to find displayable limits
  E — Is byte[1] temp, or a mode/flag?
"""

import os
import sys
import time
from typing import List, Optional

# ─── Device Constants ───────────────────────────────────────────────────────
DEVICE_PATH = "/dev/hidraw5"
FRAME_SIZE = 65          # 1 byte report ID + 64 bytes payload
PAYLOAD_SIZE = 64        # bytes[1..64] of the HID frame
REPORT_ID = 0x00
SEND_COUNT = 10          # frames per test
SEND_DELAY_MS = 200      # milliseconds between sends (2s total)


# ─── Pure Functions ─────────────────────────────────────────────────────────

def build_frame(payload: List[int]) -> bytes:
    """Build a 65-byte HID frame from a 64-byte payload list.

    Args:
        payload: 64 integers (0–255) for the payload portion of the frame.

    Returns:
        Complete 65-byte frame: [REPORT_ID] + payload.

    Raises:
        ValueError: If payload length is not exactly 64.
    """
    if len(payload) != PAYLOAD_SIZE:
        raise ValueError(
            f"Payload must be {PAYLOAD_SIZE} bytes, got {len(payload)}"
        )
    if any(b < 0 or b > 255 for b in payload):
        raise ValueError("All payload bytes must be in range 0–255")
    return bytes([REPORT_ID] + payload)


def make_payload(byte1: int = 0, byte2: int = 0, **extra_bytes: int) -> List[int]:
    """Create a zeroed 64-byte payload with specified bytes set.

    Args:
        byte1: Value for payload index 0 (= frame byte[1]).
        byte2: Value for payload index 1 (= frame byte[2]).
        extra_bytes: Additional positions as keyword args, e.g. byte3=88.

    Returns:
        64-element list of integers.

    Raises:
        ValueError: If any position is out of the 0–63 payload range.
    """
    payload = [0] * PAYLOAD_SIZE
    payload[0] = byte1
    payload[1] = byte2
    for key, value in extra_bytes.items():
        # Parse "byte3" → index 2, "byte10" → index 9, etc.
        if not key.startswith("byte") or not key[4:].isdigit():
            raise ValueError(f"Invalid extra byte key: {key!r} — use byteN=<value>")
        index = int(key[4:]) - 1  # byte1 → index 0, byte2 → index 1, ...
        if index < 0 or index >= PAYLOAD_SIZE:
            raise ValueError(f"Position {key} maps to index {index}, out of range 0–{PAYLOAD_SIZE - 1}")
        payload[index] = value
    return payload


def send_frames(fd: int, payload: List[int], count: int = SEND_COUNT, delay_ms: int = SEND_DELAY_MS) -> None:
    """Send a frame repeatedly to ensure the display updates.

    Args:
        fd: Open file descriptor for the HID device.
        payload: 64-byte payload to transmit.
        count: Number of repetitions.
        delay_ms: Delay between sends in milliseconds.
    """
    frame = build_frame(payload)
    for _ in range(count):
        os.write(fd, frame)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)


# ─── Interactive Test Helpers ───────────────────────────────────────────────

def describe_extras(**extra_bytes: int) -> str:
    """Format extra byte overrides into a readable string."""
    if not extra_bytes:
        return ""
    parts = []
    for key in sorted(extra_bytes.keys(), key=lambda k: int(k[4:])):
        parts.append(f"byte[{key[4:]}]={extra_bytes[key]}")
    return ", " + ", ".join(parts)


def print_test(test_id: str, byte1: int, byte2: int, expected: str,
               **extra_bytes: int) -> None:
    """Print test header with expected outcome and prompt for observation."""
    extras = describe_extras(**extra_bytes)
    byte_info = f"byte[1]={byte1}, byte[2]={byte2}{extras}"
    print(f"\n{'─' * 64}")
    print(f"TEST {test_id}: {byte_info}")
    print(f"  Expected: {expected}")
    print(f"  Sending {SEND_COUNT} frames ({SEND_COUNT * SEND_DELAY_MS / 1000:.0f}s)...")


def prompt_observation() -> str:
    """Ask user what the display shows and return their response."""
    while True:
        response = input("  → What does the display show? ").strip()
        if response:
            return response
        print("    Please enter the displayed value (number, 'same', 'blank', etc.)")


# ─── Test Phases ────────────────────────────────────────────────────────────

def run_test_a(fd: int) -> List[dict]:
    """TEST A: Confirm byte[1] is the real temp slot."""
    print(f"\n{'=' * 64}")
    print("TEST A: Confirm byte[1] is the real temperature slot")
    print(f"{'=' * 64}")
    results = []

    # A.1: Both zero → display should show 0
    print_test("A.1", 0, 0, "display shows 0")
    send_frames(fd, make_payload(byte1=0, byte2=0))
    results.append({"test": "A.1", "desc": "byte[1]=0, byte[2]=0 → 0", "response": prompt_observation()})

    # A.2: byte[1]=0, byte[2]=70 → fallback shows 70
    print_test("A.2", 0, 70, "display shows 70 (fallback to byte[2])")
    send_frames(fd, make_payload(byte1=0, byte2=70))
    results.append({"test": "A.2", "desc": "byte[1]=0, byte[2]=70 → 70", "response": prompt_observation()})

    # A.3: byte[1]=70, byte[2]=0 → byte[1] takes priority, shows 70
    print_test("A.3", 70, 0, "display shows 70 (byte[1] takes priority)")
    send_frames(fd, make_payload(byte1=70, byte2=0))
    results.append({"test": "A.3", "desc": "byte[1]=70, byte[2]=0 → 70", "response": prompt_observation()})

    # A.4: byte[1]=70, byte[2]=70 → both agree, shows 70
    print_test("A.4", 70, 70, "display shows 70 (both agree)")
    send_frames(fd, make_payload(byte1=70, byte2=70))
    results.append({"test": "A.4", "desc": "byte[1]=70, byte[2]=70 → 70", "response": prompt_observation()})

    # A.5: byte[1]=88, byte[2]=70 → byte[1] wins, shows 88
    print_test("A.5", 88, 70, "display shows 88 (byte[1] wins)")
    send_frames(fd, make_payload(byte1=88, byte2=70))
    results.append({"test": "A.5", "desc": "byte[1]=88, byte[2]=70 → 88", "response": prompt_observation()})

    # A.6: byte[1]=0, byte[2]=88 → fallback, shows 88
    print_test("A.6", 0, 88, "display shows 88 (fallback to byte[2])")
    send_frames(fd, make_payload(byte1=0, byte2=88))
    results.append({"test": "A.6", "desc": "byte[1]=0, byte[2]=88 → 88", "response": prompt_observation()})

    return results


def run_test_b(fd: int) -> List[dict]:
    """TEST B: Find the priority rule."""
    print(f"\n{'=' * 64}")
    print("TEST B: Priority rule — does byte[1] ALWAYS win?")
    print(f"{'=' * 64}")
    results = []

    # B.1: byte[1]=1 vs byte[2]=88
    print_test("B.1", 1, 88, "display shows 1 or 88? (does byte[1] win even at 1?)")
    send_frames(fd, make_payload(byte1=1, byte2=88))
    results.append({"test": "B.1", "desc": "byte[1]=1 vs byte[2]=88", "response": prompt_observation()})

    # B.2: byte[1]=255 vs byte[2]=42
    print_test("B.2", 255, 42, "display shows 255 or 42? (does byte[1] win at 255?)")
    send_frames(fd, make_payload(byte1=255, byte2=42))
    results.append({"test": "B.2", "desc": "byte[1]=255 vs byte[2]=42", "response": prompt_observation()})

    # B.3: byte[1]=128 vs byte[2]=42
    print_test("B.3", 128, 42, "display shows 128 or 42? (byte[1]=128 mid-range)")
    send_frames(fd, make_payload(byte1=128, byte2=42))
    results.append({"test": "B.3", "desc": "byte[1]=128 vs byte[2]=42", "response": prompt_observation()})

    return results


def run_test_c(fd: int) -> List[dict]:
    """TEST C: Check if byte[1] is actually a different field (not temp)."""
    print(f"\n{'=' * 64}")
    print("TEST C: Is byte[1] a different field, not temp?")
    print(f"{'=' * 64}")
    results = []

    # C.1: byte[1]=70, byte[3]=50 → does display show 70 AND 50%?
    print_test("C.1", 70, 0, "does display show 70°C AND 50% usage? Or just 70?",
               byte3=50)
    send_frames(fd, make_payload(byte1=70, byte2=0, byte3=50))
    results.append({"test": "C.1", "desc": "byte[1]=70 + byte[3]=50 → 70 AND 50?", "response": prompt_observation()})

    # C.2: byte[1]=70, byte[4]=60 → does a second temp (60) appear?
    print_test("C.2", 70, 0, "does a second temp (60°C) appear somewhere?",
               byte4=60)
    send_frames(fd, make_payload(byte1=70, byte2=0, byte4=60))
    results.append({"test": "C.2", "desc": "byte[1]=70 + byte[4]=60 → second temp?", "response": prompt_observation()})

    # C.3: byte[1]=70, byte[10]=60 → does GPU temp appear?
    print_test("C.3", 70, 0, "does GPU temp (60°C) appear?",
               byte10=60)
    send_frames(fd, make_payload(byte1=70, byte2=0, byte10=60))
    results.append({"test": "C.3", "desc": "byte[1]=70 + byte[10]=60 → GPU temp?", "response": prompt_observation()})

    return results


def run_test_d(fd: int) -> List[dict]:
    """TEST D: Sweep byte[1] to find its displayable range."""
    print(f"\n{'=' * 64}")
    print("TEST D: Sweep byte[1] range")
    print(f"{'=' * 64}")
    results = []

    # D.1: byte[1]=100
    print_test("D.1", 100, 0, "display shows 100?")
    send_frames(fd, make_payload(byte1=100, byte2=0))
    results.append({"test": "D.1", "desc": "byte[1]=100 → 100?", "response": prompt_observation()})

    # D.2: byte[1]=150
    print_test("D.2", 150, 0, "display shows 150? (or wraps/ignores?)")
    send_frames(fd, make_payload(byte1=150, byte2=0))
    results.append({"test": "D.2", "desc": "byte[1]=150 → 150?", "response": prompt_observation()})

    # D.3: byte[1]=200
    print_test("D.3", 200, 0, "display shows 200? (or wraps/ignores?)")
    send_frames(fd, make_payload(byte1=200, byte2=0))
    results.append({"test": "D.3", "desc": "byte[1]=200 → 200?", "response": prompt_observation()})

    # D.4: byte[1]=255
    print_test("D.4", 255, 0, "display shows 255? (or wraps to 0?)")
    send_frames(fd, make_payload(byte1=255, byte2=0))
    results.append({"test": "D.4", "desc": "byte[1]=255 → 255?", "response": prompt_observation()})

    return results


def run_test_e(fd: int) -> List[dict]:
    """TEST E: Is byte[1] really temp, or a mode/flag?"""
    print(f"\n{'=' * 64}")
    print("TEST E: Is byte[1] temp or a mode/flag?")
    print(f"{'=' * 64}")
    results = []

    # E.1: byte[1]=70, everything else zero → just temp 70?
    print_test("E.1", 70, 0, "just temp 70°C? (all other bytes zero)")
    send_frames(fd, make_payload(byte1=70, byte2=0))
    results.append({"test": "E.1", "desc": "byte[1]=70, all others 0 → 70?", "response": prompt_observation()})

    # E.2: byte[1]=70, byte[3]=88 → temp 70 + CPU usage 88%?
    print_test("E.2", 70, 0, "temp 70°C + CPU usage 88%?",
               byte3=88)
    send_frames(fd, make_payload(byte1=70, byte2=0, byte3=88))
    results.append({"test": "E.2", "desc": "byte[1]=70 + byte[3]=88 → 70 + 88%?", "response": prompt_observation()})

    # E.3: byte[1]=70, byte[5]=88 → temp 70 + something 88?
    print_test("E.3", 70, 0, "temp 70°C + something 88?",
               byte5=88)
    send_frames(fd, make_payload(byte1=70, byte2=0, byte5=88))
    results.append({"test": "E.3", "desc": "byte[1]=70 + byte[5]=88 → 70 + 88?", "response": prompt_observation()})

    # E.4: byte[1]=70, byte[13]=88 → temp 70 + GPU usage 88%?
    print_test("E.4", 70, 0, "temp 70°C + GPU usage 88%?",
               byte13=88)
    send_frames(fd, make_payload(byte1=70, byte2=0, byte13=88))
    results.append({"test": "E.4", "desc": "byte[1]=70 + byte[13]=88 → 70 + 88%?", "response": prompt_observation()})

    return results


# ─── Summary ────────────────────────────────────────────────────────────────

def print_summary(all_results: List[dict]) -> None:
    """Print a compact summary of all test observations."""
    print(f"\n{'=' * 64}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 64}")

    for r in all_results:
        print(f"  {r['test']:>5}: {r['desc']}")
        print(f"        → observed: {r['response']}")

    print(f"\n{'─' * 64}")
    print("Review the observations above to confirm:")
    print("  • byte[1] takes priority over byte[2] for temperature display")
    print("  • byte[2] acts as fallback when byte[1] == 0")
    print("  • The valid range and any mode/flag behavior of byte[1]")
    print(f"{'─' * 64}")


# ─── Entry Point ────────────────────────────────────────────────────────────

def main() -> int:
    """Run all byte[1] confirmation tests interactively."""
    print("=" * 64)
    print("WALRUS ASSASSIN 90 — byte[1] TEMPERATURE CONFIRMATION")
    print("=" * 64)
    print(f"Device:      {DEVICE_PATH}")
    print(f"Frame:       {FRAME_SIZE} bytes (report ID 0x00 + 64-byte payload)")
    print(f"Send params: {SEND_COUNT} frames × {SEND_DELAY_MS}ms = {SEND_COUNT * SEND_DELAY_MS / 1000:.0f}s per test")
    print(f"Total tests: 17 (A:6 + B:3 + C:3 + D:4 + E:4 minus 1 shared = ~20 prompts)")
    print()
    print("Keep the display visible. For each test, report what you see.")
    print()

    # ── Guard: device exists ────────────────────────────────────────────
    if not os.path.exists(DEVICE_PATH):
        print(f"ERROR: Device not found at {DEVICE_PATH}")
        print("Check USB connection: ls /dev/hidraw*")
        return 1

    # ── Guard: can open device ──────────────────────────────────────────
    try:
        fd = os.open(DEVICE_PATH, os.O_WRONLY)
    except PermissionError:
        print(f"ERROR: Permission denied for {DEVICE_PATH}")
        print("Try: sudo chmod 666 /dev/hidraw5")
        print("Or:  sudo python3 probe_byte1.py")
        return 1
    except OSError as exc:
        print(f"ERROR: Cannot open {DEVICE_PATH}: {exc}")
        return 1

    all_results: List[dict] = []

    try:
        all_results.extend(run_test_a(fd))
        all_results.extend(run_test_b(fd))
        all_results.extend(run_test_c(fd))
        all_results.extend(run_test_d(fd))
        all_results.extend(run_test_e(fd))
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except OSError as exc:
        print(f"\nERROR during test: {exc}")
        return 1
    finally:
        os.close(fd)

    print_summary(all_results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
