#!/bin/bash
# Install Polkit rules for PHP Stack Tray
# This allows managing services with a single authentication per session

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RULES_FILE="$PROJECT_DIR/data/50-php-stack-tray.rules"
TARGET_DIR="/etc/polkit-1/rules.d"

if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

if [ ! -f "$RULES_FILE" ]; then
    echo "Error: Rules file not found at $RULES_FILE"
    exit 1
fi

# Create target directory if it doesn't exist
mkdir -p "$TARGET_DIR"

# Install the rules file
cp "$RULES_FILE" "$TARGET_DIR/"
chmod 644 "$TARGET_DIR/50-php-stack-tray.rules"

echo "Polkit rules installed successfully!"
echo "You may need to restart your session for changes to take effect."
