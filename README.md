# PHP Stack Tray

A system tray application for PHP development on Linux. Manage nginx, PHP-FPM, MySQL/MariaDB, virtual hosts, and more from your system tray.

## Features

- **Service Management** - Start, stop, restart services with visual status indicators
- **Autostart Toggle** - Enable/disable services at boot
- **Xdebug Toggle** - Enable/disable Xdebug with one click
- **PHP Version Switcher** - Switch between multiple PHP versions
- **Web Logs** - View nginx access/error logs and PHP error logs
- **Sites** - Create, enable/disable, delete nginx virtual hosts
- **Config Files** - Quick access to nginx.conf, php.ini, my.cnf, etc.

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
- Web Logs submenu
- Sites management
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
