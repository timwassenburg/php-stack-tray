"""PHP error log functionality."""

import subprocess
import re
from pathlib import Path
from typing import Optional

from .systemd_client import is_flatpak


# Common PHP error log locations
ERROR_LOG_PATHS = [
    "/var/log/php-fpm/error.log",
    "/var/log/php/error.log",
    "/var/log/fpm-php.www.log",
    "/var/log/php-fpm.log",
    "/var/log/php_errors.log",
]


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
        return result.returncode == 0, result.stdout
    except Exception as e:
        return False, str(e)


def _get_configured_error_log() -> Optional[str]:
    """Get the error_log path from PHP configuration."""
    # Check php.ini
    success, output = _run_shell("php -i 2>/dev/null | grep '^error_log' | head -1")
    if success and output:
        match = re.search(r'error_log\s*=>\s*(\S+)', output)
        if match and match.group(1) != "no":
            path = match.group(1)
            if Path(path).exists():
                return path

    # Check php-fpm pool config
    success, output = _run_shell(
        "grep -h 'php_admin_value\\[error_log\\]' /etc/php/php-fpm.d/*.conf 2>/dev/null | "
        "grep -v '^;' | head -1"
    )
    if success and output:
        match = re.search(r'=\s*(\S+)', output)
        if match:
            path = match.group(1)
            if Path(path).exists():
                return path

    return None


def _find_error_log() -> Optional[str]:
    """Find an existing PHP error log file."""
    # First check configured location
    configured = _get_configured_error_log()
    if configured:
        return configured

    # Check common locations
    for path in ERROR_LOG_PATHS:
        if Path(path).exists():
            return path

    return None


def get_php_error_log(lines: int = 100) -> tuple[str, str]:
    """
    Get PHP error log content.
    Returns (log_content, source_description)
    """
    # Try file-based log first
    log_path = _find_error_log()
    if log_path:
        success, output = _run_shell(f"tail -n {lines} '{log_path}' 2>/dev/null")
        if success and output.strip():
            return output, f"File: {log_path}"

    # Fall back to journalctl for php-fpm
    success, output = _run_shell(
        f"journalctl -u php-fpm -n {lines} --no-pager 2>/dev/null"
    )
    if success and output.strip():
        return output, "Source: journalctl -u php-fpm"

    # Try alternative service names
    for service in ["php-fpm", "php82-fpm", "php83-fpm", "php81-fpm"]:
        success, output = _run_shell(
            f"journalctl -u {service} -n {lines} --no-pager 2>/dev/null"
        )
        if success and output.strip():
            return output, f"Source: journalctl -u {service}"

    return "No PHP error logs found.", "No source"


def get_php_error_log_with_filter(lines: int = 100, filter_errors: bool = True) -> tuple[str, str]:
    """
    Get PHP error log content, optionally filtering for actual errors.
    Returns (log_content, source_description)
    """
    content, source = get_php_error_log(lines * 2)  # Get more lines to filter

    if filter_errors and content and "No PHP error logs found" not in content:
        # Filter for lines containing error indicators
        error_patterns = [
            "error", "fatal", "warning", "notice", "parse",
            "exception", "stack trace", "Error:", "PHP "
        ]
        filtered_lines = []
        for line in content.splitlines():
            line_lower = line.lower()
            if any(p in line_lower for p in error_patterns):
                filtered_lines.append(line)

        if filtered_lines:
            # Return last N lines
            return "\n".join(filtered_lines[-lines:]), source

    return content, source
