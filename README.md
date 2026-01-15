# PHP Stack Tray

A system tray application for PHP development on Linux. Manage nginx, PHP-FPM, MySQL/MariaDB, virtual hosts, and more from your system tray.

## Features

- **Service Management** - Start, stop, restart nginx, PHP-FPM, MySQL/MariaDB
- **Status Indicators** - Visual status (green=running, gray=stopped, red=failed)
- **Autostart Toggle** - Enable/disable services at boot
- **Xdebug Toggle** - Enable/disable Xdebug with one click
- **PHP Version Switcher** - Switch between multiple PHP versions
- **PHP Info** - View `php -i` output in a dialog
- **Web Logs** - View nginx access/error logs and PHP error logs
- **Virtual Hosts** - Create, enable/disable, delete nginx vhosts
- **Open in Browser** - Quick access to open vhosts in browser
- **Config Files** - Quick access to nginx.conf, php.ini, my.cnf, etc.

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

## Polkit Configuration (Optional)

To avoid entering your password repeatedly, install the polkit rules:

```bash
sudo cp data/50-php-stack-tray.rules /etc/polkit-1/rules.d/
```

## Screenshots

The application runs in your system tray. Right-click to access the menu:

- Services (nginx, PHP-FPM, MySQL) with status indicators
- Xdebug toggle
- PHP Version submenu with php.ini access
- PHP Info
- Web Logs submenu
- Virtual Hosts management
- Config Files quick access
- About dialog

## Project Structure

```
src/php_stack_tray/
├── __init__.py          # Package info and version
├── main.py              # Entry point
├── tray.py              # System tray UI
├── services.py          # Service definitions
├── systemd_client.py    # Systemd interaction via pkexec
├── xdebug.py            # Xdebug toggle functionality
├── php_versions.py      # PHP version detection and switching
├── web_logs.py          # Web server log viewing
├── vhosts.py            # Virtual hosts management
└── config_files.py      # Config file detection
```

## License

MIT License

## Author

Tim Wassenburg
