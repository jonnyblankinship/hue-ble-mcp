#!/usr/bin/env python3
"""
Philips Hue BLE MCP Server
Controls Philips Hue lights directly via Bluetooth LE — no bridge required.
"""

import json
import os
from struct import pack, unpack

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# GATT Characteristic UUIDs (reverse engineered from Hue BLE protocol)
# ---------------------------------------------------------------------------
UUID_HUE_IDENTIFIER = "0000fe0f-0000-1000-8000-00805f9b34fb"  # advertised by all Hue BLE lights
UUID_POWER          = "932c32bd-0002-47a2-835a-a8d455b859dd"  # 1 byte: 0x01=on, 0x00=off
UUID_BRIGHTNESS     = "932c32bd-0003-47a2-835a-a8d455b859dd"  # 1 byte: 1–254
UUID_TEMPERATURE    = "932c32bd-0004-47a2-835a-a8d455b859dd"  # 2 bytes LE: 153–500 mireds
UUID_XY_COLOR       = "932c32bd-0005-47a2-835a-a8d455b859dd"  # 4 bytes LE: X uint16, Y uint16

mcp = FastMCP("Philips Hue BLE")

DEFAULT_ADDRESS = os.environ.get("HUE_LIGHT_ADDRESS", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scale_brightness(percent: int) -> int:
    return max(1, min(254, int(percent * 254 / 100)))


def _kelvin_to_mireds(kelvin: int) -> int:
    return max(153, min(500, int(1_000_000 / max(1, kelvin))))


def _rgb_to_xy(r: float, g: float, b: float) -> tuple[float, float]:
    """Convert sRGB (0.0–1.0) to CIE 1931 XY using the wide RGB D65 gamut."""
    r = ((r + 0.055) / 1.055) ** 2.4 if r > 0.04045 else r / 12.92
    g = ((g + 0.055) / 1.055) ** 2.4 if g > 0.04045 else g / 12.92
    b = ((b + 0.055) / 1.055) ** 2.4 if b > 0.04045 else b / 12.92
    X = r * 0.664511 + g * 0.154324 + b * 0.162028
    Y = r * 0.283881 + g * 0.668433 + b * 0.047685
    Z = r * 0.000088 + g * 0.072310 + b * 0.986039
    total = X + Y + Z
    if total == 0:
        return 0.0, 0.0
    return X / total, Y / total


def _resolve_address(address: str) -> str:
    addr = address.strip() if address else ""
    if not addr:
        if DEFAULT_ADDRESS:
            return DEFAULT_ADDRESS
        raise ValueError(
            "No light address provided. Run scan_hue_lights() first to find your light's address, "
            "then pass it here or set the HUE_LIGHT_ADDRESS env var as a default."
        )
    return addr


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def scan_hue_lights(timeout: float = 10.0) -> str:
    """
    Scan for Philips Hue BLE lights nearby and return their names and addresses.
    Run this first to find your light's Bluetooth address — you'll need it for all other tools.

    On macOS, addresses look like UUIDs (e.g. 'BEF1AF5D-9A4D-4C2B-8870-1AB7CC5CE8DD').
    This is normal — macOS CoreBluetooth uses its own identifiers instead of MAC addresses.

    Args:
        timeout: How many seconds to scan (default 10). Increase if your light isn't found.
    """
    try:
        devices = await BleakScanner.discover(
            timeout=timeout,
            service_uuids=[UUID_HUE_IDENTIFIER],
        )
    except Exception as e:
        return (
            f"Scan failed: {e}\n"
            "Make sure Bluetooth is enabled and the app has Bluetooth permission "
            "(System Settings → Privacy & Security → Bluetooth)."
        )

    if not devices:
        return (
            "No Philips Hue BLE lights found nearby.\n\n"
            "Troubleshooting:\n"
            "  1. Make sure the light is powered on\n"
            "  2. Check that Bluetooth is enabled on your Mac\n"
            "  3. If connecting for the first time, reset the light via the Hue app\n"
            "     so it re-enters pairing/connectable mode\n"
            f"  4. Try increasing timeout (current: {timeout}s)"
        )

    results = [{"name": d.name or "Philips Hue Light", "address": str(d.address)} for d in devices]
    tip = "\nTip: Set HUE_LIGHT_ADDRESS in your claude_desktop_config.json env to use it as the default."
    return json.dumps(results, indent=2) + tip


@mcp.tool()
async def turn_on(address: str = "") -> str:
    """
    Turn on a Philips Hue light.

    Args:
        address: Bluetooth address from scan_hue_lights. Leave blank to use HUE_LIGHT_ADDRESS env var.
    """
    try:
        addr = _resolve_address(address)
        async with BleakClient(addr, timeout=15.0) as client:
            await client.write_gatt_char(UUID_POWER, bytes([0x01]), response=True)
        return "Light turned ON"
    except ValueError as e:
        return f"Error: {e}"
    except BleakError as e:
        return f"Bluetooth error: {e}"


@mcp.tool()
async def turn_off(address: str = "") -> str:
    """
    Turn off a Philips Hue light.

    Args:
        address: Bluetooth address from scan_hue_lights. Leave blank to use HUE_LIGHT_ADDRESS env var.
    """
    try:
        addr = _resolve_address(address)
        async with BleakClient(addr, timeout=15.0) as client:
            await client.write_gatt_char(UUID_POWER, bytes([0x00]), response=True)
        return "Light turned OFF"
    except ValueError as e:
        return f"Error: {e}"
    except BleakError as e:
        return f"Bluetooth error: {e}"


@mcp.tool()
async def set_brightness(brightness: int, address: str = "") -> str:
    """
    Set the brightness of a Philips Hue light (turns it on if off).

    Args:
        brightness: Brightness as a percentage, 1–100.
        address: Bluetooth address from scan_hue_lights. Leave blank to use HUE_LIGHT_ADDRESS env var.
    """
    brightness = max(1, min(100, brightness))
    raw = _scale_brightness(brightness)
    try:
        addr = _resolve_address(address)
        async with BleakClient(addr, timeout=15.0) as client:
            await client.write_gatt_char(UUID_POWER, bytes([0x01]), response=True)
            await client.write_gatt_char(UUID_BRIGHTNESS, bytes([raw]), response=True)
        return f"Brightness set to {brightness}%"
    except ValueError as e:
        return f"Error: {e}"
    except BleakError as e:
        return f"Bluetooth error: {e}"


@mcp.tool()
async def set_color_temperature(kelvin: int, address: str = "") -> str:
    """
    Set the color temperature of a Philips Hue light.
    Switches the light to white/CT mode (disables any color).

    Args:
        kelvin: Color temperature in Kelvin.
                2000K = very warm candlelight
                2700K = warm white (typical bulb)
                4000K = neutral / office white
                6500K = cool daylight
        address: Bluetooth address from scan_hue_lights. Leave blank to use HUE_LIGHT_ADDRESS env var.
    """
    kelvin = max(2000, min(6500, kelvin))
    mireds = _kelvin_to_mireds(kelvin)
    try:
        addr = _resolve_address(address)
        async with BleakClient(addr, timeout=15.0) as client:
            await client.write_gatt_char(UUID_POWER, bytes([0x01]), response=True)
            await client.write_gatt_char(UUID_TEMPERATURE, pack("<H", mireds), response=True)
        return f"Color temperature set to {kelvin}K ({mireds} mireds)"
    except ValueError as e:
        return f"Error: {e}"
    except BleakError as e:
        return f"Bluetooth error: {e}"


@mcp.tool()
async def set_color(red: int, green: int, blue: int, address: str = "") -> str:
    """
    Set the color of a Philips Hue light using RGB values.
    Switches the light to color mode. Use set_color_temperature to go back to white mode.

    Args:
        red:   Red channel, 0–255
        green: Green channel, 0–255
        blue:  Blue channel, 0–255
        address: Bluetooth address from scan_hue_lights. Leave blank to use HUE_LIGHT_ADDRESS env var.
    """
    r = max(0, min(255, red)) / 255.0
    g = max(0, min(255, green)) / 255.0
    b = max(0, min(255, blue)) / 255.0
    x, y = _rgb_to_xy(r, g, b)
    xy_bytes = pack("<HH", int(x * 0xFFFF), int(y * 0xFFFF))
    try:
        addr = _resolve_address(address)
        async with BleakClient(addr, timeout=15.0) as client:
            await client.write_gatt_char(UUID_POWER, bytes([0x01]), response=True)
            await client.write_gatt_char(UUID_XY_COLOR, xy_bytes, response=True)
        return f"Color set to RGB({red}, {green}, {blue})"
    except ValueError as e:
        return f"Error: {e}"
    except BleakError as e:
        return f"Bluetooth error: {e}"


@mcp.tool()
async def get_light_state(address: str = "") -> str:
    """
    Read the current state of a Philips Hue light (power, brightness, color mode).

    Args:
        address: Bluetooth address from scan_hue_lights. Leave blank to use HUE_LIGHT_ADDRESS env var.
    """
    try:
        addr = _resolve_address(address)
        async with BleakClient(addr, timeout=15.0) as client:
            power_raw      = await client.read_gatt_char(UUID_POWER)
            brightness_raw = await client.read_gatt_char(UUID_BRIGHTNESS)
            temp_raw       = await client.read_gatt_char(UUID_TEMPERATURE)
            xy_raw         = await client.read_gatt_char(UUID_XY_COLOR)

        power = "ON" if power_raw[0] == 0x01 else "OFF"
        brightness_pct = round(brightness_raw[0] / 254 * 100)
        temp_val = unpack("<H", temp_raw[:2])[0]
        xy_val   = unpack("<HH", xy_raw[:4])

        state: dict = {"power": power, "brightness_percent": brightness_pct}

        if temp_val != 0xFFFF:
            kelvin = round(1_000_000 / temp_val) if temp_val > 0 else 0
            state["mode"] = "color_temperature"
            state["color_temperature_kelvin"] = kelvin
            state["color_temperature_mireds"] = temp_val
        else:
            x = xy_val[0] / 0xFFFF
            y = xy_val[1] / 0xFFFF
            state["mode"] = "color"
            state["color_xy"] = {"x": round(x, 4), "y": round(y, 4)}

        return json.dumps(state, indent=2)
    except ValueError as e:
        return f"Error: {e}"
    except BleakError as e:
        return f"Bluetooth error: {e}"


@mcp.tool()
async def set_scene(scene: str, address: str = "") -> str:
    """
    Apply a preset lighting scene to a Philips Hue light.

    Available scenes:
      relax       - Dim warm amber, great for winding down
      energize    - Bright cool white, boost alertness
      concentrate - Bright neutral white, focus mode
      reading     - Warm white at comfortable reading level
      nightlight  - Very dim warm red, minimal sleep disruption
      bright      - Full brightness daylight white

    Args:
        scene: Scene name (case-insensitive)
        address: Bluetooth address from scan_hue_lights. Leave blank to use HUE_LIGHT_ADDRESS env var.
    """
    scenes = {
        "relax":       {"brightness": 36,  "kelvin": 2237},
        "energize":    {"brightness": 100, "kelvin": 6500},
        "concentrate": {"brightness": 90,  "kelvin": 4000},
        "reading":     {"brightness": 75,  "kelvin": 2890},
        "nightlight":  {"brightness": 5,   "kelvin": 2000},
        "bright":      {"brightness": 100, "kelvin": 6500},
    }

    scene_key = scene.strip().lower()
    if scene_key not in scenes:
        return f"Unknown scene '{scene}'. Available: {', '.join(scenes.keys())}"

    s = scenes[scene_key]
    brightness_raw = _scale_brightness(s["brightness"])
    mireds = _kelvin_to_mireds(s["kelvin"])

    try:
        addr = _resolve_address(address)
        async with BleakClient(addr, timeout=15.0) as client:
            await client.write_gatt_char(UUID_POWER, bytes([0x01]), response=True)
            await client.write_gatt_char(UUID_BRIGHTNESS, bytes([brightness_raw]), response=True)
            await client.write_gatt_char(UUID_TEMPERATURE, pack("<H", mireds), response=True)
        return f"Scene '{scene_key}' applied: {s['brightness']}% brightness, {s['kelvin']}K"
    except ValueError as e:
        return f"Error: {e}"
    except BleakError as e:
        return f"Bluetooth error: {e}"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
