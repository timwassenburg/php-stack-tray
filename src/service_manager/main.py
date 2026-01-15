#!/usr/bin/env python3
"""Main entry point for PHP Stack Tray."""

import sys

from PyQt6.QtWidgets import QApplication

from .tray import ServiceManagerTray


def main() -> int:
    """Run the PHP Stack Tray application."""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("PHP Stack Tray")
    app.setDesktopFileName("org.example.PHPStackTray")

    tray = ServiceManagerTray(app)
    if not tray.setup():
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
