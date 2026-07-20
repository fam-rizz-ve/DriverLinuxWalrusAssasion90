#!/usr/bin/env python3
"""
walrus_lcd.py
=============
Native Linux driver for the UPSIREN Walrus Assassin 90 cooler LCD display.

Device:   USB HID  VID 0x5131  PID 0x2007
Frame:    64-byte frame sent via raw /dev/hidraw*
          byte[0] = 0x00  (report ID, unused)
          byte[1] = 0x00  (ignored by firmware)
          byte[2] = temperature integer 0-89
          byte[3..64] = 0x00  (ignored by firmware)

Display range: 0-89°C valid, 90+ blinks (alarm), 120+ shows "h1" error.
Logo UPSIREN is baked into firmware, NOT controllable via HID.

Deps:
    pip install psutil pynvml
Run:
    python3 walrus_lcd.py
"""

import sys
import time
import glob
import os
import signal
import warnings
from pathlib import Path

import psutil

# ---- optional NVIDIA GPU (lazy init) -------------------------------------
warnings.filterwarnings("ignore", category=FutureWarning)
try:
    import pynvml
    _HAS_PYNVML = True
except Exception:
    _HAS_PYNVML = False

# ---- TOML support (stdlib 3.11+, manual fallback) ------------------------
try:
    import tomllib
except ImportError:
    tomllib = None  # type: ignore[assignment]


def _parse_toml_text(text: str) -> dict:
    """Minimal TOML parser for flat key=value files (fallback when tomllib absent).

    Handles only: key = "string", key = integer, key = float, and comments.
    Sufficient for the walrus-lcd config format.
    """
    result: dict = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, val = stripped.partition("=")
        key = key.strip()
        val = val.strip().strip('"')
        # Try int
        try:
            result[key] = int(val)
            continue
        except ValueError:
            pass
        # Try float
        try:
            result[key] = float(val)
            continue
        except ValueError:
            pass
        # String (already stripped of quotes)
        result[key] = val
    return result


def load_config() -> dict:
    """Load configuration from a TOML file with sane fallback defaults.

    Search order (first match wins):
      1. ${WALRUS_LCD_CONFIG} env var
      2. ~/.local/share/walrus-lcd/config.toml
      3. <script_dir>/config.toml
      4. None found → built-in defaults (no error)

    Returns a validated dict with keys:
      temp_source, switch_seconds, refresh_ms, clamp_max

    Raises ValueError on invalid config values or malformed TOML.
    """
    defaults = {
        "temp_source": "auto",
        "switch_seconds": 6,
        "refresh_ms": 200,
        "clamp_max": 89,
    }

    config_path: str | None = None
    candidates = []
    env_override = os.environ.get("WALRUS_LCD_CONFIG", "").strip()
    if env_override:
        candidates.append(Path(env_override))
    candidates.append(Path.home() / ".local/share/walrus-lcd/config.toml")
    candidates.append(Path(__file__).resolve().parent / "config.toml")

    for candidate in candidates:
        if candidate.is_file():
            config_path = str(candidate)
            break

    if config_path is None:
        return defaults

    # --- Parse TOML at the boundary ---------------------------------------
    try:
        if tomllib is not None:
            with open(config_path, "rb") as f:
                raw = tomllib.load(f)
        else:
            with open(config_path, "r") as f:
                raw = _parse_toml_text(f.read())
    except Exception as exc:
        raise SystemExit(f"[!] Failed to parse config file {config_path}: {exc}") from exc

    # Merge: raw values override defaults
    cfg = {**defaults, **{k: v for k, v in raw.items() if k in defaults}}

    # --- Validate at boundary (Parse Don't Validate) ----------------------
    # temp_source
    if cfg["temp_source"] not in ("cpu", "gpu", "auto"):
        raise SystemExit(
            f"[!] Invalid temp_source={cfg['temp_source']!r} in {config_path}. "
            f"Must be one of: cpu, gpu, auto"
        )
    # switch_seconds
    if not isinstance(cfg["switch_seconds"], int) or cfg["switch_seconds"] < 1:
        raise SystemExit(
            f"[!] Invalid switch_seconds={cfg['switch_seconds']!r} in {config_path}. "
            f"Must be an integer >= 1"
        )
    # refresh_ms
    if not isinstance(cfg["refresh_ms"], int) or cfg["refresh_ms"] < 50:
        raise SystemExit(
            f"[!] Invalid refresh_ms={cfg['refresh_ms']!r} in {config_path}. "
            f"Must be an integer >= 50"
        )
    # clamp_max
    if not isinstance(cfg["clamp_max"], int) or cfg["clamp_max"] < 1 or cfg["clamp_max"] > 100:
        raise SystemExit(
            f"[!] Invalid clamp_max={cfg['clamp_max']!r} in {config_path}. "
            f"Must be an integer in range [1, 100]"
        )

    return cfg


# ---- Load config and derive constants ------------------------------------
_cfg = load_config()
_config_source = "built-in defaults"
for _candidate in [
    os.environ.get("WALRUS_LCD_CONFIG", "").strip(),
    str(Path.home() / ".local/share/walrus-lcd/config.toml"),
    str(Path(__file__).resolve().parent / "config.toml"),
]:
    if _candidate and os.path.isfile(_candidate):
        _config_source = _candidate
        break

VID = 0x5131
PID = 0x2007
FRAME_SIZE = 64
REFRESH_S = _cfg["refresh_ms"] / 1000.0

# ---- Temperature display mode ------------------------------------------------
# "auto" = alternate between CPU and GPU temp every TEMP_SWITCH_S seconds
TEMP_MODE = _cfg["temp_source"]
TEMP_SWITCH_S = _cfg["switch_seconds"]
TEMP_MIN = 0                # firmware floor, not configurable
TEMP_MAX = _cfg["clamp_max"]
_TEMP_MODE_CYCLE = 0        # 0 = CPU, 1 = GPU in main field
_last_good_cpu_temp = 50.0  # cache for last valid CPU temp
_last_good_gpu_temp = 40.0  # cache for last valid GPU temp


# ---------------------------------------------------------------------------
# Walrus Assassin 90 frame encoder (pure function)
# ---------------------------------------------------------------------------
def build_walrus_frame(temp: int) -> bytes:
    """Build a 64-byte frame for the Walrus Assassin 90 display.

    Pure function: same input always produces the same output.
    byte[2] = temperature integer (0-89 valid range).
    All other bytes are 0x00 (ignored by firmware).

    Args:
        temp: Temperature integer to display.

    Returns:
        64-byte frame ready to write to hidraw device.
    """
    clamped = max(TEMP_MIN, min(TEMP_MAX, temp))
    if clamped != temp:
        print(f"[!] Temp {temp} clamped to {clamped}°C (display range {TEMP_MIN}-{TEMP_MAX}°C)")
    frame = bytearray(FRAME_SIZE)
    frame[2] = clamped
    return bytes(frame)


def build_shutdown_frame() -> bytes:
    """Build a frame that blanks the display to 0°C.

    No real shutdown opcode exists — firmware renders byte[2] as temperature.
    Setting it to 0 shows 0°C, the smallest valid value.
    """
    frame = bytearray(FRAME_SIZE)
    frame[2] = 0
    return bytes(frame)


# ---------------------------------------------------------------------------
# Raw hidraw device access
# ---------------------------------------------------------------------------
class HidrawDevice:
    def __init__(self, path: str):
        self.path = path
        self.fd = os.open(path, os.O_RDWR)

    def write(self, data: bytes) -> int:
        return os.write(self.fd, data)

    def close(self) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass


def find_hidraw(vid: int = VID, pid: int = PID) -> str | None:
    """Find /dev/hidraw* for specific USB VID:PID."""
    for path in sorted(glob.glob("/dev/hidraw*")):
        hid_n = path.replace("/dev/hidraw", "")
        uevent = f"/sys/class/hidraw/hidraw{hid_n}/device/uevent"
        try:
            with open(uevent) as f:
                content = f.read()
            if f"HID_ID=0003:{vid:08X}:{pid:08X}" in content:
                return path
        except (OSError, IOError):
            continue
    return None


def open_device() -> HidrawDevice | None:
    """Open the Walrus Assassin 90 HID device. Returns None on failure."""
    path = find_hidraw(VID, PID)
    if not path:
        print(f"[!] Cannot find /dev/hidraw* for {VID:#06x}:{PID:#06x}", file=sys.stderr)
        return None
    try:
        return HidrawDevice(path)
    except OSError as e:
        print(f"[!] Cannot open {path}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Sensor reading
# ---------------------------------------------------------------------------
def _read_int(path: str) -> int | None:
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError, TypeError):
        return None


class Sensors:
    """Reads CPU and GPU temperatures with caching."""

    def __init__(self):
        self._gpu = None
        self._gpu_last_try = 0.0
        self._ensure_gpu()

    def _ensure_gpu(self) -> None:
        if self._gpu is not None or not _HAS_PYNVML:
            return
        now = time.monotonic()
        if now - self._gpu_last_try < 5.0:
            return
        self._gpu_last_try = now
        try:
            pynvml.nvmlInit()
            self._gpu = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            self._gpu = None

    def cpu_temp(self) -> float:
        """Return CPU temperature, falling back to last good cached value."""
        global _last_good_cpu_temp
        t = psutil.sensors_temperatures()
        for key in ("k10temp", "coretemp", "zenpower"):
            if t.get(key):
                pkg = next((s for s in t[key] if s.label and ("Package" in s.label or "Tctl" in s.label)), None)
                val = float((pkg or t[key][0]).current)
                if val >= 10.0:
                    _last_good_cpu_temp = val
                    return val
        for key in t:
            for s in t[key]:
                if s.current >= 10.0:
                    _last_good_cpu_temp = float(s.current)
                    return float(s.current)
        return _last_good_cpu_temp

    def gpu_temp(self) -> float:
        """Return GPU temperature, or 0.0 if unavailable."""
        global _last_good_gpu_temp
        self._ensure_gpu()
        if not self._gpu:
            return 0.0
        try:
            val = float(pynvml.nvmlDeviceGetTemperature(self._gpu, pynvml.NVML_TEMPERATURE_GPU))
            if val >= 10.0:
                _last_good_gpu_temp = val
            return val
        except Exception:
            self._gpu = None
            return 0.0


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main() -> None:
    global _TEMP_MODE_CYCLE
    debug = "--print" in sys.argv

    # ---- Startup banner --------------------------------------------------
    print("Walrus Assassin 90 display driver")
    print(f"Config: {_config_source}")
    dev = open_device()
    if not dev:
        sys.exit(1)
    print(f"Device: {dev.path}")
    if TEMP_MODE == "cpu":
        print("Mode: CPU only")
    elif TEMP_MODE == "gpu":
        print("Mode: GPU only")
    else:
        print(f"Mode: CPU<->GPU alternation every {TEMP_SWITCH_S}s")
    print(f"Refresh: {REFRESH_S*1000:.0f}ms  |  Temp range: {TEMP_MIN}-{TEMP_MAX}°C (clamped)")
    print("Streaming sensors (Ctrl-C to stop).")

    sensors = Sensors()
    running = {"on": True}
    last_switch = time.monotonic()

    def stop(*_):
        running["on"] = False
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        while running["on"]:
            try:
                # Temperature alternation timer
                if TEMP_MODE == "auto":
                    now_t = time.monotonic()
                    if now_t - last_switch >= TEMP_SWITCH_S:
                        _TEMP_MODE_CYCLE = (_TEMP_MODE_CYCLE + 1) & 0x7FFFFFFF
                        last_switch = now_t

                # Decide which temperature to show
                show_gpu = (TEMP_MODE == "auto" and _TEMP_MODE_CYCLE % 2 == 1)
                if show_gpu:
                    gpu_t = sensors.gpu_temp()
                    if gpu_t > 0:
                        temp = gpu_t
                    else:
                        temp = sensors.cpu_temp()
                else:
                    temp = sensors.cpu_temp()

                # Build and send frame
                frame = build_walrus_frame(int(temp))
                dev.write(frame)

                if debug:
                    mode_label = ""
                    if TEMP_MODE == "auto":
                        mode_label = " [GPU]" if show_gpu else " [CPU]"
                    print(f"Temp: {temp:.0f}°C{mode_label}  ", end="\r", flush=True)

            except OSError:
                print("[!] Write failed, reconnecting...", file=sys.stderr)
                dev.close()
                time.sleep(1.0)
                dev = open_device()
                if not dev:
                    time.sleep(2.0)
                    dev = open_device()
                    if not dev:
                        break
                continue
            time.sleep(REFRESH_S)
    finally:
        if dev is not None:
            try:
                dev.write(build_shutdown_frame())
                dev.close()
            except Exception:
                pass
        print("\nStopped, screen released.")


if __name__ == "__main__":
    main()
