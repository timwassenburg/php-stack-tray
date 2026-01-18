# PHP Stack Tray

A system tray application for PHP development on Linux. Manage nginx, PHP-FPM, MySQL/MariaDB, virtual hosts, and more from your system tray.

## Features

### Service Management
- Start, stop, restart services with visual status indicators
- Enable/disable autostart at boot
- View service logs via journalctl

### Virtual Hosts (Sites)
- Create, enable/disable, delete nginx virtual hosts
- Per-site PHP version selection
- Automatic /etc/hosts entry management
- Support for Debian-style (sites-available/sites-enabled) and conf.d style

### PHP Management
- Switch between multiple PHP versions
- Per-site PHP-FPM version selection
- Quick access to php.ini files
- Xdebug toggle with one click

### Logs & Diagnostics
- Unified logs viewer with dropdown selector
- Nginx access/error logs
- PHP error logs
- Service logs (journalctl)

### Config Files
- Quick access to nginx.conf, php.ini, my.cnf, etc.
- Organized by category (Nginx, PHP, MySQL, System)

## Supported Services

The app automatically detects and shows only the services installed on your system:

| Service | Description |
|---------|-------------|
| **Nginx** | High-performance HTTP server and reverse proxy |
| **Apache** | Apache HTTP Server (apache2 or httpd) |
| **PHP-FPM** | PHP FastCGI Process Manager |
| **MariaDB** | MariaDB database server |
| **MySQL** | MySQL database server |
| **PostgreSQL** | PostgreSQL database server |
| **Redis** | Redis in-memory data store |

*Note: MariaDB/MySQL and Apache/httpd are mutually exclusive - only one of each pair is shown.*

## Supported Distributions

- **Arch Linux** (and derivatives like Manjaro, EndeavourOS)
- **Debian/Ubuntu** (and derivatives like Linux Mint, Pop!_OS)
- **Fedora/RHEL** (and derivatives like CentOS, Rocky Linux, AlmaLinux)

## Requirements

- Python 3.10+
- PyQt6
- Linux with systemd
- polkit (for privilege escalation)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/php-stack-tray.git
cd php-stack-tray

# Install dependencies
pip install PyQt6

# Run
PYTHONPATH=src python -m php_stack_tray.main
```

## Polkit Configuration (Recommended)

To avoid entering your password repeatedly, install the polkit rules:

```bash
sudo cp data/50-php-stack-tray.rules /etc/polkit-1/rules.d/
```

This caches authentication for the session, so you only need to enter your password once.

## Usage

The application runs in your system tray. Right-click to access the menu:

1. **Services** - Each service shows status (green=running, gray=stopped, red=failed)
   - Click to expand submenu with Start/Stop/Restart options
   - Toggle autostart
   - View logs

2. **Sites** - Opens the Sites Manager dialog
   - View all virtual hosts with status and PHP version
   - Create new sites with PHP version selection
   - Enable/disable sites
   - Change PHP version per site

3. **PHP Version** - Switch global PHP version

4. **Xdebug** - Toggle Xdebug on/off (restarts PHP-FPM automatically)

5. **View Logs** - Unified log viewer for all services and web logs

6. **Config Files** - Quick access to configuration files

## Project Structure

```
src/php_stack_tray/
├── __init__.py          # Package info and version
├── main.py              # Entry point
├── tray.py              # System tray UI and dialogs
├── services.py          # Service definitions
├── systemd_client.py    # Systemd interaction via pkexec
├── xdebug.py            # Xdebug toggle functionality
├── php_versions.py      # PHP version detection and switching
├── php_logs.py          # PHP log file detection
├── web_logs.py          # Web server log viewing
├── vhosts.py            # Virtual hosts management
└── config_files.py      # Config file detection
```

## License

MIT License

## Author

Tim Wassenburg
