#!/usr/bin/env python3
"""
Walrus Assassin 90 — Opcode Structure Discovery Tool

HYPOTHESIS:
  byte[1] is an opcode that switches display modes/layouts.
  byte[2] is the temperature value (confirmed).
  When byte[1]=0, normal temp display from byte[2].
  When byte[1]=1-9, the firmware enters different display modes.

Device: /dev/hidraw5, 65-byte HID output reports
Frame:  byte[0]=0x00 (report ID), byte[1..64]=payload (64 bytes)

Phases:
  A — Confirm byte[2] is temp, find its full range
  B — Map byte[1] as opcode (what does each value do?)
  C — When byte[1]=1, where does temp come from?
  D — When byte[1]=2, where does temp come from?
  E — Find the shutdown/blank opcode
"""

import os
import sys
import time
from typing import List

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
        payload: 64 integers (0-255) for the payload portion of the frame.

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
        raise ValueError("All payload bytes must be in range 0-255")
    return bytes([REPORT_ID] + payload)


def make_payload(byte1: int = 0, byte2: int = 0, **extra_bytes: int) -> List[int]:
    """Create a zeroed 64-byte payload with specified bytes set.

    Args:
        byte1: Value for payload index 0 (= frame byte[1], the opcode).
        byte2: Value for payload index 1 (= frame byte[2], the temperature).
        extra_bytes: Additional positions as keyword args, e.g. byte3=88.

    Returns:
        64-element list of integers.

    Raises:
        ValueError: If any position is out of the 0-63 payload range.
    """
    payload = [0] * PAYLOAD_SIZE
    payload[0] = byte1
    payload[1] = byte2
    for key, value in extra_bytes.items():
        if not key.startswith("byte") or not key[4:].isdigit():
            raise ValueError(f"Invalid extra byte key: {key!r} — use byteN=<value>")
        index = int(key[4:]) - 1  # byte1 → index 0, byte2 → index 1, ...
        if index < 0 or index >= PAYLOAD_SIZE:
            raise ValueError(
                f"Position {key} maps to index {index}, "
                f"out of range 0-{PAYLOAD_SIZE - 1}"
            )
        payload[index] = value
    return payload


def send_frames(fd: int, payload: List[int], count: int = SEND_COUNT,
                delay_ms: int = SEND_DELAY_MS) -> None:
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
    """Print test header with expected outcome."""
    extras = describe_extras(**extra_bytes)
    byte_info = f"byte[1]={byte1}, byte[2]={byte2}{extras}"
    print(f"\n{'─' * 64}")
    print(f"TEST {test_id}: {byte_info}")
    print(f"  Expected: {expected}")
    print(f"  Sending {SEND_COUNT} frames ({SEND_COUNT * SEND_DELAY_MS / 1000:.0f}s)...")


def prompt_observation() -> str:
    """Ask user what the display shows and return their response."""
    while True:
        response = input(
            "  → What does the display show? "
            "(number, 'blank', 'blink', 'logo change', 'layout change', 'same'): "
        ).strip()
        if response:
            return response
        print("    Please enter a description of the display state.")


# ─── Test Phases ────────────────────────────────────────────────────────────

def run_phase_a(fd: int) -> List[dict]:
    """PHASE A: Confirm byte[2] is temp, find its full range."""
    print(f"\n{'=' * 64}")
    print("PHASE A: Confirm byte[2] is temperature, find full range")
    print(f"{'=' * 64}")
    results = []

    # A.1: byte[1]=0, byte[2]=0 → expect 0
    print_test("A.1", 0, 0, "display shows 0")
    send_frames(fd, make_payload(byte1=0, byte2=0))
    results.append({"test": "A.1", "desc": "byte[1]=0, byte[2]=0 → expect 0",
                     "response": prompt_observation()})

    # A.2: byte[1]=0, byte[2]=30 → expect 30
    print_test("A.2", 0, 30, "display shows 30")
    send_frames(fd, make_payload(byte1=0, byte2=30))
    results.append({"test": "A.2", "desc": "byte[1]=0, byte[2]=30 → expect 30",
                     "response": prompt_observation()})

    # A.3: byte[1]=0, byte[2]=60 → expect 60
    print_test("A.3", 0, 60, "display shows 60")
    send_frames(fd, make_payload(byte1=0, byte2=60))
    results.append({"test": "A.3", "desc": "byte[1]=0, byte[2]=60 → expect 60",
                     "response": prompt_observation()})

    # A.4: byte[1]=0, byte[2]=90 → expect 90
    print_test("A.4", 0, 90, "display shows 90")
    send_frames(fd, make_payload(byte1=0, byte2=90))
    results.append({"test": "A.4", "desc": "byte[1]=0, byte[2]=90 → expect 90",
                     "response": prompt_observation()})

    # A.5: byte[1]=0, byte[2]=120 → expect 120 (or wraps?)
    print_test("A.5", 0, 120, "display shows 120? (or wraps to lower value?)")
    send_frames(fd, make_payload(byte1=0, byte2=120))
    results.append({"test": "A.5", "desc": "byte[1]=0, byte[2]=120 → expect 120?",
                     "response": prompt_observation()})

    # A.6: byte[1]=0, byte[2]=200 → expect 200 (or wraps?)
    print_test("A.6", 0, 200, "display shows 200? (or wraps?)")
    send_frames(fd, make_payload(byte1=0, byte2=200))
    results.append({"test": "A.6", "desc": "byte[1]=0, byte[2]=200 → expect 200?",
                     "response": prompt_observation()})

    # A.7: byte[1]=0, byte[2]=255 → expect 255 (or wraps?)
    print_test("A.7", 0, 255, "display shows 255? (or wraps?)")
    send_frames(fd, make_payload(byte1=0, byte2=255))
    results.append({"test": "A.7", "desc": "byte[1]=0, byte[2]=255 → expect 255?",
                     "response": prompt_observation()})

    return results


def run_phase_b(fd: int) -> List[dict]:
    """PHASE B: Map byte[1] as opcode — what does each value do?"""
    print(f"\n{'=' * 64}")
    print("PHASE B: Map byte[1] as opcode — what does each value do?")
    print(f"{'=' * 64}")
    print("For each opcode, byte[2]=70 (baseline temp).")
    print("Observe: number, blank, blink, logo change, layout change.\n")
    results = []

    opcodes = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 255]

    for i, opcode in enumerate(opcodes, start=1):
        print_test(
            f"B.{i}", opcode, 70,
            f"opcode {opcode}: what does the display show?"
        )
        send_frames(fd, make_payload(byte1=opcode, byte2=70))
        results.append({
            "test": f"B.{i}",
            "desc": f"byte[1]={opcode}, byte[2]=70 → opcode behavior",
            "response": prompt_observation(),
        })

    return results


def run_phase_c(fd: int) -> List[dict]:
    """PHASE C: When byte[1]=1 (mode 1), where does temp come from?"""
    print(f"\n{'=' * 64}")
    print("PHASE C: When byte[1]=1, where does the temperature come from?")
    print(f"{'=' * 64}")
    print("Hypothesis: mode 1 shifts temp to a different byte position.\n")
    results = []

    # C.1: byte[1]=1, byte[2]=0, byte[3]=70
    print_test("C.1", 1, 0, "does display show 70? (temp moved to byte[3]?)",
               byte3=70)
    send_frames(fd, make_payload(byte1=1, byte2=0, byte3=70))
    results.append({"test": "C.1",
                     "desc": "byte[1]=1, byte[3]=70 → temp in byte[3]?",
                     "response": prompt_observation()})

    # C.2: byte[1]=1, byte[2]=0, byte[4]=70
    print_test("C.2", 1, 0, "does display show 70? (temp moved to byte[4]?)",
               byte4=70)
    send_frames(fd, make_payload(byte1=1, byte2=0, byte4=70))
    results.append({"test": "C.2",
                     "desc": "byte[1]=1, byte[4]=70 → temp in byte[4]?",
                     "response": prompt_observation()})

    # C.3: byte[1]=1, byte[2]=0, byte[5]=70
    print_test("C.3", 1, 0, "does display show 70? (temp moved to byte[5]?)",
               byte5=70)
    send_frames(fd, make_payload(byte1=1, byte2=0, byte5=70))
    results.append({"test": "C.3",
                     "desc": "byte[1]=1, byte[5]=70 → temp in byte[5]?",
                     "response": prompt_observation()})

    # C.4: byte[1]=1, byte[2]=0, byte[6]=70
    print_test("C.4", 1, 0, "does display show 70? (temp moved to byte[6]?)",
               byte6=70)
    send_frames(fd, make_payload(byte1=1, byte2=0, byte6=70))
    results.append({"test": "C.4",
                     "desc": "byte[1]=1, byte[6]=70 → temp in byte[6]?",
                     "response": prompt_observation()})

    # C.5: byte[1]=1, byte[2]=0, byte[7]=70
    print_test("C.5", 1, 0, "does display show 70? (temp moved to byte[7]?)",
               byte7=70)
    send_frames(fd, make_payload(byte1=1, byte2=0, byte7=70))
    results.append({"test": "C.5",
                     "desc": "byte[1]=1, byte[7]=70 → temp in byte[7]?",
                     "response": prompt_observation()})

    # C.6: byte[1]=1, byte[2]=0, byte[8]=70
    print_test("C.6", 1, 0, "does display show 70? (temp moved to byte[8]?)",
               byte8=70)
    send_frames(fd, make_payload(byte1=1, byte2=0, byte8=70))
    results.append({"test": "C.6",
                     "desc": "byte[1]=1, byte[8]=70 → temp in byte[8]?",
                     "response": prompt_observation()})

    # C.7: byte[1]=1, byte[2]=0, byte[9]=70
    print_test("C.7", 1, 0, "does display show 70? (temp moved to byte[9]?)",
               byte9=70)
    send_frames(fd, make_payload(byte1=1, byte2=0, byte9=70))
    results.append({"test": "C.7",
                     "desc": "byte[1]=1, byte[9]=70 → temp in byte[9]?",
                     "response": prompt_observation()})

    # C.8: byte[1]=1, byte[2]=0, byte[10]=70
    print_test("C.8", 1, 0, "does display show 70? (temp moved to byte[10]?)",
               byte10=70)
    send_frames(fd, make_payload(byte1=1, byte2=0, byte10=70))
    results.append({"test": "C.8",
                     "desc": "byte[1]=1, byte[10]=70 → temp in byte[10]?",
                     "response": prompt_observation()})

    return results


def run_phase_d(fd: int) -> List[dict]:
    """PHASE D: When byte[1]=2, where does temp come from?"""
    print(f"\n{'=' * 64}")
    print("PHASE D: When byte[1]=2, where does the temperature come from?")
    print(f"{'=' * 64}")
    print("Hypothesis: mode 2 shifts temp to yet another byte position.\n")
    results = []

    # D.1: byte[1]=2, byte[2]=0, byte[3]=70
    print_test("D.1", 2, 0, "does display show 70? (temp in byte[3]?)",
               byte3=70)
    send_frames(fd, make_payload(byte1=2, byte2=0, byte3=70))
    results.append({"test": "D.1",
                     "desc": "byte[1]=2, byte[3]=70 → temp in byte[3]?",
                     "response": prompt_observation()})

    # D.2: byte[1]=2, byte[2]=0, byte[4]=70
    print_test("D.2", 2, 0, "does display show 70? (temp in byte[4]?)",
               byte4=70)
    send_frames(fd, make_payload(byte1=2, byte2=0, byte4=70))
    results.append({"test": "D.2",
                     "desc": "byte[1]=2, byte[4]=70 → temp in byte[4]?",
                     "response": prompt_observation()})

    # D.3: byte[1]=2, byte[2]=0, byte[5]=70
    print_test("D.3", 2, 0, "does display show 70? (temp in byte[5]?)",
               byte5=70)
    send_frames(fd, make_payload(byte1=2, byte2=0, byte5=70))
    results.append({"test": "D.3",
                     "desc": "byte[1]=2, byte[5]=70 → temp in byte[5]?",
                     "response": prompt_observation()})

    # D.4: byte[1]=2, byte[2]=0, byte[6]=70
    print_test("D.4", 2, 0, "does display show 70? (temp in byte[6]?)",
               byte6=70)
    send_frames(fd, make_payload(byte1=2, byte2=0, byte6=70))
    results.append({"test": "D.4",
                     "desc": "byte[1]=2, byte[6]=70 → temp in byte[6]?",
                     "response": prompt_observation()})

    # D.5: byte[1]=2, byte[2]=0, byte[10]=70
    print_test("D.5", 2, 0, "does display show 70? (temp in byte[10]?)",
               byte10=70)
    send_frames(fd, make_payload(byte1=2, byte2=0, byte10=70))
    results.append({"test": "D.5",
                     "desc": "byte[1]=2, byte[10]=70 → temp in byte[10]?",
                     "response": prompt_observation()})

    return results


def run_phase_e(fd: int) -> List[dict]:
    """PHASE E: Find the shutdown/blank opcode."""
    print(f"\n{'=' * 64}")
    print("PHASE E: Find the shutdown/blank opcode")
    print(f"{'=' * 64}")
    print("Testing opcodes that might blank or shut down the display.\n")
    results = []

    # E.1: byte[1]=15, byte[2]=0 → Vevor uses 0x0F for shutdown
    print_test("E.1", 15, 0,
               "display goes blank? (0x0F = Vevor shutdown opcode)")
    send_frames(fd, make_payload(byte1=15, byte2=0))
    results.append({"test": "E.1",
                     "desc": "byte[1]=15 (0x0F) → blank/shutdown?",
                     "response": prompt_observation()})

    # E.2: byte[1]=16, byte[2]=0
    print_test("E.2", 16, 0, "display goes blank?")
    send_frames(fd, make_payload(byte1=16, byte2=0))
    results.append({"test": "E.2",
                     "desc": "byte[1]=16 → blank?",
                     "response": prompt_observation()})

    # E.3: byte[1]=255, byte[2]=0
    print_test("E.3", 255, 0, "display goes blank? (0xFF opcode)")
    send_frames(fd, make_payload(byte1=255, byte2=0))
    results.append({"test": "E.3",
                     "desc": "byte[1]=255 (0xFF) → blank?",
                     "response": prompt_observation()})

    # E.4: byte[1]=0xFF, all other bytes=0xFF
    print_test("E.4", 0xFF, 0, "display goes blank? (all 0xFF payload)")
    payload = [0xFF] * PAYLOAD_SIZE
    send_frames(fd, payload)
    results.append({"test": "E.4",
                     "desc": "all 0xFF payload → blank?",
                     "response": prompt_observation()})

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
    print("ANALYSIS NOTES:")
    print("  • byte[2] = temperature value (confirmed in Phase A)")
    print("  • byte[1] = opcode/mode flag (mapped in Phase B)")
    print("  • Phases C-D find where temp moves in non-zero modes")
    print("  • Phase E searches for blank/shutdown opcodes")
    print(f"{'─' * 64}")


# ─── Entry Point ────────────────────────────────────────────────────────────

def main() -> int:
    """Run all opcode discovery tests interactively."""
    print("=" * 64)
    print("WALRUS ASSASSIN 90 — OPCODE STRUCTURE DISCOVERY")
    print("=" * 64)
    print(f"Device:      {DEVICE_PATH}")
    print(f"Frame:       {FRAME_SIZE} bytes (report ID 0x00 + 64-byte payload)")
    print(f"Send params: {SEND_COUNT} frames x {SEND_DELAY_MS}ms = "
          f"{SEND_COUNT * SEND_DELAY_MS / 1000:.0f}s per test")
    print(f"Total tests: A:7 + B:14 + C:8 + D:5 + E:4 = 38 prompts")
    print()
    print("HYPOTHESIS: byte[1] is an opcode switching display modes.")
    print("  When byte[1]=0: normal temp from byte[2]")
    print("  When byte[1]=1-9: different display modes, temp from elsewhere")
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
        print("Or:  sudo python3 probe_opcode.py")
        return 1
    except OSError as exc:
        print(f"ERROR: Cannot open {DEVICE_PATH}: {exc}")
        return 1

    all_results: List[dict] = []

    try:
        all_results.extend(run_phase_a(fd))
        all_results.extend(run_phase_b(fd))
        all_results.extend(run_phase_c(fd))
        all_results.extend(run_phase_d(fd))
        all_results.extend(run_phase_e(fd))
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
