"""PHP version switching functionality."""

import subprocess
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .systemd_client import is_flatpak


@dataclass
class PhpVersion:
    """Represents an installed PHP version."""
    version: str  # e.g., "8.2", "8.3"
    binary_path: str  # e.g., "/usr/bin/php82"
    fpm_service: str  # e.g., "php82-fpm" or "php-fpm"
    is_default: bool = False


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
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def _get_php_version_from_binary(binary_path: str) -> Optional[str]:
    """Extract PHP version from a binary."""
    success, output = _run_shell(f"{binary_path} -v 2>/dev/null | head -1")
    if success and output:
        # Parse "PHP 8.3.1 (cli) ..." -> "8.3"
        match = re.search(r'PHP (\d+\.\d+)', output)
        if match:
            return match.group(1)
    return None


def get_installed_php_versions() -> list[PhpVersion]:
    """Detect all installed PHP versions."""
    versions = []
    seen_versions = set()

    # Check for default PHP
    default_version = _get_php_version_from_binary("/usr/bin/php")
    if default_version:
        versions.append(PhpVersion(
            version=default_version,
            binary_path="/usr/bin/php",
            fpm_service="php-fpm",
            is_default=True
        ))
        seen_versions.add(default_version)

    # Check for versioned PHP binaries (AUR style: php81, php82, php83)
    success, output = _run_shell("ls /usr/bin/php[0-9][0-9] 2>/dev/null")
    if success and output:
        for binary in output.splitlines():
            binary = binary.strip()
            if binary:
                version = _get_php_version_from_binary(binary)
                if version and version not in seen_versions:
                    # Derive service name from binary (php82 -> php82-fpm)
                    binary_name = Path(binary).name
                    fpm_service = f"{binary_name}-fpm"
                    versions.append(PhpVersion(
                        version=version,
                        binary_path=binary,
                        fpm_service=fpm_service,
                        is_default=False
                    ))
                    seen_versions.add(version)

    # Check for Debian/Ubuntu style (/usr/bin/php8.2)
    success, output = _run_shell("ls /usr/bin/php[0-9].[0-9] 2>/dev/null")
    if success and output:
        for binary in output.splitlines():
            binary = binary.strip()
            if binary:
                version = _get_php_version_from_binary(binary)
                if version and version not in seen_versions:
                    fpm_service = f"php{version}-fpm"
                    versions.append(PhpVersion(
                        version=version,
                        binary_path=binary,
                        fpm_service=fpm_service,
                        is_default=False
                    ))
                    seen_versions.add(version)

    return sorted(versions, key=lambda v: v.version, reverse=True)


def get_active_php_version() -> Optional[str]:
    """Get the currently active PHP-FPM version."""
    # Check which php-fpm service is running
    success, output = _run_shell("systemctl list-units --type=service --state=running | grep php.*fpm")
    if success and output:
        # Parse service name to get version
        for line in output.splitlines():
            match = re.search(r'php(\d+)-fpm|php(\d+\.\d+)-fpm|php-fpm', line)
            if match:
                if match.group(1):
                    # php82-fpm style -> 8.2
                    v = match.group(1)
                    return f"{v[0]}.{v[1]}" if len(v) == 2 else v
                elif match.group(2):
                    return match.group(2)
                else:
                    # Default php-fpm
                    return _get_php_version_from_binary("/usr/bin/php")
    return None


def switch_php_version(target_version: PhpVersion) -> tuple[bool, str]:
    """Switch to a different PHP version by managing FPM services."""
    versions = get_installed_php_versions()

    # Stop all other PHP-FPM services
    for v in versions:
        if v.version != target_version.version:
            _run_command(["pkexec", "systemctl", "stop", v.fpm_service])

    # Start the target PHP-FPM service
    success, output = _run_command(["pkexec", "systemctl", "start", target_version.fpm_service])
    if not success:
        return False, f"Failed to start {target_version.fpm_service}: {output}"

    return True, f"Switched to PHP {target_version.version}"


def has_multiple_versions() -> bool:
    """Check if multiple PHP versions are available."""
    return len(get_installed_php_versions()) > 1


def get_php_ini_path(version: PhpVersion) -> Optional[str]:
    """Get the php.ini path for a specific PHP version."""
    # Use the binary to find the loaded ini file
    success, output = _run_shell(f"{version.binary_path} --ini 2>/dev/null | grep 'Loaded Configuration' | awk '{{print $NF}}' | tr -d '\"'")
    if success and output and output != "(none)":
        return output

    # Fallback: check common locations
    common_paths = [
        f"/etc/php/{version.version}/fpm/php.ini",  # Debian/Ubuntu
        f"/etc/php/{version.version}/cli/php.ini",
        f"/etc/php{version.version.replace('.', '')}/php.ini",  # Arch AUR (php82)
        f"/etc/php/php.ini",  # Arch default
        f"/etc/php.ini",  # Some distros
    ]

    for path in common_paths:
        success, _ = _run_shell(f"test -f {path}")
        if success:
            return path

    return None
