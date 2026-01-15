"""Systemd service management using pkexec for authentication."""

import os
import subprocess
from enum import Enum


def is_flatpak() -> bool:
    """Check if running inside a Flatpak sandbox."""
    return os.path.exists("/.flatpak-info")


class ServiceState(Enum):
    """Possible states of a systemd service."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    ACTIVATING = "activating"
    DEACTIVATING = "deactivating"
    UNKNOWN = "unknown"


class SystemdClient:
    """Client for managing systemd services via systemctl + pkexec."""

    def __init__(self):
        self._in_flatpak = is_flatpak()

    def _run_command(self, cmd: list[str]) -> tuple[bool, str]:
        """Run a command, using flatpak-spawn if in Flatpak sandbox."""
        if self._in_flatpak:
            cmd = ["flatpak-spawn", "--host"] + cmd
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def _run_systemctl(self, *args: str, needs_root: bool = False) -> tuple[bool, str]:
        """Run systemctl command, optionally with pkexec for root access."""
        cmd = ["pkexec", "systemctl", *args] if needs_root else ["systemctl", *args]
        return self._run_command(cmd)

    def get_service_state(self, service_name: str) -> ServiceState:
        """Get the current state of a service."""
        success, output = self._run_systemctl("is-active", f"{service_name}.service")
        state_str = output.strip().lower()
        try:
            return ServiceState(state_str)
        except ValueError:
            return ServiceState.UNKNOWN

    def is_service_running(self, service_name: str) -> bool:
        """Check if a service is currently running."""
        return self.get_service_state(service_name) == ServiceState.ACTIVE

    def start_service(self, service_name: str) -> bool:
        """Start a service. Returns True on success."""
        success, output = self._run_systemctl("start", f"{service_name}.service", needs_root=True)
        if not success:
            print(f"Failed to start {service_name}: {output}")
        return success

    def stop_service(self, service_name: str) -> bool:
        """Stop a service. Returns True on success."""
        success, output = self._run_systemctl("stop", f"{service_name}.service", needs_root=True)
        if not success:
            print(f"Failed to stop {service_name}: {output}")
        return success

    def restart_service(self, service_name: str) -> bool:
        """Restart a service. Returns True on success."""
        success, output = self._run_systemctl("restart", f"{service_name}.service", needs_root=True)
        if not success:
            print(f"Failed to restart {service_name}: {output}")
        return success

    def is_service_installed(self, service_name: str) -> bool:
        """Check if a service unit file exists."""
        success, output = self._run_systemctl("cat", f"{service_name}.service")
        return success

    def get_logs(self, service_name: str, lines: int = 50) -> str:
        """Get recent log entries for a service."""
        cmd = ["journalctl", "-u", f"{service_name}.service", "-n", str(lines), "--no-pager"]
        success, output = self._run_command(cmd)
        return output if success else f"Failed to get logs: {output}"

    def is_service_enabled(self, service_name: str) -> bool:
        """Check if a service is enabled to start at boot."""
        success, output = self._run_systemctl("is-enabled", f"{service_name}.service")
        return output.strip().lower() == "enabled"

    def enable_service(self, service_name: str) -> bool:
        """Enable a service to start at boot."""
        success, output = self._run_systemctl("enable", f"{service_name}.service", needs_root=True)
        if not success:
            print(f"Failed to enable {service_name}: {output}")
        return success

    def disable_service(self, service_name: str) -> bool:
        """Disable a service from starting at boot."""
        success, output = self._run_systemctl("disable", f"{service_name}.service", needs_root=True)
        if not success:
            print(f"Failed to disable {service_name}: {output}")
        return success
