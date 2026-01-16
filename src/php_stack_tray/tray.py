"""System tray UI for service management."""

import subprocess
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QBrush
from PyQt6.QtWidgets import (
    QApplication, QMenu, QSystemTrayIcon, QMessageBox,
    QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout,
    QLabel, QLineEdit, QFormLayout, QCheckBox, QFileDialog, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)

from .services import ServiceDefinition, ServiceRegistry, DEFAULT_SERVICES
from .systemd_client import SystemdClient, ServiceState, is_flatpak
from . import xdebug
from . import php_versions
from . import web_logs
from . import vhosts
from . import config_files


class LogsDialog(QDialog):
    """Dialog to display service logs."""

    def __init__(self, title: str, logs: str, refresh_callback=None, source: str = None, parent=None):
        super().__init__(parent)
        self.refresh_callback = refresh_callback
        self.source = source
        self.setWindowTitle(title)
        self.setMinimumSize(700, 500)
        self._setup_ui(logs)

    def _setup_ui(self, logs: str) -> None:
        layout = QVBoxLayout(self)

        # Source label (if provided)
        if self.source:
            from PyQt6.QtWidgets import QLabel
            source_label = QLabel(self.source)
            source_label.setStyleSheet("color: gray; font-size: 11px;")
            layout.addWidget(source_label)

        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFontFamily("monospace")
        self.log_text.setPlainText(logs)
        # Scroll to bottom
        self.log_text.moveCursor(self.log_text.textCursor().MoveOperation.End)
        layout.addWidget(self.log_text)

        # Buttons
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._on_refresh)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _on_refresh(self) -> None:
        """Refresh the logs."""
        if self.refresh_callback:
            logs = self.refresh_callback()
            self.log_text.setPlainText(logs)
            self.log_text.moveCursor(self.log_text.textCursor().MoveOperation.End)


class UnifiedLogsDialog(QDialog):
    """Dialog to display logs with a dropdown selector."""

    def __init__(self, log_sources: dict, parent=None):
        """
        log_sources: dict of {display_name: (fetch_function, source_label)}
        """
        super().__init__(parent)
        self.log_sources = log_sources
        self.setWindowTitle("Logs Viewer")
        self.setMinimumSize(800, 600)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Top bar with dropdown
        top_layout = QHBoxLayout()

        top_layout.addWidget(QLabel("Log:"))

        self.log_selector = QComboBox()
        self.log_selector.addItems(self.log_sources.keys())
        self.log_selector.currentTextChanged.connect(self._on_log_changed)
        top_layout.addWidget(self.log_selector, 1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setIcon(QIcon.fromTheme("view-refresh"))
        refresh_btn.clicked.connect(self._on_refresh)
        top_layout.addWidget(refresh_btn)

        layout.addLayout(top_layout)

        # Source label
        self.source_label = QLabel()
        self.source_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.source_label)

        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFontFamily("monospace")
        layout.addWidget(self.log_text)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        # Load initial log
        self._load_current_log()

    def _on_log_changed(self, text: str) -> None:
        """Handle log selection change."""
        self._load_current_log()

    def _on_refresh(self) -> None:
        """Refresh current log."""
        self._load_current_log()

    def _load_current_log(self) -> None:
        """Load the currently selected log."""
        current = self.log_selector.currentText()
        if current in self.log_sources:
            fetch_func, source = self.log_sources[current]
            try:
                logs = fetch_func()
                self.log_text.setPlainText(logs)
                self.log_text.moveCursor(self.log_text.textCursor().MoveOperation.End)
                self.source_label.setText(source)
            except Exception as e:
                self.log_text.setPlainText(f"Error loading log: {e}")
                self.source_label.setText("")


class NewVhostDialog(QDialog):
    """Dialog for creating a new virtual host."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Site")
        self.setMinimumWidth(450)
        self._setup_ui()
        self.result_data = None

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Form
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("myproject")
        self.name_input.textChanged.connect(self._update_server_name)
        form.addRow("Config name:", self.name_input)

        self.server_name_input = QLineEdit()
        self.server_name_input.setPlaceholderText("myproject.local")
        form.addRow("Domain:", self.server_name_input)

        # Document root with browse button
        docroot_layout = QHBoxLayout()
        self.docroot_input = QLineEdit()
        self.docroot_input.setPlaceholderText("/home/user/projects/myproject/public")
        docroot_layout.addWidget(self.docroot_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_docroot)
        docroot_layout.addWidget(browse_btn)

        form.addRow("Document root:", docroot_layout)

        self.add_hosts_checkbox = QCheckBox("Add to /etc/hosts")
        self.add_hosts_checkbox.setChecked(True)
        form.addRow("", self.add_hosts_checkbox)

        self.enable_checkbox = QCheckBox("Enable immediately")
        self.enable_checkbox.setChecked(True)
        form.addRow("", self.enable_checkbox)

        layout.addLayout(form)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        create_btn = QPushButton("Create")
        create_btn.clicked.connect(self._on_create)
        create_btn.setDefault(True)
        button_layout.addWidget(create_btn)

        layout.addLayout(button_layout)

    def _update_server_name(self, text: str) -> None:
        """Auto-fill server name based on config name."""
        if text and not self.server_name_input.text():
            self.server_name_input.setText(f"{text}.local")

    def _browse_docroot(self) -> None:
        """Open file dialog to select document root."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Document Root",
            str(Path.home())
        )
        if directory:
            self.docroot_input.setText(directory)

    def _on_create(self) -> None:
        """Validate and accept the dialog."""
        name = self.name_input.text().strip()
        server_name = self.server_name_input.text().strip()
        docroot = self.docroot_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Error", "Config name is required")
            return
        if not server_name:
            QMessageBox.warning(self, "Error", "Domain is required")
            return
        if not docroot:
            QMessageBox.warning(self, "Error", "Document root is required")
            return

        self.result_data = {
            "name": name,
            "server_name": server_name,
            "docroot": docroot,
            "add_hosts": self.add_hosts_checkbox.isChecked(),
            "enable": self.enable_checkbox.isChecked()
        }
        self.accept()


class SitesDialog(QDialog):
    """Dialog for managing virtual hosts / sites."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sites Manager")
        self.setMinimumSize(700, 400)
        self._setup_ui()
        self._load_sites()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Domain", "Document Root", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(3, 80)

        layout.addWidget(self.table)

        # Action buttons
        action_layout = QHBoxLayout()

        self.toggle_btn = QPushButton("Enable")
        self.toggle_btn.setIcon(QIcon.fromTheme("media-playback-start"))
        self.toggle_btn.clicked.connect(self._toggle_site)
        self.toggle_btn.setEnabled(False)
        action_layout.addWidget(self.toggle_btn)

        self.browser_btn = QPushButton("Open in Browser")
        self.browser_btn.setIcon(QIcon.fromTheme("internet-web-browser"))
        self.browser_btn.clicked.connect(self._open_in_browser)
        self.browser_btn.setEnabled(False)
        action_layout.addWidget(self.browser_btn)

        self.edit_btn = QPushButton("Edit Config")
        self.edit_btn.setIcon(QIcon.fromTheme("document-edit"))
        self.edit_btn.clicked.connect(self._edit_config)
        self.edit_btn.setEnabled(False)
        action_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setIcon(QIcon.fromTheme("edit-delete"))
        self.delete_btn.clicked.connect(self._delete_site)
        self.delete_btn.setEnabled(False)
        action_layout.addWidget(self.delete_btn)

        layout.addLayout(action_layout)

        # Bottom buttons
        bottom_layout = QHBoxLayout()

        new_btn = QPushButton("New Site...")
        new_btn.setIcon(QIcon.fromTheme("list-add"))
        new_btn.clicked.connect(self._new_site)
        bottom_layout.addWidget(new_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setIcon(QIcon.fromTheme("view-refresh"))
        refresh_btn.clicked.connect(self._load_sites)
        bottom_layout.addWidget(refresh_btn)

        bottom_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(close_btn)

        layout.addLayout(bottom_layout)

    def _load_sites(self) -> None:
        """Load and display all virtual hosts."""
        self.table.setRowCount(0)
        self._sites = vhosts.get_virtual_hosts()

        for vh in self._sites:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(vh.name))
            self.table.setItem(row, 1, QTableWidgetItem(vh.server_name or "-"))
            self.table.setItem(row, 2, QTableWidgetItem(vh.document_root or "-"))

            status_item = QTableWidgetItem("Enabled" if vh.enabled else "Disabled")
            status_item.setForeground(QColor("#2ecc71" if vh.enabled else "#95a5a6"))
            self.table.setItem(row, 3, status_item)

        self._on_selection_changed()

    def _get_selected_site(self):
        """Get the currently selected site."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if row < len(self._sites):
            return self._sites[row]
        return None

    def _on_selection_changed(self) -> None:
        """Update button states based on selection."""
        site = self._get_selected_site()
        has_selection = site is not None

        self.toggle_btn.setEnabled(has_selection)
        self.browser_btn.setEnabled(has_selection and site.enabled if site else False)
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

        if site:
            if site.enabled:
                self.toggle_btn.setText("Disable")
                self.toggle_btn.setIcon(QIcon.fromTheme("media-playback-stop"))
            else:
                self.toggle_btn.setText("Enable")
                self.toggle_btn.setIcon(QIcon.fromTheme("media-playback-start"))

    def _toggle_site(self) -> None:
        """Enable or disable the selected site."""
        site = self._get_selected_site()
        if not site:
            return

        if site.enabled:
            success, message = vhosts.disable_vhost(site.name)
        else:
            success, message = vhosts.enable_vhost(site.name)

        if not success:
            QMessageBox.warning(self, "Error", message)
        self._load_sites()

    def _open_in_browser(self) -> None:
        """Open the selected site in browser."""
        site = self._get_selected_site()
        if site and site.server_name:
            url = f"http://{site.server_name}"
            subprocess.Popen(["xdg-open", url], start_new_session=True)

    def _edit_config(self) -> None:
        """Open the config file in default editor."""
        site = self._get_selected_site()
        if site:
            subprocess.Popen(["xdg-open", str(site.config_path)], start_new_session=True)

    def _delete_site(self) -> None:
        """Delete the selected site."""
        site = self._get_selected_site()
        if not site:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete '{site.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success, message = vhosts.delete_vhost(site.name)
            if not success:
                QMessageBox.warning(self, "Error", message)
            self._load_sites()

    def _new_site(self) -> None:
        """Create a new virtual host."""
        dialog = NewVhostDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.result_data
            success, message = vhosts.create_vhost(
                data["name"],
                data["server_name"],
                data["docroot"]
            )

            if success:
                if data["add_hosts"]:
                    vhosts.add_hosts_entry(data["server_name"])
                if data["enable"]:
                    vhosts.enable_vhost(data["name"])
                self._load_sites()
            else:
                QMessageBox.warning(self, "Error", message)


class PHPStackTray:
    """System tray application for PHP development."""

    REFRESH_INTERVAL_MS = 5000  # 5 seconds

    # Status indicator colors
    STATUS_COLORS = {
        ServiceState.ACTIVE: "#2ecc71",      # Green
        ServiceState.INACTIVE: "#95a5a6",    # Gray
        ServiceState.FAILED: "#e74c3c",      # Red
        ServiceState.ACTIVATING: "#f39c12",  # Orange
        ServiceState.DEACTIVATING: "#f39c12", # Orange
        ServiceState.UNKNOWN: "#95a5a6",     # Gray
    }

    def __init__(self, app: QApplication):
        self._app = app
        self._systemd = SystemdClient()
        self._registry = ServiceRegistry()
        self._tray: Optional[QSystemTrayIcon] = None
        self._menu: Optional[QMenu] = None
        self._service_menus: dict[str, QMenu] = {}
        self._status_actions: dict[str, QAction] = {}
        self._service_actions: dict[str, dict[str, QAction]] = {}  # service -> {start, stop, restart}
        self._refresh_timer: Optional[QTimer] = None
        self._xdebug_action: Optional[QAction] = None
        self._php_version_menu: Optional[QMenu] = None
        self._php_version_actions: dict[str, QAction] = {}

    def setup(self) -> bool:
        """Initialize the system tray icon and menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(
                None,
                "PHP Stack Tray",
                "System tray is not available on this system."
            )
            return False

        self._tray = QSystemTrayIcon()

        # Create a simple colored icon that always works
        from PyQt6.QtGui import QPixmap, QPainter, QColor
        from PyQt6.QtCore import Qt
        pixmap = QPixmap(22, 22)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#3498db"))  # Blue
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 18, 18)
        painter.end()

        self._tray.setIcon(QIcon(pixmap))
        self._tray.setToolTip("PHP Stack Tray")

        self._build_menu()
        self._tray.setContextMenu(self._menu)

        # Setup refresh timer
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(self.REFRESH_INTERVAL_MS)

        self._tray.setVisible(True)
        self._tray.show()
        return True

    def _build_menu(self) -> None:
        """Build the context menu with all services."""
        self._menu = QMenu()

        # === HEADER ===
        header = QAction("PHP Stack Tray", self._menu)
        header.setEnabled(False)
        font = header.font()
        font.setBold(True)
        header.setFont(font)
        self._menu.addAction(header)
        self._menu.addSeparator()

        # === SERVICES ===
        installed_count = 0
        shown_services: set[str] = set()

        for service in self._registry.get_all_services():
            if service.conflicts:
                if any(c in shown_services for c in service.conflicts):
                    continue

            if self._systemd.is_service_installed(service.name):
                self._add_service_menu(service)
                shown_services.add(service.name)
                installed_count += 1

        if installed_count == 0:
            no_services = QAction("No services found", self._menu)
            no_services.setEnabled(False)
            self._menu.addAction(no_services)

        # === SITES (right after services) ===
        if vhosts.has_nginx_sites():
            self._menu.addSeparator()
            sites_action = QAction(QIcon.fromTheme("network-server"), "Sites...", self._menu)
            sites_action.triggered.connect(self._show_sites_dialog)
            self._menu.addAction(sites_action)

        # === PHP (version + xdebug together) ===
        versions = php_versions.get_installed_php_versions()
        has_php = versions or xdebug.is_xdebug_installed()

        if has_php:
            self._menu.addSeparator()

        if versions:
            self._php_version_menu = QMenu("PHP Version", self._menu)
            self._php_version_menu.setIcon(QIcon.fromTheme("applications-development"))
            self._build_php_version_menu(versions)
            self._menu.addMenu(self._php_version_menu)

        if xdebug.is_xdebug_installed():
            self._xdebug_action = QAction(QIcon.fromTheme("debug-run"), "Xdebug: ...", self._menu)
            self._xdebug_action.triggered.connect(self._toggle_xdebug)
            self._menu.addAction(self._xdebug_action)
            self._update_xdebug_status()

        # === DIAGNOSTICS (logs + config together) ===
        self._menu.addSeparator()

        view_logs_action = QAction(QIcon.fromTheme("text-x-log"), "View Logs", self._menu)
        view_logs_action.triggered.connect(self._view_all_logs)
        self._menu.addAction(view_logs_action)

        all_configs = config_files.get_all_configs()
        if all_configs:
            config_menu = QMenu("Config Files", self._menu)
            config_menu.setIcon(QIcon.fromTheme("preferences-system"))
            self._build_config_menu(config_menu, all_configs)
            self._menu.addMenu(config_menu)

        # === SYSTEM ===
        self._menu.addSeparator()

        refresh_action = QAction(QIcon.fromTheme("view-refresh"), "Refresh Status", self._menu)
        refresh_action.triggered.connect(self._refresh_status)
        self._menu.addAction(refresh_action)

        self._menu.addSeparator()

        about_action = QAction(QIcon.fromTheme("help-about"), "About", self._menu)
        about_action.triggered.connect(self._show_about)
        self._menu.addAction(about_action)

        quit_action = QAction(QIcon.fromTheme("application-exit"), "Quit", self._menu)
        quit_action.triggered.connect(self._quit)
        self._menu.addAction(quit_action)

    def _get_service_version(self, service: ServiceDefinition) -> Optional[str]:
        """Get version string for a service."""
        if not service.version_cmd:
            return None
        try:
            cmd = service.version_cmd
            if is_flatpak():
                cmd = f"flatpak-spawn --host bash -c '{cmd}'"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            version = result.stdout.strip()
            return version if version else None
        except Exception:
            return None

    def _add_service_menu(self, service: ServiceDefinition) -> None:
        """Add a submenu for a specific service."""
        # Build display name with version
        display_name = service.display_name
        version = self._get_service_version(service)
        if version:
            display_name = f"{service.display_name} {version}"

        service_menu = QMenu(display_name, self._menu)
        self._service_menus[service.name] = service_menu

        # Status indicator (not clickable)
        status_action = QAction("Status: ...", service_menu)
        status_action.setEnabled(False)
        service_menu.addAction(status_action)
        self._status_actions[service.name] = status_action

        service_menu.addSeparator()

        # Start action
        start_action = QAction(QIcon.fromTheme("media-playback-start"), "Start", service_menu)
        start_action.triggered.connect(lambda: self._start_service(service.name))
        service_menu.addAction(start_action)

        # Stop action
        stop_action = QAction(QIcon.fromTheme("media-playback-stop"), "Stop", service_menu)
        stop_action.triggered.connect(lambda: self._stop_service(service.name))
        service_menu.addAction(stop_action)

        # Restart action
        restart_action = QAction(QIcon.fromTheme("view-refresh"), "Restart", service_menu)
        restart_action.triggered.connect(lambda: self._restart_service(service.name))
        service_menu.addAction(restart_action)

        service_menu.addSeparator()

        # View Logs action
        logs_action = QAction(QIcon.fromTheme("text-x-log"), "View Logs", service_menu)
        logs_action.triggered.connect(lambda: self._view_logs(service.name))
        service_menu.addAction(logs_action)

        # Autostart toggle action
        autostart_action = QAction(QIcon.fromTheme("system-run"), "Autostart: ...", service_menu)
        autostart_action.triggered.connect(lambda: self._toggle_autostart(service.name))
        service_menu.addAction(autostart_action)

        # Store action references for visibility updates
        self._service_actions[service.name] = {
            "start": start_action,
            "stop": stop_action,
            "restart": restart_action,
            "autostart": autostart_action,
        }

        self._menu.addMenu(service_menu)

        # Update initial status
        self._update_service_status(service.name)

    def _create_status_icon(self, state: ServiceState) -> QIcon:
        """Create a colored circle icon for service status."""
        size = 16
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(self.STATUS_COLORS.get(state, "#95a5a6"))
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, size - 4, size - 4)

        painter.end()
        return QIcon(pixmap)

    def _get_status_text(self, state: ServiceState) -> str:
        """Get human-readable status text."""
        status_map = {
            ServiceState.ACTIVE: "Running",
            ServiceState.INACTIVE: "Stopped",
            ServiceState.FAILED: "Failed",
            ServiceState.ACTIVATING: "Starting...",
            ServiceState.DEACTIVATING: "Stopping...",
            ServiceState.UNKNOWN: "Unknown",
        }
        return status_map.get(state, "Unknown")

    def _update_service_status(self, service_name: str) -> None:
        """Update the status display and action visibility for a service."""
        if service_name not in self._status_actions:
            return

        state = self._systemd.get_service_state(service_name)
        status_text = self._get_status_text(state)
        self._status_actions[service_name].setText(f"Status: {status_text}")

        # Update service menu icon with status indicator
        if service_name in self._service_menus:
            status_icon = self._create_status_icon(state)
            self._service_menus[service_name].setIcon(status_icon)

        # Update action visibility based on state
        if service_name in self._service_actions:
            actions = self._service_actions[service_name]
            is_running = state == ServiceState.ACTIVE
            actions["start"].setVisible(not is_running)
            actions["stop"].setVisible(is_running)
            actions["restart"].setVisible(is_running)

            # Update autostart status
            if "autostart" in actions:
                is_enabled = self._systemd.is_service_enabled(service_name)
                autostart_text = "Enabled" if is_enabled else "Disabled"
                actions["autostart"].setText(f"Autostart: {autostart_text}")

    def _refresh_status(self) -> None:
        """Refresh status of all services."""
        for service_name in self._status_actions:
            self._update_service_status(service_name)
        self._update_xdebug_status()

    def _start_service(self, service_name: str) -> None:
        """Start a service."""
        if self._systemd.start_service(service_name):
            self._show_notification(f"Starting {service_name}...")
        else:
            self._show_notification(f"Failed to start {service_name}", error=True)
        # Refresh after a short delay to show new status
        QTimer.singleShot(1000, lambda: self._update_service_status(service_name))

    def _stop_service(self, service_name: str) -> None:
        """Stop a service."""
        if self._systemd.stop_service(service_name):
            self._show_notification(f"Stopping {service_name}...")
        else:
            self._show_notification(f"Failed to stop {service_name}", error=True)
        QTimer.singleShot(1000, lambda: self._update_service_status(service_name))

    def _restart_service(self, service_name: str) -> None:
        """Restart a service."""
        if self._systemd.restart_service(service_name):
            self._show_notification(f"Restarting {service_name}...")
        else:
            self._show_notification(f"Failed to restart {service_name}", error=True)
        QTimer.singleShot(1000, lambda: self._update_service_status(service_name))

    def _toggle_autostart(self, service_name: str) -> None:
        """Toggle autostart for a service."""
        is_enabled = self._systemd.is_service_enabled(service_name)

        if is_enabled:
            if self._systemd.disable_service(service_name):
                self._show_notification(f"{service_name} autostart disabled")
            else:
                self._show_notification(f"Failed to disable {service_name} autostart", error=True)
        else:
            if self._systemd.enable_service(service_name):
                self._show_notification(f"{service_name} autostart enabled")
            else:
                self._show_notification(f"Failed to enable {service_name} autostart", error=True)

        self._update_service_status(service_name)

    def _view_logs(self, service_name: str) -> None:
        """Show logs dialog for a service."""
        logs = self._systemd.get_logs(service_name)
        dialog = LogsDialog(
            f"Logs - {service_name}",
            logs,
            refresh_callback=lambda: self._systemd.get_logs(service_name),
            source=f"journalctl -u {service_name}.service"
        )
        dialog.exec()

    def _view_nginx_access_log(self) -> None:
        """Show nginx access log dialog."""
        logs, source = web_logs.get_nginx_access_log(lines=100)
        dialog = LogsDialog(
            "Nginx Access Log",
            logs,
            refresh_callback=lambda: web_logs.get_nginx_access_log(lines=100)[0],
            source=source
        )
        dialog.exec()

    def _view_nginx_error_log(self) -> None:
        """Show nginx error log dialog."""
        logs, source = web_logs.get_nginx_error_log(lines=100)
        dialog = LogsDialog(
            "Nginx Error Log",
            logs,
            refresh_callback=lambda: web_logs.get_nginx_error_log(lines=100)[0],
            source=source
        )
        dialog.exec()

    def _view_php_error_log(self) -> None:
        """Show PHP error log dialog."""
        logs, source = web_logs.get_php_error_log(lines=100)
        dialog = LogsDialog(
            "PHP Error Log",
            logs,
            refresh_callback=lambda: web_logs.get_php_error_log(lines=100)[0],
            source=source
        )
        dialog.exec()

    def _view_all_logs(self) -> None:
        """Show unified logs viewer dialog."""
        log_sources = {}

        # Add service logs
        for service_name in self._status_actions.keys():
            display_name = f"{service_name} (service)"
            log_sources[display_name] = (
                lambda sn=service_name: self._systemd.get_logs(sn),
                f"journalctl -u {service_name}.service"
            )

        # Add web logs
        if web_logs.has_nginx_logs():
            log_sources["Nginx Access Log"] = (
                lambda: web_logs.get_nginx_access_log(lines=200)[0],
                web_logs.get_nginx_access_log(lines=1)[1]
            )
            log_sources["Nginx Error Log"] = (
                lambda: web_logs.get_nginx_error_log(lines=200)[0],
                web_logs.get_nginx_error_log(lines=1)[1]
            )

        # Add PHP error log
        if self._systemd.is_service_installed("php-fpm"):
            log_sources["PHP Error Log"] = (
                lambda: web_logs.get_php_error_log(lines=200)[0],
                web_logs.get_php_error_log(lines=1)[1]
            )

        dialog = UnifiedLogsDialog(log_sources)
        dialog.exec()

    def _build_config_menu(self, menu: QMenu, configs: dict) -> None:
        """Build the config files submenu."""
        for category, files in configs.items():
            if len(configs) > 1:
                # Add category as submenu if multiple categories
                cat_menu = QMenu(category, menu)
                for cf in files:
                    action = QAction(cf.name, cat_menu)
                    action.triggered.connect(lambda checked, path=cf.path: self._open_config_file(path))
                    cat_menu.addAction(action)
                menu.addMenu(cat_menu)
            else:
                # Single category, add directly
                for cf in files:
                    action = QAction(f"{cf.name}", menu)
                    action.triggered.connect(lambda checked, path=cf.path: self._open_config_file(path))
                    menu.addAction(action)

    def _open_config_file(self, path: str) -> None:
        """Open a config file in the default editor."""
        import subprocess
        try:
            subprocess.Popen(["xdg-open", path], start_new_session=True)
        except Exception:
            self._show_notification(f"Could not open {path}", error=True)

    def _open_in_browser(self, domain: str) -> None:
        """Open a domain in the default browser."""
        import subprocess
        url = f"http://{domain}"
        try:
            subprocess.Popen(["xdg-open", url], start_new_session=True)
        except Exception:
            self._show_notification(f"Could not open {url}", error=True)

    def _show_sites_dialog(self) -> None:
        """Show the sites management dialog."""
        dialog = SitesDialog()
        dialog.exec()

    def _update_xdebug_status(self) -> None:
        """Update the Xdebug menu item text."""
        if self._xdebug_action:
            enabled = xdebug.is_xdebug_enabled()
            status = "Enabled" if enabled else "Disabled"
            self._xdebug_action.setText(f"Xdebug: {status}")

    def _build_php_version_menu(self, versions: list) -> None:
        """Build the PHP version submenu."""
        active_version = php_versions.get_active_php_version()

        for v in versions:
            # Create submenu for each PHP version
            label = f"PHP {v.version}"
            if v.version == active_version:
                label += " (active)"

            version_menu = QMenu(label, self._php_version_menu)

            # Switch action
            switch_action = QAction("Switch to this version", version_menu)
            switch_action.setCheckable(True)
            switch_action.setChecked(v.version == active_version)
            switch_action.triggered.connect(lambda checked, ver=v: self._switch_php_version(ver))
            version_menu.addAction(switch_action)
            self._php_version_actions[v.version] = switch_action

            # php.ini action
            ini_path = php_versions.get_php_ini_path(v)
            if ini_path:
                ini_action = QAction(f"Edit php.ini", version_menu)
                ini_action.triggered.connect(lambda checked, path=ini_path: self._open_php_ini(path))
                version_menu.addAction(ini_action)

            # Set icon based on active status
            if v.version == active_version:
                version_menu.setIcon(self._create_status_icon(ServiceState.ACTIVE))
            else:
                version_menu.setIcon(self._create_status_icon(ServiceState.INACTIVE))

            self._php_version_menu.addMenu(version_menu)

    def _switch_php_version(self, version) -> None:
        """Switch to a different PHP version."""
        success, message = php_versions.switch_php_version(version)

        if success:
            self._show_notification(f"Switched to PHP {version.version}")
            # Update menu checkmarks
            for v, action in self._php_version_actions.items():
                action.setChecked(v == version.version)
                text = f"PHP {v}"
                if v == version.version:
                    text += " (active)"
                action.setText(text)
            # Refresh service status
            QTimer.singleShot(1000, self._refresh_status)
        else:
            self._show_notification(message, error=True)

    def _open_php_ini(self, path: str) -> None:
        """Open php.ini in the default editor."""
        import subprocess
        try:
            # Try xdg-open first, then common editors
            subprocess.Popen(["xdg-open", path], start_new_session=True)
        except Exception:
            try:
                subprocess.Popen(["kate", path], start_new_session=True)
            except Exception:
                try:
                    subprocess.Popen(["gedit", path], start_new_session=True)
                except Exception:
                    self._show_notification(f"Could not open {path}", error=True)

    def _toggle_xdebug(self) -> None:
        """Toggle Xdebug on/off and restart PHP-FPM."""
        success, message, new_state = xdebug.toggle_xdebug()

        if success:
            # Restart PHP-FPM to apply changes
            self._systemd.restart_service("php-fpm")
            state_str = "enabled" if new_state else "disabled"
            self._show_notification(f"Xdebug {state_str}. PHP-FPM restarting...")
            self._update_xdebug_status()
            # Update PHP-FPM status after restart
            QTimer.singleShot(1500, lambda: self._update_service_status("php-fpm"))
        else:
            self._show_notification(message, error=True)

    def _show_notification(self, message: str, error: bool = False) -> None:
        """Show a system notification."""
        if self._tray:
            icon = (QSystemTrayIcon.MessageIcon.Critical if error
                    else QSystemTrayIcon.MessageIcon.Information)
            self._tray.showMessage("PHP Stack Tray", message, icon, 3000)

    def _show_about(self) -> None:
        """Show the About dialog."""
        from . import __version__
        QMessageBox.about(
            None,
            "About PHP Stack Tray",
            f"""<h2>PHP Stack Tray</h2>
            <p>Version {__version__}</p>
            <p>A system tray application for PHP development on Linux.</p>
            <p>Manage nginx, PHP-FPM, MySQL/MariaDB, virtual hosts, and more.</p>
            <hr>
            <p><small>Author: Tim Wassenburg</small></p>"""
        )

    def _quit(self) -> None:
        """Quit the application."""
        if self._refresh_timer:
            self._refresh_timer.stop()
        self._app.quit()
