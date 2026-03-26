[//]: # (mcp-name: io.github.jonnyblankinship/hue-ble-mcp)

# hue-ble-mcp

An [MCP](https://modelcontextprotocol.io) server that lets Claude control **Philips Hue lights via Bluetooth LE** — no Hue Bridge or internet connection required.

Just ask Claude things like:
- *"Turn off the light"*
- *"Set the light to a warm reading mode"*
- *"Make it a deep blue"*
- *"Dim it to 20%"*

## Tools

| Tool | Description |
|---|---|
| `scan_hue_lights` | Discover nearby Hue BLE lights and get their addresses |
| `turn_on` | Turn a light on |
| `turn_off` | Turn a light off |
| `set_brightness` | Set brightness 1–100% |
| `set_color_temperature` | Set white color temperature (2000K warm → 6500K cool) |
| `set_color` | Set RGB color |
| `get_light_state` | Read current power, brightness, and color mode |
| `set_scene` | Apply a preset: `relax`, `energize`, `concentrate`, `reading`, `nightlight`, `bright` |

## Requirements

- macOS (uses CoreBluetooth via [bleak](https://github.com/hbldh/bleak))
- Python 3.10+
- A Philips Hue light with Bluetooth support (most lights made after 2019)
- Claude Desktop

## Installation

### Option 1: pip (recommended)

```bash
pip install hue-ble-mcp
```

Then add to your `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hue-ble": {
      "command": "hue-ble-mcp",
      "env": {
        "HUE_LIGHT_ADDRESS": ""
      }
    }
  }
}
```

### Option 2: Clone and run

```bash
git clone https://github.com/jonnyblankinship/hue-ble-mcp.git
cd hue-ble-mcp
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Then add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hue-ble": {
      "command": "/absolute/path/to/hue-ble-mcp/venv/bin/python",
      "args": ["/absolute/path/to/hue-ble-mcp/server.py"],
      "env": {
        "HUE_LIGHT_ADDRESS": ""
      }
    }
  }
}
```

## First-time setup

### 1. Pair your light

Hue BLE lights need to be in pairing mode the first time you connect. The easiest way is to **reset the light via the Hue app** (Settings → Light setup → select light → Delete), which puts it back into factory pairing mode.

> After the first successful connection, macOS remembers the bond and you won't need to do this again.

### 2. Find your light's address

Restart Claude Desktop, then ask:

> *"Scan for my Hue lights"*

Claude will return something like:

```json
[
  {
    "name": "Signe gradient floor",
    "address": "77577FFA-2F08-CAFD-5F3C-5C1824D8C362"
  }
]
```

> On macOS, addresses are UUIDs (not MAC addresses). This is normal — CoreBluetooth assigns its own identifiers.

### 3. Set the default address

Paste the address into `HUE_LIGHT_ADDRESS` in your config and restart Claude Desktop. From then on, you don't need to specify the address in every command.

```json
"env": {
  "HUE_LIGHT_ADDRESS": "77577FFA-2F08-CAFD-5F3C-5C1824D8C362"
}
```

## How it works

Philips Hue lights broadcast over Bluetooth LE using a proprietary but [well-documented](https://gist.github.com/shinyquagsire23/f7907fdf6b470200702e75a30135caf3) GATT profile. This server writes directly to those GATT characteristics using [bleak](https://github.com/hbldh/bleak), bypassing the need for a Hue Bridge or the Hue cloud entirely.

Key characteristics used:

| UUID | Function |
|---|---|
| `932c32bd-0002-...` | Power (on/off) |
| `932c32bd-0003-...` | Brightness |
| `932c32bd-0004-...` | Color temperature (mireds) |
| `932c32bd-0005-...` | XY color (CIE 1931) |

RGB colors are converted to CIE 1931 XY space using the wide RGB D65 gamut matrix before being sent to the light.

## Limitations

- **macOS only** — Linux should work too but is untested. Windows is not supported.
- **Bluetooth range** — must be within ~10m of the light.
- **One adapter per light** — the light bonds to the Bluetooth adapter used during first pairing. A different Mac won't be able to connect without re-pairing.
- **Multiple lights** — supported, just call each tool with the specific address. Set `HUE_LIGHT_ADDRESS` to your primary light for convenience.

## License

MIT
