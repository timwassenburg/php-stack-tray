"""Tests for xdebug.py module."""

import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from php_stack_tray import xdebug


class TestIsCommentedConfig:
    """Tests for _is_commented_config function."""

    def test_enabled_config(self, temp_dir, sample_xdebug_config_enabled):
        """Test detection of enabled (uncommented) config."""
        config_file = temp_dir / "xdebug.ini"
        config_file.write_text(sample_xdebug_config_enabled)

        assert xdebug._is_commented_config(config_file) is False

    def test_disabled_config(self, temp_dir, sample_xdebug_config_disabled):
        """Test detection of disabled (commented) config."""
        config_file = temp_dir / "xdebug.ini"
        config_file.write_text(sample_xdebug_config_disabled)

        assert xdebug._is_commented_config(config_file) is True

    def test_config_with_spaces(self, temp_dir):
        """Test detection with spaces around semicolon."""
        config = """  ; zend_extension=xdebug
xdebug.mode=debug
"""
        config_file = temp_dir / "xdebug.ini"
        config_file.write_text(config)

        assert xdebug._is_commented_config(config_file) is True

    def test_config_without_zend_extension(self, temp_dir):
        """Test config without zend_extension line."""
        config = """xdebug.mode=debug
xdebug.client_host=localhost
"""
        config_file = temp_dir / "xdebug.ini"
        config_file.write_text(config)

        # No zend_extension line = treated as disabled
        assert xdebug._is_commented_config(config_file) is True

    def test_nonexistent_file(self, temp_dir):
        """Test non-existent file returns True (disabled)."""
        config_file = temp_dir / "nonexistent.ini"

        assert xdebug._is_commented_config(config_file) is True

    def test_zend_extension_with_path(self, temp_dir):
        """Test detection with full path to xdebug.so."""
        config = """zend_extension=/usr/lib/php/modules/xdebug.so
xdebug.mode=debug
"""
        config_file = temp_dir / "xdebug.ini"
        config_file.write_text(config)

        assert xdebug._is_commented_config(config_file) is False


class TestGetXdebugConfigPath:
    """Tests for get_xdebug_config_path function."""

    def test_find_existing_config(self, temp_dir):
        """Test finding existing config file."""
        config_file = temp_dir / "xdebug.ini"
        config_file.write_text("zend_extension=xdebug")

        with patch.object(xdebug, 'XDEBUG_CONFIG_PATHS', [str(config_file)]):
            result = xdebug.get_xdebug_config_path()
            assert result == config_file

    def test_find_disabled_config(self, temp_dir):
        """Test finding .disabled config file."""
        disabled_file = temp_dir / "xdebug.ini.disabled"
        disabled_file.write_text(";zend_extension=xdebug")

        with patch.object(xdebug, 'XDEBUG_CONFIG_PATHS', [
            str(temp_dir / "xdebug.ini"),  # doesn't exist
        ]):
            result = xdebug.get_xdebug_config_path()
            assert result == disabled_file

    def test_no_config_found(self, temp_dir):
        """Test when no config file exists."""
        with patch.object(xdebug, 'XDEBUG_CONFIG_PATHS', [
            str(temp_dir / "nonexistent1.ini"),
            str(temp_dir / "nonexistent2.ini"),
        ]):
            result = xdebug.get_xdebug_config_path()
            assert result is None


class TestXdebugConfigPaths:
    """Tests for XDEBUG_CONFIG_PATHS coverage."""

    def test_arch_paths_included(self):
        """Test that Arch Linux paths are included."""
        paths_str = " ".join(xdebug.XDEBUG_CONFIG_PATHS)
        assert "/etc/php/conf.d/xdebug.ini" in paths_str

    def test_debian_paths_included(self):
        """Test that Debian/Ubuntu paths are included."""
        paths_str = " ".join(xdebug.XDEBUG_CONFIG_PATHS)
        assert "/etc/php/8.2/mods-available/xdebug.ini" in paths_str

    def test_fedora_paths_included(self):
        """Test that Fedora/RHEL paths are included."""
        paths_str = " ".join(xdebug.XDEBUG_CONFIG_PATHS)
        assert "/etc/php.d/xdebug.ini" in paths_str

    def test_versioned_paths_included(self):
        """Test that versioned PHP paths are included."""
        paths_str = " ".join(xdebug.XDEBUG_CONFIG_PATHS)
        assert "php82" in paths_str or "php83" in paths_str
