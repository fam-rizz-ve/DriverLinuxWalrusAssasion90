#!/usr/bin/env python3
"""
Walrus Assassin 90 HID Frame Format Discovery Tool

This script systematically probes the device by sending structured test
frames, allowing the user to observe the display and identify which bytes
control various display fields (CPU temp, GPU temp, usage, fan RPM, etc.).

Device: VID=5131 (0x1403), PID=2007 (0x07D7)
Interface: /dev/hidraw5 (65-byte HID output reports)
Frame: byte[0]=0x00 (report ID), byte[1..64]=payload

CONFIRMED: byte[2] = CPU temperature
"""

import os
import sys
import time
from typing import List

# ─── Device Constants ───────────────────────────────────────────────────────
DEVICE_PATH = "/dev/hidraw5"
FRAME_SIZE = 65  # 1 byte report ID + 64 bytes payload
REPORT_ID = 0x00
BASELINE_TEMP = 70  # Known CPU temp value for visual confirmation


def build_frame(payload: List[int]) -> bytes:
    """
    Build a 65-byte HID frame with report ID and payload.

    Args:
        payload: List of 64 bytes (indices 0-63) for the frame payload

    Returns:
        65-byte frame ready for transmission
    """
    if len(payload) != FRAME_SIZE - 1:
        raise ValueError(f"Payload must be {FRAME_SIZE - 1} bytes, got {len(payload)}")

    frame = bytes([REPORT_ID] + payload)
    return frame


def send_frame(fd: int, payload: List[int], repetitions: int = 10, delay_ms: int = 200) -> None:
    """
    Send a frame multiple times to ensure display updates.

    Args:
        fd: File descriptor for HID device
        payload: 64-byte payload to send
        repetitions: Number of times to send the frame
        delay_ms: Milliseconds between each send
    """
    frame = build_frame(payload)
    for i in range(repetitions):
        os.write(fd, frame)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)


def print_test_header(test_id: str, description: str, bytes_changed: List[int], values: List[int]) -> None:
    """Print a clear test header showing what's being changed."""
    print(f"\n{'='*70}")
    print(f"TEST {test_id}: {description}")
    print(f"{'='*70}")
    byte_str = ", ".join(f"byte[{b}]={v}" for b, v in zip(bytes_changed, values))
    print(f"  Modifying: {byte_str}")
    print(f"  Baseline: byte[2]={BASELINE_TEMP} (CPU temp - should always show 70°C)")
    print(f"  Watching display for changes...")


def get_user_response() -> str:
    """Get Y/N response from user about display changes."""
    while True:
        response = input("  → Did the display change? (Y/N): ").strip().upper()
        if response in ('Y', 'N'):
            return response
        print("    Please enter Y or N")


def run_phase_1(fd: int) -> List[dict]:
    """PHASE 1: Confirm byte[2] and find other temperature slots."""
    results = []

    print(f"\n{'#'*70}")
    print("# PHASE 1: Temperature Slots")
    print(f"{'#'*70}")
    print("Testing which bytes control temperature display values.\n")

    # Test 1.1: Baseline - only byte[2] set
    payload = [0] * 64
    payload[2] = BASELINE_TEMP  # byte[2] = CPU temp
    print_test_header("1.1", "Baseline: Only byte[2]=70 (confirm CPU temp)", [2], [BASELINE_TEMP])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "1.1", "desc": "Baseline byte[2]=70", "response": response})

    # Test 1.2: Try byte[4] as GPU temp
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[4] = 50
    print_test_header("1.2", "byte[4]=50 (GPU temp candidate?)", [2, 4], [BASELINE_TEMP, 50])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "1.2", "desc": "byte[4]=50 GPU temp?", "response": response})

    # Test 1.3: Try byte[6] as GPU temp
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[6] = 50
    print_test_header("1.3", "byte[6]=50 (GPU temp candidate?)", [2, 6], [BASELINE_TEMP, 50])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "1.3", "desc": "byte[6]=50 GPU temp?", "response": response})

    # Test 1.4: Try byte[8] as GPU temp
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[8] = 50
    print_test_header("1.4", "byte[8]=50 (GPU temp candidate?)", [2, 8], [BASELINE_TEMP, 50])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "1.4", "desc": "byte[8]=50 GPU temp?", "response": response})

    # Test 1.5: Try byte[10] as GPU temp
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[10] = 50
    print_test_header("1.5", "byte[10]=50 (GPU temp candidate?)", [2, 10], [BASELINE_TEMP, 50])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "1.5", "desc": "byte[10]=50 GPU temp?", "response": response})

    # Test 1.6: Try byte[12] as GPU temp
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[12] = 50
    print_test_header("1.6", "byte[12]=50 (GPU temp candidate?)", [2, 12], [BASELINE_TEMP, 50])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "1.6", "desc": "byte[12]=50 GPU temp?", "response": response})

    # Test 1.7: Try byte[14] as GPU temp
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[14] = 50
    print_test_header("1.7", "byte[14]=50 (GPU temp candidate?)", [2, 14], [BASELINE_TEMP, 50])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "1.7", "desc": "byte[14]=50 GPU temp?", "response": response})

    return results


def run_phase_2(fd: int) -> List[dict]:
    """PHASE 2: Find usage/load slots."""
    results = []

    print(f"\n{'#'*70}")
    print("# PHASE 2: Usage/Load Slots")
    print(f"{'#'*70}")
    print("Testing which bytes control CPU/GPU/RAM usage percentage.\n")

    # Test 2.1: byte[3] as CPU usage
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[3] = 88
    print_test_header("2.1", "byte[3]=88 (CPU usage candidate?)", [2, 3], [BASELINE_TEMP, 88])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "2.1", "desc": "byte[3]=88 CPU usage?", "response": response})

    # Test 2.2: byte[5] as CPU usage
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[5] = 88
    print_test_header("2.2", "byte[5]=88 (CPU usage candidate?)", [2, 5], [BASELINE_TEMP, 88])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "2.2", "desc": "byte[5]=88 CPU usage?", "response": response})

    # Test 2.3: byte[7] as CPU usage
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[7] = 88
    print_test_header("2.3", "byte[7]=88 (CPU usage candidate?)", [2, 7], [BASELINE_TEMP, 88])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "2.3", "desc": "byte[7]=88 CPU usage?", "response": response})

    # Test 2.4: byte[9] as CPU usage
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[9] = 88
    print_test_header("2.4", "byte[9]=88 (CPU usage candidate?)", [2, 9], [BASELINE_TEMP, 88])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "2.4", "desc": "byte[9]=88 CPU usage?", "response": response})

    # Test 2.5: byte[11] as CPU usage
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[11] = 88
    print_test_header("2.5", "byte[11]=88 (CPU usage candidate?)", [2, 11], [BASELINE_TEMP, 88])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "2.5", "desc": "byte[11]=88 CPU usage?", "response": response})

    # Test 2.6: byte[13] as GPU usage
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[13] = 88
    print_test_header("2.6", "byte[13]=88 (GPU usage candidate?)", [2, 13], [BASELINE_TEMP, 88])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "2.6", "desc": "byte[13]=88 GPU usage?", "response": response})

    # Test 2.7: byte[15] as GPU usage
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[15] = 88
    print_test_header("2.7", "byte[15]=88 (GPU usage candidate?)", [2, 15], [BASELINE_TEMP, 88])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "2.7", "desc": "byte[15]=88 GPU usage?", "response": response})

    # Test 2.8: byte[30] as RAM usage
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[30] = 88
    print_test_header("2.8", "byte[30]=88 (RAM usage candidate?)", [2, 30], [BASELINE_TEMP, 88])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "2.8", "desc": "byte[30]=88 RAM usage?", "response": response})

    return results


def run_phase_3(fd: int) -> List[dict]:
    """PHASE 3: Find fan/RPM slots."""
    results = []

    print(f"\n{'#'*70}")
    print("# PHASE 3: Fan/Pump RPM Slots")
    print(f"{'#'*70}")
    print("Testing which bytes control fan and pump speed (RPM).\n")

    # Test 3.1: byte[18..19] as fan RPM (16-bit)
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[18] = 50
    payload[19] = 50
    print_test_header("3.1", "byte[18..19]=0x3232 (fan RPM candidate?)", [2, 18, 19], [BASELINE_TEMP, 50, 50])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "3.1", "desc": "byte[18..19]=50,50 fan RPM?", "response": response})

    # Test 3.2: byte[20..21] as pump RPM (16-bit)
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[20] = 50
    payload[21] = 50
    print_test_header("3.2", "byte[20..21]=0x3232 (pump RPM candidate?)", [2, 20, 21], [BASELINE_TEMP, 50, 50])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "3.2", "desc": "byte[20..21]=50,50 pump RPM?", "response": response})

    # Test 3.3: byte[16..17] as fan RPM (16-bit, big endian)
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[16] = 1
    payload[17] = 150  # ~300 RPM in big endian
    print_test_header("3.3", "byte[16..17]=0x0196 (fan RPM ~300 BE candidate?)", [2, 16, 17], [BASELINE_TEMP, 1, 150])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "3.3", "desc": "byte[16..17]=1,150 fan RPM BE?", "response": response})

    # Test 3.4: byte[22..23] as fan RPM (16-bit, big endian)
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[22] = 1
    payload[23] = 150
    print_test_header("3.4", "byte[22..23]=0x0196 (pump RPM ~300 BE candidate?)", [2, 22, 23], [BASELINE_TEMP, 1, 150])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "3.4", "desc": "byte[22..23]=1,150 pump RPM BE?", "response": response})

    return results


def run_phase_4(fd: int) -> List[dict]:
    """PHASE 4: Find date/time slots."""
    results = []

    print(f"\n{'#'*70}")
    print("# PHASE 4: Date/Time Slots")
    print(f"{'#'*70}")
    print("Testing which bytes control date and time display.\n")

    # Test 4.1: byte[24..27] as date (year, month, day, dow)
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[24] = 26  # Year 2026
    payload[25] = 7   # July
    payload[26] = 18  # Day 18
    payload[27] = 6   # Saturday
    print_test_header("4.1", "byte[24..27]=26,7,18,6 (date candidate: 2026-07-18 Sat?)", [2, 24, 25, 26, 27], [BASELINE_TEMP, 26, 7, 18, 6])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "4.1", "desc": "byte[24..27]=date 2026-07-18?", "response": response})

    # Test 4.2: byte[28..30] as time (hour, minute, second)
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[28] = 15  # 3 PM
    payload[29] = 30  # 30 minutes
    payload[30] = 45  # 45 seconds
    print_test_header("4.2", "byte[28..30]=15,30,45 (time candidate: 15:30:45?)", [2, 28, 29, 30], [BASELINE_TEMP, 15, 30, 45])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "4.2", "desc": "byte[28..30]=15,30,45 time?", "response": response})

    # Test 4.3: Alternative date encoding (day, month, year)
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[24] = 18  # Day
    payload[25] = 7   # Month
    payload[26] = 26  # Year
    payload[27] = 6   # Day of week
    print_test_header("4.3", "byte[24..27]=18,7,26,6 (date alt: 18/07/2026?)", [2, 24, 25, 26, 27], [BASELINE_TEMP, 18, 7, 26, 6])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "4.3", "desc": "byte[24..27]=18,7,26,6 date alt?", "response": response})

    return results


def run_phase_5(fd: int) -> List[dict]:
    """PHASE 5: Find logo/icon/layout bytes."""
    results = []

    print(f"\n{'#'*70}")
    print("# PHASE 5: Logo/Icon/Layout Control")
    print(f"{'#'*70}")
    print("Testing which bytes control display layout, icons, or logos.\n")

    # Test 5.1-5.9: byte[0] values 1-9
    for val in range(1, 10):
        payload = [0] * 64
        payload[2] = BASELINE_TEMP
        payload[0] = val
        print_test_header(f"5.{val}", f"byte[0]={val} (layout/icon candidate?)", [0, 2], [val, BASELINE_TEMP])
        send_frame(fd, payload)
        response = get_user_response()
        results.append({"test": f"5.{val}", "desc": f"byte[0]={val} layout?", "response": response})

    # Test 5.10-5.18: byte[1] values 1-9
    for i, val in enumerate(range(1, 10), start=10):
        payload = [0] * 64
        payload[2] = BASELINE_TEMP
        payload[1] = val
        print_test_header(f"5.{i}", f"byte[1]={val} (layout/icon candidate?)", [1, 2], [val, BASELINE_TEMP])
        send_frame(fd, payload)
        response = get_user_response()
        results.append({"test": f"5.{i}", "desc": f"byte[1]={val} layout?", "response": response})

    # Test 5.19: byte[63] = 0xFF pattern
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[63] = 0xFF
    print_test_header("5.19", "byte[63]=0xFF (layout/icon candidate?)", [2, 63], [BASELINE_TEMP, 0xFF])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "5.19", "desc": "byte[63]=0xFF layout?", "response": response})

    # Test 5.20: All bytes 30-63 = 0xFF
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    for i in range(30, 64):
        payload[i] = 0xFF
    print_test_header("5.20", "bytes[30..63]=0xFF (all ones in upper region)", [2], [BASELINE_TEMP])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "5.20", "desc": "bytes[30..63]=0xFF", "response": response})

    # Test 5.21: All bytes 30-63 = 0x55
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    for i in range(30, 64):
        payload[i] = 0x55
    print_test_header("5.21", "bytes[30..63]=0x55 (alternating pattern)", [2], [BASELINE_TEMP])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "5.21", "desc": "bytes[30..63]=0x55", "response": response})

    # Test 5.22: All bytes 30-63 = 0x00 with byte[30]=1
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[30] = 1
    print_test_header("5.22", "byte[30]=1 (layout/section selector?)", [2, 30], [BASELINE_TEMP, 1])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "5.22", "desc": "byte[30]=1 section?", "response": response})

    # Test 5.23: byte[30] = 2
    payload = [0] * 64
    payload[2] = BASELINE_TEMP
    payload[30] = 2
    print_test_header("5.23", "byte[30]=2 (layout/section selector?)", [2, 30], [BASELINE_TEMP, 2])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "5.23", "desc": "byte[30]=2 section?", "response": response})

    return results


def run_phase_6(fd: int) -> List[dict]:
    """PHASE 6: Multi-byte temperature encoding."""
    results = []

    print(f"\n{'#'*70}")
    print("# PHASE 6: Multi-byte Temperature Encoding")
    print(f"{'#'*70}")
    print("Testing if temperature uses 2 bytes for higher precision.\n")

    # Test 6.1: byte[2]=50, byte[3]=50
    payload = [0] * 64
    payload[2] = 50
    payload[3] = 50
    print_test_header("6.1", "byte[2]=50, byte[3]=50 (temp as 2 bytes?)", [2, 3], [50, 50])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "6.1", "desc": "byte[2]=50, byte[3]=50 temp?", "response": response})

    # Test 6.2: byte[2]=1, byte[3]=50 → temp = 1*100 + 50 = 150?
    payload = [0] * 64
    payload[2] = 1
    payload[3] = 50
    print_test_header("6.2", "byte[2]=1, byte[3]=50 (temp = 1*100+50=150?)", [2, 3], [1, 50])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "6.2", "desc": "byte[2]=1, byte[3]=50 → 150?", "response": response})

    # Test 6.3: byte[1]=1, byte[2]=50 → temp = 1*100 + 50 = 150?
    payload = [0] * 64
    payload[1] = 1
    payload[2] = 50
    print_test_header("6.3", "byte[1]=1, byte[2]=50 (temp = 1*100+50=150?)", [1, 2], [1, 50])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "6.3", "desc": "byte[1]=1, byte[2]=50 → 150?", "response": response})

    # Test 6.4: byte[2]=255, byte[3]=0 → temp = 255*100+0=25500?
    payload = [0] * 64
    payload[2] = 255
    payload[3] = 0
    print_test_header("6.4", "byte[2]=255, byte[3]=0 (temp = 255*100+0=25500?)", [2, 3], [255, 0])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "6.4", "desc": "byte[2]=255, byte[3]=0 → 25500?", "response": response})

    # Test 6.5: byte[2]=100, byte[3]=50 → temp = 100*100+50=10050?
    payload = [0] * 64
    payload[2] = 100
    payload[3] = 50
    print_test_header("6.5", "byte[2]=100, byte[3]=50 (temp = 100*100+50=10050?)", [2, 3], [100, 50])
    send_frame(fd, payload)
    response = get_user_response()
    results.append({"test": "6.5", "desc": "byte[2]=100, byte[3]=50 → 10050?", "response": response})

    return results


def print_summary(all_results: List[dict]) -> None:
    """Print a summary of all test results."""
    print(f"\n{'#'*70}")
    print("# TEST SUMMARY")
    print(f"{'#'*70}")

    positive = [r for r in all_results if r["response"] == "Y"]
    negative = [r for r in all_results if r["response"] == "N"]

    print(f"\nTotal tests: {len(all_results)}")
    print(f"Display changed: {len(positive)}")
    print(f"No change: {len(negative)}")

    if positive:
        print(f"\n{'='*50}")
        print("TESTS WHERE DISPLAY CHANGED:")
        print(f"{'='*50}")
        for r in positive:
            print(f"  Test {r['test']}: {r['desc']}")

    if negative:
        print(f"\n{'='*50}")
        print("TESTS WITH NO CHANGE:")
        print(f"{'='*50}")
        for r in negative:
            print(f"  Test {r['test']}: {r['desc']}")

    print(f"\n{'='*50}")
    print("NEXT STEPS:")
    print(f"{'='*50}")
    print("1. Review which tests caused display changes above")
    print("2. Note which bytes control which display fields")
    print("3. Refine with more tests on the discovered bytes")
    print("4. Document findings in a mapping file")


def main() -> int:
    """Main entry point for the probe script."""
    print("="*70)
    print("WALRUS ASSASSIN 90 HID FRAME FORMAT DISCOVERY TOOL")
    print("="*70)
    print(f"\nDevice: {DEVICE_PATH}")
    print(f"Frame size: {FRAME_SIZE} bytes (report ID + 64 byte payload)")
    print(f"Baseline CPU temp: {BASELINE_TEMP}°C")
    print(f"\nInstructions:")
    print(f"  1. Keep the display visible while running tests")
    print(f"  2. Watch for ANY change on the display")
    print(f"  3. Each test sends frames for ~2 seconds")
    print(f"  4. Answer Y if display changed, N if no change")
    print(f"\n{'='*70}")

    # Early exit: Check device exists
    if not os.path.exists(DEVICE_PATH):
        print(f"ERROR: Device not found at {DEVICE_PATH}")
        print("Check USB connection and try: ls /dev/hidraw*")
        return 1

    # Early exit: Check permissions
    try:
        fd = os.open(DEVICE_PATH, os.O_WRONLY)
    except PermissionError:
        print(f"ERROR: Permission denied for {DEVICE_PATH}")
        print("Try: sudo chmod 666 /dev/hidraw5")
        print("Or run: sudo python3 probe_frame.py")
        return 1
    except OSError as e:
        print(f"ERROR: Cannot open {DEVICE_PATH}: {e}")
        return 1

    all_results = []

    try:
        # Run all phases
        all_results.extend(run_phase_1(fd))
        all_results.extend(run_phase_2(fd))
        all_results.extend(run_phase_3(fd))
        all_results.extend(run_phase_4(fd))
        all_results.extend(run_phase_5(fd))
        all_results.extend(run_phase_6(fd))

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nERROR during testing: {e}")
        return 1
    finally:
        os.close(fd)

    # Print summary
    print_summary(all_results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
