"""Tests for config_files.py module."""

import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from php_stack_tray import config_files
from php_stack_tray.config_files import ConfigFile


class TestFindFile:
    """Tests for _find_file function."""

    def test_find_first_existing(self, temp_dir):
        """Test finding first existing file."""
        file1 = temp_dir / "file1.conf"
        file2 = temp_dir / "file2.conf"
        file1.write_text("content1")
        file2.write_text("content2")

        result = config_files._find_file([
            str(file1),
            str(file2),
        ])

        assert result == str(file1)

    def test_find_second_when_first_missing(self, temp_dir):
        """Test finding second file when first doesn't exist."""
        file2 = temp_dir / "file2.conf"
        file2.write_text("content2")

        result = config_files._find_file([
            str(temp_dir / "nonexistent.conf"),
            str(file2),
        ])

        assert result == str(file2)

    def test_none_when_all_missing(self, temp_dir):
        """Test returning None when no files exist."""
        result = config_files._find_file([
            str(temp_dir / "nonexistent1.conf"),
            str(temp_dir / "nonexistent2.conf"),
        ])

        assert result is None

    def test_empty_list(self):
        """Test with empty list."""
        result = config_files._find_file([])
        assert result is None


class TestConfigFile:
    """Tests for ConfigFile dataclass."""

    def test_create_config_file(self):
        """Test creating a ConfigFile instance."""
        cf = ConfigFile(
            name="nginx.conf",
            path="/etc/nginx/nginx.conf",
            category="nginx"
        )

        assert cf.name == "nginx.conf"
        assert cf.path == "/etc/nginx/nginx.conf"
        assert cf.category == "nginx"


class TestGetNginxConfigs:
    """Tests for get_nginx_configs function."""

    def test_find_nginx_conf(self, temp_dir):
        """Test finding nginx.conf."""
        nginx_conf = temp_dir / "nginx.conf"
        nginx_conf.write_text("worker_processes 1;")

        with patch.object(config_files, '_find_file', side_effect=[
            str(nginx_conf),  # nginx.conf
            None,             # fastcgi
            None,             # mime.types
        ]):
            configs = config_files.get_nginx_configs()

        assert len(configs) >= 1
        assert any(c.name == "nginx.conf" for c in configs)

    def test_no_configs_found(self, temp_dir):
        """Test when no nginx configs exist."""
        with patch.object(config_files, '_find_file', return_value=None):
            configs = config_files.get_nginx_configs()

        assert configs == []


class TestGetPhpConfigs:
    """Tests for get_php_configs function."""

    def test_find_php_fpm_conf(self, temp_dir):
        """Test finding php-fpm.conf."""
        fpm_conf = temp_dir / "php-fpm.conf"
        fpm_conf.write_text("[global]")

        with patch.object(config_files, '_find_file', side_effect=[
            str(fpm_conf),  # php-fpm.conf
            None,           # www.conf
            None,           # xdebug.ini
        ]):
            configs = config_files.get_php_configs()

        assert len(configs) >= 1
        assert any(c.name == "php-fpm.conf" for c in configs)


class TestGetMysqlConfigs:
    """Tests for get_mysql_configs function."""

    def test_find_my_cnf(self, temp_dir):
        """Test finding my.cnf."""
        my_cnf = temp_dir / "my.cnf"
        my_cnf.write_text("[mysqld]")

        with patch.object(config_files, '_find_file', side_effect=[
            str(my_cnf),  # my.cnf
            None,         # mariadb
            None,         # mysql specific
        ]):
            configs = config_files.get_mysql_configs()

        assert len(configs) >= 1
        assert any(c.name == "my.cnf" for c in configs)


class TestGetHostsFile:
    """Tests for get_hosts_file function."""

    def test_hosts_exists(self):
        """Test when /etc/hosts exists (should always exist)."""
        result = config_files.get_hosts_file()

        # /etc/hosts should exist on any Linux system
        if Path("/etc/hosts").exists():
            assert result is not None
            assert result.name == "hosts"
            assert result.category == "system"


class TestGetAllConfigs:
    """Tests for get_all_configs function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        with patch.object(config_files, 'get_nginx_configs', return_value=[]):
            with patch.object(config_files, 'get_php_configs', return_value=[]):
                with patch.object(config_files, 'get_mysql_configs', return_value=[]):
                    with patch.object(config_files, 'get_hosts_file', return_value=None):
                        result = config_files.get_all_configs()

        assert isinstance(result, dict)

    def test_groups_by_category(self, temp_dir):
        """Test that configs are grouped by category."""
        nginx_conf = ConfigFile("nginx.conf", "/etc/nginx/nginx.conf", "nginx")
        php_conf = ConfigFile("php-fpm.conf", "/etc/php-fpm.conf", "php")

        with patch.object(config_files, 'get_nginx_configs', return_value=[nginx_conf]):
            with patch.object(config_files, 'get_php_configs', return_value=[php_conf]):
                with patch.object(config_files, 'get_mysql_configs', return_value=[]):
                    with patch.object(config_files, 'get_hosts_file', return_value=None):
                        result = config_files.get_all_configs()

        assert "Nginx" in result
        assert "PHP" in result
        assert len(result["Nginx"]) == 1
        assert len(result["PHP"]) == 1
