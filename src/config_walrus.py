#!/usr/bin/env python3
"""
walrus-config — interactive configuration for the Walrus Assassin 90 LCD driver

Reads/writes:  ~/.local/share/walrus-lcd/config.toml
Auto-restarts: systemctl --user restart cooler-lcd.service (if running)

Usage:
    walrus-config            # interactive editor
    walrus-config --show     # print current config and exit
    walrus-config --reset    # write defaults and exit (with confirmation)
    walrus-config --help     # print help
"""

import datetime
import os
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# TOML support (stdlib 3.11+, manual fallback)
# ---------------------------------------------------------------------------
try:
    import tomllib
except ImportError:
    tomllib = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULTS: dict = {
    "temp_source": "auto",
    "switch_seconds": 6,
    "refresh_ms": 200,
    "clamp_max": 89,
}

USAGE = """\
Usage: walrus-config [OPTION]

Interactive configuration for the Walrus Assassin 90 LCD driver.

Options:
  --show     Print current configuration and exit
  --reset    Reset configuration to defaults and exit (with confirmation)
  --help     Show this help message and exit

Without arguments, starts an interactive configuration editor.
Config file: {config_path}\
"""


# ---------------------------------------------------------------------------
# TOML parsing (mirrors walrus_lcd.py — standalone, no driver dependency)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Config path resolution
# ---------------------------------------------------------------------------
def _config_path() -> Path:
    """Resolve the config file path using the same logic as walrus_lcd.py.

    Search order (first match wins):
      1. ${WALRUS_LCD_CONFIG} env var (if set)
      2. ~/.local/share/walrus-lcd/config.toml (default)
    """
    env_override = os.environ.get("WALRUS_LCD_CONFIG", "").strip()
    if env_override:
        return Path(env_override)
    return Path.home() / ".local/share/walrus-lcd/config.toml"


def _config_dir(path: Path) -> Path:
    """Return the parent directory of the config file."""
    return path.parent


# ---------------------------------------------------------------------------
# Load config
# ---------------------------------------------------------------------------
def load_config() -> dict:
    """Load configuration from the TOML file, falling back to defaults.

    Returns a validated dict with keys:
      temp_source, switch_seconds, refresh_ms, clamp_max

    Raises SystemExit on malformed TOML or invalid values.
    """
    config_path = _config_path()

    if not config_path.is_file():
        return dict(DEFAULTS)

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
    cfg = {**DEFAULTS, **{k: v for k, v in raw.items() if k in DEFAULTS}}

    # Validate at boundary (Parse Don't Validate)
    if cfg["temp_source"] not in ("cpu", "gpu", "auto"):
        raise SystemExit(
            f"[!] Invalid temp_source={cfg['temp_source']!r} in {config_path}. "
            f"Must be one of: cpu, gpu, auto"
        )
    if not isinstance(cfg["switch_seconds"], int) or cfg["switch_seconds"] < 1:
        raise SystemExit(
            f"[!] Invalid switch_seconds={cfg['switch_seconds']!r} in {config_path}. "
            f"Must be an integer >= 1"
        )
    if not isinstance(cfg["refresh_ms"], int) or cfg["refresh_ms"] < 50:
        raise SystemExit(
            f"[!] Invalid refresh_ms={cfg['refresh_ms']!r} in {config_path}. "
            f"Must be an integer >= 50"
        )
    if not isinstance(cfg["clamp_max"], int) or cfg["clamp_max"] < 1 or cfg["clamp_max"] > 100:
        raise SystemExit(
            f"[!] Invalid clamp_max={cfg['clamp_max']!r} in {config_path}. "
            f"Must be an integer in range [1, 100]"
        )

    return cfg


# ---------------------------------------------------------------------------
# TOML writing
# ---------------------------------------------------------------------------
def _write_toml(path: Path, cfg: dict) -> None:
    """Write config as a flat TOML file with atomic rename.

    Format mirrors the driver's expected layout exactly.
    """
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    content = (
        f"# Walrus Assassin 90 LCD driver configuration\n"
        f"# Generated by walrus-config on {timestamp}\n"
        f"\n"
        f'temp_source = "{cfg["temp_source"]}"\n'
        f'switch_seconds = {cfg["switch_seconds"]}\n'
        f'refresh_ms = {cfg["refresh_ms"]}\n'
        f'clamp_max = {cfg["clamp_max"]}\n'
    )

    _config_dir(path).mkdir(parents=True, exist_ok=True)

    # Atomic write: write to .tmp in same directory, then rename
    fd, tmp_path = tempfile.mkstemp(
        dir=str(_config_dir(path)),
        prefix=".config_walrus_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except BaseException:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Service restart
# ---------------------------------------------------------------------------
SERVICE_NAME = "cooler-lcd.service"


def _restart_service_if_running() -> bool:
    """Restart cooler-lcd.service if it's active. Returns True if restarted."""
    import subprocess

    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False  # not active or no systemd
        subprocess.run(
            ["systemctl", "--user", "restart", SERVICE_NAME],
            capture_output=True,
            timeout=10,
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False  # silently — service may not be installed


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def _temp_source_label(value: str) -> str:
    """Human-readable label for temp_source values."""
    labels = {
        "cpu": "CPU only",
        "gpu": "GPU only",
        "auto": "CPU<->GPU alternating",
    }
    return labels.get(value, value)


def print_config_table(cfg: dict, indent: str = "  ") -> None:
    """Print config values in a formatted table."""
    print(f"{indent}temp_source     = {cfg['temp_source']}    ({_temp_source_label(cfg['temp_source'])})")
    print(f"{indent}switch_seconds = {cfg['switch_seconds']}")
    print(f"{indent}refresh_ms     = {cfg['refresh_ms']}")
    print(f"{indent}clamp_max      = {cfg['clamp_max']}")


# ---------------------------------------------------------------------------
# Interactive prompting
# ---------------------------------------------------------------------------
MAX_RETRIES = 5


def prompt_with_validation(
    prompt_text: str,
    current_value,
    *,
    parser=None,
    validator=None,
    error_message: str = "",
) -> object:
    """Prompt user for input, validate, and return parsed value.

    Empty input (just Enter) returns current_value unchanged.

    Args:
        prompt_text: Display prompt including the current value hint.
        current_value: The value to keep if user presses Enter.
        parser: Optional callable to parse the raw string to a typed value.
        validator: Optional callable that returns True if the parsed value is valid.
        error_message: Message shown on invalid input.

    Returns:
        The validated, parsed value.

    Raises:
        SystemExit: If max retries exceeded.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        raw = input(prompt_text).strip()

        # Empty = keep current
        if raw == "":
            return current_value

        # Parse
        if parser is not None:
            try:
                parsed = parser(raw)
            except (ValueError, TypeError):
                print(f"  [!] Invalid value: {error_message}")
                continue
        else:
            parsed = raw

        # Validate
        if validator is not None and not validator(parsed):
            print(f"  [!] Invalid value: {error_message}")
            continue

        return parsed

    # Max retries exceeded
    print(f"\n[!] Too many invalid attempts ({MAX_RETRIES}). Exiting.", file=sys.stderr)
    raise SystemExit(2)


# ---------------------------------------------------------------------------
# Parsers and validators
# ---------------------------------------------------------------------------
def _parse_temp_source(raw: str) -> str:
    value = raw.lower().strip()
    if value not in ("cpu", "gpu", "auto"):
        raise ValueError(f"must be one of: cpu, gpu, auto (got {value!r})")
    return value


def _parse_positive_int(min_value: int):
    """Return a parser/validator pair for int >= min_value."""
    def parser(raw: str) -> int:
        return int(raw)

    def validator(value: int) -> bool:
        return value >= min_value

    return parser, validator


def _parse_clamp_max(raw: str) -> int:
    return int(raw)


def _validate_clamp_max(value: int) -> bool:
    return 1 <= value <= 100


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_show() -> None:
    """Print current config and exit."""
    cfg = load_config()
    print_config_table(cfg)


def cmd_reset() -> None:
    """Reset config to defaults with confirmation, then restart service."""
    answer = input("Reset to defaults? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled.")
        return

    config_path = _config_path()
    _write_toml(config_path, DEFAULTS)
    print("Config reset to defaults.")

    restarted = _restart_service_if_running()
    if restarted:
        print(f"Service {SERVICE_NAME} restarted.")


def cmd_interactive() -> None:
    """Interactive configuration editor."""
    config_path = _config_path()
    current = load_config()

    print("🐋 Walrus LCD Configuration")
    print()
    print("Current configuration:")
    print_config_table(current)
    print()
    print("Edit values (press Enter to keep current):")
    print()

    try:
        # --- Temperature source ---
        new_temp_source = prompt_with_validation(
            f"  Temperature source [{current['temp_source']}] (cpu|gpu|auto): ",
            current["temp_source"],
            parser=_parse_temp_source,
            error_message="must be one of: cpu, gpu, auto",
        )

        # --- Switch seconds ---
        ss_parser, ss_validator = _parse_positive_int(1)
        new_switch_seconds = prompt_with_validation(
            f"  Switch seconds [{current['switch_seconds']}]: ",
            current["switch_seconds"],
            parser=ss_parser,
            validator=ss_validator,
            error_message="must be an integer >= 1",
        )

        # --- Refresh ms ---
        rm_parser, rm_validator = _parse_positive_int(50)
        new_refresh_ms = prompt_with_validation(
            f"  Refresh ms [{current['refresh_ms']}] (min 50): ",
            current["refresh_ms"],
            parser=rm_parser,
            validator=rm_validator,
            error_message="must be an integer >= 50",
        )

        # --- Clamp max ---
        new_clamp_max = prompt_with_validation(
            f"  Clamp max [{current['clamp_max']}] (1-100): ",
            current["clamp_max"],
            parser=_parse_clamp_max,
            validator=_validate_clamp_max,
            error_message="must be an integer in range [1, 100]",
        )
    except (EOFError, KeyboardInterrupt):
        print("\nNo changes made.")
        return

    # Build proposed config
    proposed: dict = {
        "temp_source": new_temp_source,
        "switch_seconds": new_switch_seconds,
        "refresh_ms": new_refresh_ms,
        "clamp_max": new_clamp_max,
    }

    print()
    print("New configuration:")
    print_config_table(proposed)
    print()

    # Confirm save
    try:
        save_answer = input("Save? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nNo changes made.")
        return

    if save_answer == "n":
        print("No changes made.")
        return

    _write_toml(config_path, proposed)
    print()
    print(f"\u2705 Saved to {config_path}")

    restarted = _restart_service_if_running()
    if restarted:
        print("\U0001f504 Service restarted.")
    else:
        print(f"\u2139\ufe0f  Service not running or not installed — restart manually if needed.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    args = sys.argv[1:]

    if not args:
        cmd_interactive()
        return

    flag = args[0]

    if flag in ("--help", "-h"):
        config_path = _config_path()
        print(USAGE.format(config_path=config_path))
        return

    if flag == "--show":
        cmd_show()
        return

    if flag == "--reset":
        cmd_reset()
        return

    print(f"[!] Unknown option: {flag}", file=sys.stderr)
    print("Run 'walrus-config --help' for usage.", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
