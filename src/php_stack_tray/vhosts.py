"""Virtual hosts management for Nginx."""

import subprocess
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .systemd_client import is_flatpak


# Nginx path configurations for different distros
NGINX_PATHS = {
    "debian": {  # Debian, Ubuntu
        "available": Path("/etc/nginx/sites-available"),
        "enabled": Path("/etc/nginx/sites-enabled"),
        "uses_symlinks": True,
    },
    "conf.d": {  # Arch, Fedora, RHEL, Alpine
        "available": Path("/etc/nginx/conf.d"),
        "enabled": Path("/etc/nginx/conf.d"),
        "uses_symlinks": False,
    },
}

HOSTS_FILE = Path("/etc/hosts")

# Common PHP-FPM socket locations
PHP_FPM_SOCKET_PATHS = [
    "/run/php-fpm/php-fpm.sock",      # Arch
    "/run/php-fpm/www.sock",          # Arch alternative
    "/var/run/php-fpm/php-fpm.sock",  # Some distros
    "/var/run/php-fpm/www.sock",      # CentOS/RHEL
    "/run/php/php-fpm.sock",          # Debian/Ubuntu
    "/var/run/php/php-fpm.sock",      # Debian/Ubuntu alternative
    "/run/php/php8.3-fpm.sock",       # Debian versioned
    "/run/php/php8.2-fpm.sock",       # Debian versioned
    "/run/php/php8.1-fpm.sock",       # Debian versioned
]


@dataclass
class VirtualHost:
    """Represents a virtual host configuration."""
    name: str
    config_path: Path
    enabled: bool
    server_name: Optional[str] = None
    document_root: Optional[str] = None


def _detect_nginx_style() -> dict:
    """Detect which nginx configuration style is used."""
    # Check Debian-style first (more specific)
    if NGINX_PATHS["debian"]["available"].exists():
        return NGINX_PATHS["debian"]
    # Fall back to conf.d style
    if NGINX_PATHS["conf.d"]["available"].exists():
        return NGINX_PATHS["conf.d"]
    # Default to Debian style if nothing exists yet
    return NGINX_PATHS["debian"]


def _detect_php_fpm_socket() -> str:
    """Detect the PHP-FPM socket path."""
    for socket_path in PHP_FPM_SOCKET_PATHS:
        if Path(socket_path).exists():
            return socket_path
    # Default fallback
    return "/run/php-fpm/php-fpm.sock"


def _get_vhost_template(php_socket: str) -> str:
    """Get the nginx vhost template with the correct PHP-FPM socket."""
    return """server {{
    listen 80;
    server_name {server_name};
    root {document_root};
    index index.php index.html;

    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}

    location ~ \\.php$ {{
        fastcgi_pass unix:{php_socket};
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
    }}

    location ~ /\\.ht {{
        deny all;
    }}

    error_log /var/log/nginx/{{name}}_error.log;
    access_log /var/log/nginx/{{name}}_access.log;
}}
""".replace("{php_socket}", php_socket)


def _run_command(cmd: list[str]) -> tuple[bool, str]:
    """Run a command, using flatpak-spawn if in Flatpak sandbox."""
    if is_flatpak():
        cmd = ["flatpak-spawn", "--host"] + cmd
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


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


def _parse_vhost_config(config_path: Path) -> tuple[Optional[str], Optional[str]]:
    """Parse server_name and root from nginx config."""
    server_name = None
    document_root = None

    try:
        content = config_path.read_text()

        # Extract server_name
        match = re.search(r'server_name\s+([^;]+);', content)
        if match:
            server_name = match.group(1).strip()

        # Extract root
        match = re.search(r'^\s*root\s+([^;]+);', content, re.MULTILINE)
        if match:
            document_root = match.group(1).strip()

    except Exception:
        pass

    return server_name, document_root


def _is_vhost_config(config_path: Path) -> bool:
    """Check if a config file is a virtual host (has server block)."""
    try:
        content = config_path.read_text()
        return bool(re.search(r'server\s*\{', content))
    except Exception:
        return False


def get_virtual_hosts() -> list[VirtualHost]:
    """Get list of all virtual hosts."""
    vhosts = []
    nginx_style = _detect_nginx_style()
    sites_available = nginx_style["available"]
    sites_enabled = nginx_style["enabled"]
    uses_symlinks = nginx_style["uses_symlinks"]

    if not sites_available.exists():
        return vhosts

    if uses_symlinks:
        # Debian-style: sites-available + sites-enabled symlinks
        enabled_sites = set()
        if sites_enabled.exists():
            for link in sites_enabled.iterdir():
                if link.is_symlink():
                    target = link.resolve()
                    enabled_sites.add(target.name)

        for config_file in sites_available.iterdir():
            if config_file.is_file() and not config_file.name.startswith('.'):
                server_name, document_root = _parse_vhost_config(config_file)
                vhosts.append(VirtualHost(
                    name=config_file.name,
                    config_path=config_file,
                    enabled=config_file.name in enabled_sites,
                    server_name=server_name,
                    document_root=document_root
                ))
    else:
        # conf.d style: all .conf files are enabled
        for config_file in sites_available.iterdir():
            # Only include .conf files that contain server blocks
            if config_file.is_file() and config_file.suffix == '.conf':
                if _is_vhost_config(config_file):
                    server_name, document_root = _parse_vhost_config(config_file)
                    # Check if disabled (renamed to .conf.disabled)
                    vhosts.append(VirtualHost(
                        name=config_file.stem,  # Remove .conf
                        config_path=config_file,
                        enabled=True,
                        server_name=server_name,
                        document_root=document_root
                    ))

        # Also check for disabled configs (.conf.disabled)
        for config_file in sites_available.iterdir():
            if config_file.is_file() and config_file.name.endswith('.conf.disabled'):
                if _is_vhost_config(config_file):
                    server_name, document_root = _parse_vhost_config(config_file)
                    vhosts.append(VirtualHost(
                        name=config_file.name.replace('.conf.disabled', ''),
                        config_path=config_file,
                        enabled=False,
                        server_name=server_name,
                        document_root=document_root
                    ))

    return sorted(vhosts, key=lambda v: v.name)


def enable_vhost(name: str) -> tuple[bool, str]:
    """Enable a virtual host."""
    nginx_style = _detect_nginx_style()
    uses_symlinks = nginx_style["uses_symlinks"]

    if uses_symlinks:
        # Debian-style: create symlink
        source = nginx_style["available"] / name
        target = nginx_style["enabled"] / name

        if not source.exists():
            return False, f"Virtual host '{name}' not found"

        if target.exists():
            return True, "Virtual host already enabled"

        success, output = _run_command([
            "pkexec", "ln", "-s", str(source), str(target)
        ])

        if not success:
            return False, f"Failed to enable: {output}"
    else:
        # conf.d style: rename from .conf.disabled to .conf
        disabled_path = nginx_style["available"] / f"{name}.conf.disabled"
        enabled_path = nginx_style["available"] / f"{name}.conf"

        if enabled_path.exists():
            return True, "Virtual host already enabled"

        if not disabled_path.exists():
            return False, f"Virtual host '{name}' not found"

        success, output = _run_command([
            "pkexec", "mv", str(disabled_path), str(enabled_path)
        ])

        if not success:
            return False, f"Failed to enable: {output}"

    # Reload nginx
    _run_command(["pkexec", "systemctl", "reload", "nginx"])
    return True, "Virtual host enabled"


def disable_vhost(name: str) -> tuple[bool, str]:
    """Disable a virtual host."""
    nginx_style = _detect_nginx_style()
    uses_symlinks = nginx_style["uses_symlinks"]

    if uses_symlinks:
        # Debian-style: remove symlink
        target = nginx_style["enabled"] / name

        if not target.exists():
            return True, "Virtual host already disabled"

        success, output = _run_command(["pkexec", "rm", str(target)])

        if not success:
            return False, f"Failed to disable: {output}"
    else:
        # conf.d style: rename from .conf to .conf.disabled
        enabled_path = nginx_style["available"] / f"{name}.conf"
        disabled_path = nginx_style["available"] / f"{name}.conf.disabled"

        if disabled_path.exists():
            return True, "Virtual host already disabled"

        if not enabled_path.exists():
            return False, f"Virtual host '{name}' not found"

        success, output = _run_command([
            "pkexec", "mv", str(enabled_path), str(disabled_path)
        ])

        if not success:
            return False, f"Failed to disable: {output}"

    # Reload nginx
    _run_command(["pkexec", "systemctl", "reload", "nginx"])
    return True, "Virtual host disabled"


def create_vhost(name: str, server_name: str, document_root: str) -> tuple[bool, str]:
    """Create a new virtual host."""
    nginx_style = _detect_nginx_style()
    uses_symlinks = nginx_style["uses_symlinks"]

    if uses_symlinks:
        config_path = nginx_style["available"] / name
    else:
        config_path = nginx_style["available"] / f"{name}.conf"

    if config_path.exists():
        return False, f"Virtual host '{name}' already exists"

    # Create document root if it doesn't exist
    doc_root_path = Path(document_root)
    if not doc_root_path.exists():
        success, output = _run_command(["pkexec", "mkdir", "-p", document_root])
        if not success:
            return False, f"Failed to create document root: {output}"

    # Detect PHP-FPM socket and generate config
    php_socket = _detect_php_fpm_socket()
    template = _get_vhost_template(php_socket)
    config_content = template.format(
        name=name,
        server_name=server_name,
        document_root=document_root
    )

    # Write config file (need to use tee with pkexec)
    success, output = _run_shell(
        f"echo '{config_content}' | pkexec tee {config_path} > /dev/null"
    )

    if not success:
        return False, f"Failed to create config: {output}"

    return True, f"Virtual host '{name}' created"


def delete_vhost(name: str) -> tuple[bool, str]:
    """Delete a virtual host."""
    nginx_style = _detect_nginx_style()
    uses_symlinks = nginx_style["uses_symlinks"]

    if uses_symlinks:
        config_path = nginx_style["available"] / name
        enabled_path = nginx_style["enabled"] / name
    else:
        # Check both enabled and disabled paths
        config_path = nginx_style["available"] / f"{name}.conf"
        if not config_path.exists():
            config_path = nginx_style["available"] / f"{name}.conf.disabled"
        enabled_path = None  # No separate enabled path in conf.d style

    if not config_path.exists():
        return False, f"Virtual host '{name}' not found"

    # Remove from sites-enabled first (Debian-style only)
    if enabled_path and enabled_path.exists():
        _run_command(["pkexec", "rm", str(enabled_path)])

    # Remove config file
    success, output = _run_command(["pkexec", "rm", str(config_path)])

    if not success:
        return False, f"Failed to delete: {output}"

    # Reload nginx
    _run_command(["pkexec", "systemctl", "reload", "nginx"])
    return True, "Virtual host deleted"


def add_hosts_entry(hostname: str, ip: str = "127.0.0.1") -> tuple[bool, str]:
    """Add entry to /etc/hosts."""
    # Check if entry already exists
    success, content = _run_shell(f"grep -q '{hostname}' /etc/hosts && echo exists")
    if "exists" in content:
        return True, "Hosts entry already exists"

    # Add entry
    entry = f"{ip}\t{hostname}"
    success, output = _run_shell(
        f"echo '{entry}' | pkexec tee -a /etc/hosts > /dev/null"
    )

    if not success:
        return False, f"Failed to add hosts entry: {output}"

    return True, "Hosts entry added"


def remove_hosts_entry(hostname: str) -> tuple[bool, str]:
    """Remove entry from /etc/hosts."""
    success, output = _run_shell(
        f"pkexec sed -i '/{hostname}/d' /etc/hosts"
    )

    if not success:
        return False, f"Failed to remove hosts entry: {output}"

    return True, "Hosts entry removed"


def test_nginx_config() -> tuple[bool, str]:
    """Test nginx configuration syntax."""
    success, output = _run_command(["nginx", "-t"])
    return success, output


def has_nginx_sites() -> bool:
    """Check if nginx sites directory exists."""
    nginx_style = _detect_nginx_style()
    return nginx_style["available"].exists()
