"""Xdebug toggle functionality."""

import subprocess
from pathlib import Path
from typing import Optional

from .systemd_client import is_flatpak


# Common Xdebug config locations
XDEBUG_CONFIG_PATHS = [
    # Arch Linux
    "/etc/php/conf.d/xdebug.ini",
    "/etc/php/conf.d/50-xdebug.ini",
    # Arch AUR versioned
    "/etc/php81/conf.d/xdebug.ini",
    "/etc/php82/conf.d/xdebug.ini",
    "/etc/php83/conf.d/xdebug.ini",
    "/etc/php84/conf.d/xdebug.ini",
    # Debian/Ubuntu
    "/etc/php/8.1/mods-available/xdebug.ini",
    "/etc/php/8.2/mods-available/xdebug.ini",
    "/etc/php/8.3/mods-available/xdebug.ini",
    "/etc/php/8.4/mods-available/xdebug.ini",
    # Fedora/RHEL/CentOS
    "/etc/php.d/xdebug.ini",
    "/etc/php.d/15-xdebug.ini",
    "/etc/php.d/20-xdebug.ini",
    # Alpine
    "/etc/php81/conf.d/xdebug.ini",
    "/etc/php82/conf.d/00_xdebug.ini",
]


def _run_command(cmd: list[str]) -> tuple[bool, str]:
    """Run a command, using flatpak-spawn if in Flatpak sandbox."""
    if is_flatpak():
        cmd = ["flatpak-spawn", "--host"] + cmd
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def _run_shell(cmd: str) -> tuple[bool, str]:
    """Run a shell command."""
    if is_flatpak():
        cmd = f"flatpak-spawn --host bash -c '{cmd}'"
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def is_xdebug_installed() -> bool:
    """Check if Xdebug is installed (config file exists)."""
    for path in XDEBUG_CONFIG_PATHS:
        if Path(path).exists() or Path(f"{path}.disabled").exists():
            return True
    # Also check if xdebug.so exists in common extension directories
    success, output = _run_shell(
        "php -m 2>/dev/null | grep -qi xdebug && echo yes || "
        "find /usr/lib/php*/modules /usr/lib64/php/modules /usr/lib/php/*/modules "
        "-name 'xdebug.so' 2>/dev/null | head -1"
    )
    return bool(output.strip())


def is_xdebug_enabled() -> bool:
    """Check if Xdebug is currently enabled."""
    success, output = _run_shell("php -m 2>/dev/null | grep -i xdebug")
    return "xdebug" in output.lower()


def get_xdebug_config_path() -> Optional[Path]:
    """Find the Xdebug config file path."""
    for path_str in XDEBUG_CONFIG_PATHS:
        path = Path(path_str)
        if path.exists():
            return path
        disabled_path = Path(f"{path_str}.disabled")
        if disabled_path.exists():
            return disabled_path
    return None


def _is_commented_config(config_path: Path) -> bool:
    """Check if the zend_extension line is commented out."""
    try:
        content = config_path.read_text()
        for line in content.splitlines():
            if "zend_extension" in line and "xdebug" in line.lower():
                return line.strip().startswith(";")
        return True  # No zend_extension line found, treat as disabled
    except Exception:
        return True


def enable_xdebug() -> tuple[bool, str]:
    """Enable Xdebug by uncommenting config or renaming file."""
    config_path = get_xdebug_config_path()
    if not config_path:
        return False, "Xdebug config file not found"

    # Handle .disabled file rename
    if str(config_path).endswith(".disabled"):
        new_path = str(config_path)[:-9]
        success, output = _run_command(["pkexec", "mv", str(config_path), new_path])
        if not success:
            return False, f"Failed to enable Xdebug: {output}"
        return True, "Xdebug enabled"

    # Handle commented config (Arch Linux style)
    if _is_commented_config(config_path):
        # Uncomment the zend_extension line
        success, output = _run_shell(
            f"pkexec sed -i 's/^;zend_extension=xdebug/zend_extension=xdebug/' {config_path}"
        )
        if not success:
            return False, f"Failed to enable Xdebug: {output}"
        return True, "Xdebug enabled"

    return True, "Xdebug is already enabled"


def disable_xdebug() -> tuple[bool, str]:
    """Disable Xdebug by commenting config or renaming file."""
    config_path = get_xdebug_config_path()
    if not config_path:
        return False, "Xdebug config file not found"

    if str(config_path).endswith(".disabled"):
        return True, "Xdebug is already disabled"

    # Check if it's a commented config
    if _is_commented_config(config_path):
        return True, "Xdebug is already disabled"

    # Comment out the zend_extension line (Arch Linux style)
    success, output = _run_shell(
        f"pkexec sed -i 's/^zend_extension=xdebug/;zend_extension=xdebug/' {config_path}"
    )
    if not success:
        return False, f"Failed to disable Xdebug: {output}"

    return True, "Xdebug disabled"


def toggle_xdebug() -> tuple[bool, str, bool]:
    """Toggle Xdebug on/off. Returns (success, message, new_state)."""
    if is_xdebug_enabled():
        success, msg = disable_xdebug()
        return success, msg, False
    else:
        success, msg = enable_xdebug()
        return success, msg, True
