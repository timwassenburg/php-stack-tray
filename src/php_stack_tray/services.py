"""Service definitions and configuration."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ServiceDefinition:
    """Definition of a manageable service."""
    name: str  # systemd service name (without .service suffix)
    display_name: str  # Human-readable name for UI
    description: str
    icon: Optional[str] = None  # Optional icon name
    conflicts: Optional[list[str]] = None  # Services that conflict (aliases)
    version_cmd: Optional[str] = None  # Command to get version (e.g., "php --version")


# Default services to manage
# Note: Order matters - first matching service in a conflict group is shown
DEFAULT_SERVICES = [
    ServiceDefinition(
        name="nginx",
        display_name="Nginx",
        description="High-performance HTTP server and reverse proxy",
    ),
    ServiceDefinition(
        name="mariadb",
        display_name="MariaDB",
        description="MariaDB database server",
        conflicts=["mysql"],
    ),
    ServiceDefinition(
        name="mysql",
        display_name="MySQL",
        description="MySQL database server",
        conflicts=["mariadb"],
    ),
    ServiceDefinition(
        name="apache2",
        display_name="Apache",
        description="Apache HTTP Server",
        conflicts=["httpd"],
    ),
    ServiceDefinition(
        name="httpd",
        display_name="Apache (httpd)",
        description="Apache HTTP Server (RHEL/Fedora)",
        conflicts=["apache2"],
    ),
    ServiceDefinition(
        name="postgresql",
        display_name="PostgreSQL",
        description="PostgreSQL database server",
    ),
    ServiceDefinition(
        name="redis",
        display_name="Redis",
        description="Redis in-memory data store",
    ),
    ServiceDefinition(
        name="php-fpm",
        display_name="PHP-FPM",
        description="PHP FastCGI Process Manager",
        version_cmd="php --version | grep -oP '^PHP \\K[0-9]+\\.[0-9]+'",
    ),
]


class ServiceRegistry:
    """Registry of available services."""

    def __init__(self, services: Optional[list[ServiceDefinition]] = None):
        self._services = {s.name: s for s in (services or DEFAULT_SERVICES)}

    def get_service(self, name: str) -> Optional[ServiceDefinition]:
        """Get a service definition by name."""
        return self._services.get(name)

    def get_all_services(self) -> list[ServiceDefinition]:
        """Get all registered services."""
        return list(self._services.values())

    def add_service(self, service: ServiceDefinition) -> None:
        """Add a new service to the registry."""
        self._services[service.name] = service

    def remove_service(self, name: str) -> bool:
        """Remove a service from the registry."""
        if name in self._services:
            del self._services[name]
            return True
        return False
