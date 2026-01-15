"""Web server log viewing functionality."""

import subprocess
from pathlib import Path
from typing import Optional

from .systemd_client import is_flatpak


# Log file locations
NGINX_LOG_PATHS = {
    "access": [
        "/var/log/nginx/access.log",
        "/var/log/nginx/access.log.1",
    ],
    "error": [
        "/var/log/nginx/error.log",
        "/var/log/nginx/error.log.1",
    ],
}

PHP_ERROR_LOG_PATHS = [
    "/var/log/php-fpm/www-error.log",
    "/var/log/php-fpm/error.log",
    "/var/log/php/error.log",
    "/var/log/fpm-php.www.log",
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


def _find_log_file(paths: list[str]) -> Optional[str]:
    """Find the first existing log file from a list of paths."""
    for path in paths:
        if Path(path).exists():
            return path
    return None


def _read_log_file(path: str, lines: int = 100) -> tuple[str, str]:
    """Read the last N lines from a log file."""
    if not Path(path).exists():
        return f"Log file not found: {path}", path

    success, output = _run_shell(f"tail -n {lines} '{path}' 2>/dev/null")
    if success:
        return output if output.strip() else "(empty log file)", path
    return f"Failed to read log file: {path}", path


def get_nginx_access_log(lines: int = 100) -> tuple[str, str]:
    """Get nginx access log content."""
    log_path = _find_log_file(NGINX_LOG_PATHS["access"])
    if not log_path:
        return "Nginx access log not found", "No file"
    return _read_log_file(log_path, lines)


def get_nginx_error_log(lines: int = 100) -> tuple[str, str]:
    """Get nginx error log content."""
    log_path = _find_log_file(NGINX_LOG_PATHS["error"])
    if not log_path:
        return "Nginx error log not found (this is normal if there are no errors)", "No file"
    return _read_log_file(log_path, lines)


def get_php_error_log(lines: int = 100) -> tuple[str, str]:
    """Get PHP error log content."""
    # First try configured error_log from PHP
    success, output = _run_shell("php -i 2>/dev/null | grep '^error_log' | awk '{print $3}'")
    if success and output.strip() and output.strip() != "no" and Path(output.strip()).exists():
        return _read_log_file(output.strip(), lines)

    # Try common locations
    log_path = _find_log_file(PHP_ERROR_LOG_PATHS)
    if log_path:
        return _read_log_file(log_path, lines)

    # Fall back to journalctl with PHP errors filtered
    success, output = _run_shell(
        f"journalctl -u php-fpm -n {lines * 2} --no-pager 2>/dev/null | "
        "grep -iE 'error|warning|fatal|exception|parse' | tail -n {lines}"
    )
    if success and output.strip():
        return output, "journalctl -u php-fpm (filtered)"

    return "No PHP error log found. Configure error_log in php.ini", "No file"


def has_nginx_logs() -> bool:
    """Check if any nginx logs exist."""
    return bool(_find_log_file(NGINX_LOG_PATHS["access"]) or
                _find_log_file(NGINX_LOG_PATHS["error"]))
