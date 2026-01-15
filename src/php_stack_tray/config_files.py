"""Configuration file detection and access."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .systemd_client import is_flatpak
import subprocess


@dataclass
class ConfigFile:
    """Represents a configuration file."""
    name: str
    path: str
    category: str  # e.g., "nginx", "php", "mysql"


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


def _find_file(paths: list[str]) -> Optional[str]:
    """Find the first existing file from a list of paths."""
    for path in paths:
        if Path(path).exists():
            return path
    return None


def get_nginx_configs() -> list[ConfigFile]:
    """Get nginx configuration files."""
    configs = []

    # Main nginx.conf
    nginx_conf = _find_file([
        "/etc/nginx/nginx.conf",
        "/usr/local/etc/nginx/nginx.conf",
    ])
    if nginx_conf:
        configs.append(ConfigFile("nginx.conf", nginx_conf, "nginx"))

    # FastCGI params
    fastcgi = _find_file([
        "/etc/nginx/fastcgi_params",
        "/etc/nginx/fastcgi.conf",
    ])
    if fastcgi:
        configs.append(ConfigFile(Path(fastcgi).name, fastcgi, "nginx"))

    # Mime types
    mime = _find_file(["/etc/nginx/mime.types"])
    if mime:
        configs.append(ConfigFile("mime.types", mime, "nginx"))

    return configs


def get_php_configs() -> list[ConfigFile]:
    """Get PHP configuration files."""
    configs = []

    # PHP-FPM main config
    fpm_conf = _find_file([
        "/etc/php/php-fpm.conf",
        "/etc/php-fpm.conf",
        "/etc/php/8.3/fpm/php-fpm.conf",
        "/etc/php/8.2/fpm/php-fpm.conf",
    ])
    if fpm_conf:
        configs.append(ConfigFile("php-fpm.conf", fpm_conf, "php"))

    # PHP-FPM pool config (www.conf)
    pool_conf = _find_file([
        "/etc/php/php-fpm.d/www.conf",
        "/etc/php-fpm.d/www.conf",
        "/etc/php/8.3/fpm/pool.d/www.conf",
        "/etc/php/8.2/fpm/pool.d/www.conf",
    ])
    if pool_conf:
        configs.append(ConfigFile("www.conf (pool)", pool_conf, "php"))

    # Xdebug config
    xdebug_conf = _find_file([
        "/etc/php/conf.d/xdebug.ini",
        "/etc/php/conf.d/50-xdebug.ini",
        "/etc/php/8.3/mods-available/xdebug.ini",
        "/etc/php/8.2/mods-available/xdebug.ini",
    ])
    if xdebug_conf:
        configs.append(ConfigFile("xdebug.ini", xdebug_conf, "php"))

    return configs


def get_mysql_configs() -> list[ConfigFile]:
    """Get MySQL/MariaDB configuration files."""
    configs = []

    # Main my.cnf
    my_cnf = _find_file([
        "/etc/my.cnf",
        "/etc/mysql/my.cnf",
        "/etc/my.cnf.d/server.cnf",
    ])
    if my_cnf:
        configs.append(ConfigFile("my.cnf", my_cnf, "mysql"))

    # MariaDB specific
    mariadb_conf = _find_file([
        "/etc/my.cnf.d/mariadb-server.cnf",
        "/etc/mysql/mariadb.conf.d/50-server.cnf",
    ])
    if mariadb_conf:
        configs.append(ConfigFile(Path(mariadb_conf).name, mariadb_conf, "mysql"))

    return configs


def get_hosts_file() -> Optional[ConfigFile]:
    """Get the hosts file."""
    if Path("/etc/hosts").exists():
        return ConfigFile("hosts", "/etc/hosts", "system")
    return None


def get_all_configs() -> dict[str, list[ConfigFile]]:
    """Get all configuration files grouped by category."""
    configs = {}

    nginx = get_nginx_configs()
    if nginx:
        configs["Nginx"] = nginx

    php = get_php_configs()
    if php:
        configs["PHP"] = php

    mysql = get_mysql_configs()
    if mysql:
        configs["MySQL/MariaDB"] = mysql

    hosts = get_hosts_file()
    if hosts:
        configs["System"] = [hosts]

    return configs
