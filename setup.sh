#!/bin/bash
# Sets up the Philips Hue BLE MCP server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Setting up Philips Hue BLE MCP server..."

# Create virtual environment
python3 -m venv venv
echo "Created virtual environment"

# Install dependencies
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt
echo "Installed dependencies"

PYTHON_PATH="$SCRIPT_DIR/venv/bin/python"
SERVER_PATH="$SCRIPT_DIR/server.py"

echo ""
echo "Setup complete!"
echo ""
echo "Add this to your ~/Library/Application\ Support/Claude/claude_desktop_config.json:"
echo ""
echo '{'
echo '  "mcpServers": {'
echo '    "hue-ble": {'
echo "      \"command\": \"$PYTHON_PATH\","
echo "      \"args\": [\"$SERVER_PATH\"],"
echo '      "env": {'
echo '        "HUE_LIGHT_ADDRESS": ""'
echo '      }'
echo '    }'
echo '  }'
echo '}'
echo ""
echo "First run: leave HUE_LIGHT_ADDRESS blank, then ask Claude to run scan_hue_lights()"
echo "to find your light's address. Paste that into the config and restart Claude."
