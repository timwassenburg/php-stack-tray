"""Tests for vhosts.py module."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from php_stack_tray import vhosts


class TestParseVhostConfig:
    """Tests for _parse_vhost_config function."""

    def test_parse_server_name(self, temp_dir, sample_vhost_config):
        """Test parsing server_name from config."""
        config_file = temp_dir / "test.conf"
        config_file.write_text(sample_vhost_config)

        server_name, document_root = vhosts._parse_vhost_config(config_file)

        assert server_name == "example.local"

    def test_parse_document_root(self, temp_dir, sample_vhost_config):
        """Test parsing root from config."""
        config_file = temp_dir / "test.conf"
        config_file.write_text(sample_vhost_config)

        server_name, document_root = vhosts._parse_vhost_config(config_file)

        assert document_root == "/var/www/example"

    def test_parse_multiple_server_names(self, temp_dir):
        """Test parsing config with multiple server names."""
        config = """server {
    server_name example.local www.example.local;
    root /var/www/example;
}"""
        config_file = temp_dir / "test.conf"
        config_file.write_text(config)

        server_name, document_root = vhosts._parse_vhost_config(config_file)

        assert server_name == "example.local www.example.local"

    def test_parse_missing_server_name(self, temp_dir):
        """Test parsing config without server_name."""
        config = """server {
    root /var/www/example;
}"""
        config_file = temp_dir / "test.conf"
        config_file.write_text(config)

        server_name, document_root = vhosts._parse_vhost_config(config_file)

        assert server_name is None
        assert document_root == "/var/www/example"

    def test_parse_nonexistent_file(self, temp_dir):
        """Test parsing non-existent file returns None."""
        config_file = temp_dir / "nonexistent.conf"

        server_name, document_root = vhosts._parse_vhost_config(config_file)

        assert server_name is None
        assert document_root is None


class TestIsVhostConfig:
    """Tests for _is_vhost_config function."""

    def test_valid_vhost_config(self, temp_dir, sample_vhost_config):
        """Test detection of valid vhost config."""
        config_file = temp_dir / "test.conf"
        config_file.write_text(sample_vhost_config)

        assert vhosts._is_vhost_config(config_file) is True

    def test_non_vhost_config(self, temp_dir):
        """Test detection of non-vhost config (no server block)."""
        config = """# Some other nginx config
upstream backend {
    server 127.0.0.1:8080;
}
"""
        config_file = temp_dir / "upstream.conf"
        config_file.write_text(config)

        assert vhosts._is_vhost_config(config_file) is False

    def test_empty_file(self, temp_dir):
        """Test empty file returns False."""
        config_file = temp_dir / "empty.conf"
        config_file.write_text("")

        assert vhosts._is_vhost_config(config_file) is False


class TestDetectNginxStyle:
    """Tests for _detect_nginx_style function."""

    def test_detect_debian_style(self, temp_dir):
        """Test detection of Debian-style nginx config."""
        sites_available = temp_dir / "sites-available"
        sites_available.mkdir()

        with patch.object(vhosts, 'NGINX_PATHS', {
            "debian": {
                "available": sites_available,
                "enabled": temp_dir / "sites-enabled",
                "uses_symlinks": True,
            },
            "conf.d": {
                "available": temp_dir / "conf.d",
                "enabled": temp_dir / "conf.d",
                "uses_symlinks": False,
            },
        }):
            style = vhosts._detect_nginx_style()
            assert style["uses_symlinks"] is True
            assert style["available"] == sites_available

    def test_detect_confd_style(self, temp_dir):
        """Test detection of conf.d-style nginx config."""
        conf_d = temp_dir / "conf.d"
        conf_d.mkdir()

        with patch.object(vhosts, 'NGINX_PATHS', {
            "debian": {
                "available": temp_dir / "sites-available",  # doesn't exist
                "enabled": temp_dir / "sites-enabled",
                "uses_symlinks": True,
            },
            "conf.d": {
                "available": conf_d,
                "enabled": conf_d,
                "uses_symlinks": False,
            },
        }):
            style = vhosts._detect_nginx_style()
            assert style["uses_symlinks"] is False
            assert style["available"] == conf_d


class TestDetectPhpFpmSocket:
    """Tests for _detect_php_fpm_socket function."""

    def test_detect_existing_socket(self, temp_dir):
        """Test detection of existing PHP-FPM socket."""
        socket_path = temp_dir / "php-fpm.sock"
        socket_path.touch()

        with patch.object(vhosts, 'PHP_FPM_SOCKET_PATHS', [str(socket_path)]):
            result = vhosts._detect_php_fpm_socket()
            assert result == str(socket_path)

    def test_fallback_when_no_socket(self, temp_dir):
        """Test fallback when no socket exists."""
        with patch.object(vhosts, 'PHP_FPM_SOCKET_PATHS', [
            str(temp_dir / "nonexistent1.sock"),
            str(temp_dir / "nonexistent2.sock"),
        ]):
            result = vhosts._detect_php_fpm_socket()
            # Should return default fallback
            assert result == "/run/php-fpm/php-fpm.sock"


class TestGetVhostTemplate:
    """Tests for _get_vhost_template function."""

    def test_template_contains_socket(self):
        """Test that template includes the provided socket path."""
        socket = "/run/php/php8.2-fpm.sock"
        template = vhosts._get_vhost_template(socket)

        assert socket in template
        assert "fastcgi_pass unix:" in template

    def test_template_has_placeholders(self):
        """Test that template has required placeholders."""
        template = vhosts._get_vhost_template("/test.sock")

        assert "{server_name}" in template
        assert "{document_root}" in template
        assert "{name}" in template
