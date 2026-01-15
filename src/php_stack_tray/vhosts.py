"""Virtual hosts management for Nginx."""

import subprocess
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .systemd_client import is_flatpak


# Nginx paths
NGINX_SITES_AVAILABLE = Path("/etc/nginx/sites-available")
NGINX_SITES_ENABLED = Path("/etc/nginx/sites-enabled")
HOSTS_FILE = Path("/etc/hosts")


@dataclass
class VirtualHost:
    """Represents a virtual host configuration."""
    name: str
    config_path: Path
    enabled: bool
    server_name: Optional[str] = None
    document_root: Optional[str] = None


# Nginx vhost template
NGINX_VHOST_TEMPLATE = """server {{
    listen 80;
    server_name {server_name};
    root {document_root};
    index index.php index.html;

    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}

    location ~ \\.php$ {{
        fastcgi_pass unix:/run/php-fpm/php-fpm.sock;
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
    }}

    location ~ /\\.ht {{
        deny all;
    }}

    error_log /var/log/nginx/{name}_error.log;
    access_log /var/log/nginx/{name}_access.log;
}}
"""


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


def get_virtual_hosts() -> list[VirtualHost]:
    """Get list of all virtual hosts."""
    vhosts = []

    if not NGINX_SITES_AVAILABLE.exists():
        return vhosts

    # Get enabled sites
    enabled_sites = set()
    if NGINX_SITES_ENABLED.exists():
        for link in NGINX_SITES_ENABLED.iterdir():
            if link.is_symlink():
                target = link.resolve()
                enabled_sites.add(target.name)

    # List all available sites
    for config_file in NGINX_SITES_AVAILABLE.iterdir():
        if config_file.is_file():
            server_name, document_root = _parse_vhost_config(config_file)
            vhosts.append(VirtualHost(
                name=config_file.name,
                config_path=config_file,
                enabled=config_file.name in enabled_sites,
                server_name=server_name,
                document_root=document_root
            ))

    return sorted(vhosts, key=lambda v: v.name)


def enable_vhost(name: str) -> tuple[bool, str]:
    """Enable a virtual host by creating symlink."""
    source = NGINX_SITES_AVAILABLE / name
    target = NGINX_SITES_ENABLED / name

    if not source.exists():
        return False, f"Virtual host '{name}' not found"

    if target.exists():
        return True, "Virtual host already enabled"

    success, output = _run_command([
        "pkexec", "ln", "-s", str(source), str(target)
    ])

    if not success:
        return False, f"Failed to enable: {output}"

    # Reload nginx
    _run_command(["pkexec", "systemctl", "reload", "nginx"])
    return True, "Virtual host enabled"


def disable_vhost(name: str) -> tuple[bool, str]:
    """Disable a virtual host by removing symlink."""
    target = NGINX_SITES_ENABLED / name

    if not target.exists():
        return True, "Virtual host already disabled"

    success, output = _run_command(["pkexec", "rm", str(target)])

    if not success:
        return False, f"Failed to disable: {output}"

    # Reload nginx
    _run_command(["pkexec", "systemctl", "reload", "nginx"])
    return True, "Virtual host disabled"


def create_vhost(name: str, server_name: str, document_root: str) -> tuple[bool, str]:
    """Create a new virtual host."""
    config_path = NGINX_SITES_AVAILABLE / name

    if config_path.exists():
        return False, f"Virtual host '{name}' already exists"

    # Create document root if it doesn't exist
    doc_root_path = Path(document_root)
    if not doc_root_path.exists():
        success, output = _run_command(["pkexec", "mkdir", "-p", document_root])
        if not success:
            return False, f"Failed to create document root: {output}"

    # Generate config
    config_content = NGINX_VHOST_TEMPLATE.format(
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
    config_path = NGINX_SITES_AVAILABLE / name
    enabled_path = NGINX_SITES_ENABLED / name

    if not config_path.exists():
        return False, f"Virtual host '{name}' not found"

    # Remove from sites-enabled first
    if enabled_path.exists():
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
    """Check if nginx sites-available directory exists."""
    return NGINX_SITES_AVAILABLE.exists()
