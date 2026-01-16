"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


@pytest.fixture
def nginx_debian_style(temp_dir):
    """Create a Debian-style nginx sites structure."""
    sites_available = temp_dir / "sites-available"
    sites_enabled = temp_dir / "sites-enabled"
    sites_available.mkdir()
    sites_enabled.mkdir()
    return {
        "available": sites_available,
        "enabled": sites_enabled,
        "root": temp_dir,
    }


@pytest.fixture
def nginx_confd_style(temp_dir):
    """Create a conf.d-style nginx sites structure."""
    conf_d = temp_dir / "conf.d"
    conf_d.mkdir()
    return {
        "conf_d": conf_d,
        "root": temp_dir,
    }


@pytest.fixture
def sample_vhost_config():
    """Sample nginx vhost configuration."""
    return """server {
    listen 80;
    server_name example.local;
    root /var/www/example;
    index index.php index.html;

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \\.php$ {
        fastcgi_pass unix:/run/php-fpm/php-fpm.sock;
        fastcgi_index index.php;
        include fastcgi_params;
    }
}
"""


@pytest.fixture
def sample_xdebug_config_enabled():
    """Sample Xdebug config (enabled)."""
    return """zend_extension=xdebug
xdebug.mode=debug
xdebug.client_host=localhost
xdebug.client_port=9003
"""


@pytest.fixture
def sample_xdebug_config_disabled():
    """Sample Xdebug config (disabled/commented)."""
    return """;zend_extension=xdebug
xdebug.mode=debug
xdebug.client_host=localhost
xdebug.client_port=9003
"""
