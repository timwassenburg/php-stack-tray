"""Tests for services.py module."""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from php_stack_tray.services import ServiceDefinition, ServiceRegistry, DEFAULT_SERVICES


class TestServiceDefinition:
    """Tests for ServiceDefinition dataclass."""

    def test_create_basic_service(self):
        """Test creating a basic service definition."""
        service = ServiceDefinition(
            name="nginx",
            display_name="Nginx",
            description="HTTP server"
        )

        assert service.name == "nginx"
        assert service.display_name == "Nginx"
        assert service.description == "HTTP server"
        assert service.icon is None
        assert service.conflicts is None
        assert service.version_cmd is None

    def test_create_service_with_conflicts(self):
        """Test creating a service with conflicts."""
        service = ServiceDefinition(
            name="mariadb",
            display_name="MariaDB",
            description="Database server",
            conflicts=["mysql"]
        )

        assert service.conflicts == ["mysql"]

    def test_create_service_with_version_cmd(self):
        """Test creating a service with version command."""
        service = ServiceDefinition(
            name="php-fpm",
            display_name="PHP-FPM",
            description="PHP FastCGI",
            version_cmd="php --version"
        )

        assert service.version_cmd == "php --version"


class TestServiceRegistry:
    """Tests for ServiceRegistry class."""

    def test_create_empty_registry(self):
        """Test creating registry with no services."""
        registry = ServiceRegistry(services=[])

        assert registry.get_all_services() == []

    def test_create_registry_with_services(self):
        """Test creating registry with services."""
        services = [
            ServiceDefinition("nginx", "Nginx", "Web server"),
            ServiceDefinition("mysql", "MySQL", "Database"),
        ]
        registry = ServiceRegistry(services=services)

        assert len(registry.get_all_services()) == 2

    def test_get_service_by_name(self):
        """Test getting service by name."""
        services = [
            ServiceDefinition("nginx", "Nginx", "Web server"),
            ServiceDefinition("mysql", "MySQL", "Database"),
        ]
        registry = ServiceRegistry(services=services)

        service = registry.get_service("nginx")

        assert service is not None
        assert service.name == "nginx"
        assert service.display_name == "Nginx"

    def test_get_nonexistent_service(self):
        """Test getting non-existent service returns None."""
        registry = ServiceRegistry(services=[])

        service = registry.get_service("nonexistent")

        assert service is None

    def test_add_service(self):
        """Test adding a service to registry."""
        registry = ServiceRegistry(services=[])
        new_service = ServiceDefinition("redis", "Redis", "Cache")

        registry.add_service(new_service)

        assert registry.get_service("redis") is not None
        assert len(registry.get_all_services()) == 1

    def test_remove_service(self):
        """Test removing a service from registry."""
        services = [
            ServiceDefinition("nginx", "Nginx", "Web server"),
        ]
        registry = ServiceRegistry(services=services)

        result = registry.remove_service("nginx")

        assert result is True
        assert registry.get_service("nginx") is None
        assert len(registry.get_all_services()) == 0

    def test_remove_nonexistent_service(self):
        """Test removing non-existent service returns False."""
        registry = ServiceRegistry(services=[])

        result = registry.remove_service("nonexistent")

        assert result is False

    def test_default_services_used_when_none(self):
        """Test that DEFAULT_SERVICES is used when no services provided."""
        registry = ServiceRegistry()

        services = registry.get_all_services()

        assert len(services) > 0
        assert len(services) == len(DEFAULT_SERVICES)


class TestDefaultServices:
    """Tests for DEFAULT_SERVICES list."""

    def test_nginx_included(self):
        """Test that nginx is in default services."""
        names = [s.name for s in DEFAULT_SERVICES]
        assert "nginx" in names

    def test_php_fpm_included(self):
        """Test that php-fpm is in default services."""
        names = [s.name for s in DEFAULT_SERVICES]
        assert "php-fpm" in names

    def test_mariadb_mysql_conflict(self):
        """Test that mariadb and mysql have conflict defined."""
        mariadb = next((s for s in DEFAULT_SERVICES if s.name == "mariadb"), None)
        mysql = next((s for s in DEFAULT_SERVICES if s.name == "mysql"), None)

        assert mariadb is not None
        assert mysql is not None
        assert "mysql" in mariadb.conflicts
        assert "mariadb" in mysql.conflicts

    def test_apache_httpd_conflict(self):
        """Test that apache2 and httpd have conflict defined."""
        apache2 = next((s for s in DEFAULT_SERVICES if s.name == "apache2"), None)
        httpd = next((s for s in DEFAULT_SERVICES if s.name == "httpd"), None)

        assert apache2 is not None
        assert httpd is not None
        assert "httpd" in apache2.conflicts
        assert "apache2" in httpd.conflicts

    def test_redis_included(self):
        """Test that redis is in default services."""
        names = [s.name for s in DEFAULT_SERVICES]
        assert "redis" in names

    def test_postgresql_included(self):
        """Test that postgresql is in default services."""
        names = [s.name for s in DEFAULT_SERVICES]
        assert "postgresql" in names

    def test_php_fpm_has_version_cmd(self):
        """Test that php-fpm has version command defined."""
        php_fpm = next((s for s in DEFAULT_SERVICES if s.name == "php-fpm"), None)

        assert php_fpm is not None
        assert php_fpm.version_cmd is not None
        assert "php" in php_fpm.version_cmd
