"""Control Philips Hue lights with hueru.

Key Features:

- List lights
- Send lights commands

Examples:

    List the Hue lights:

    ```bash
    hueru list
    ```

    Set a light to an RGB color:

    ```bash
    hueru set <light-id> rgb <r> <g> <b>
    ```
"""

import asyncio
import click
import aiohttp
import functools
import json
import os

from aiohue import create_app_key, LinkButtonNotPressed
from aiohue.discovery import discover_nupnp
from aiohue.v2 import HueBridgeV2

CONFIG_FILE = ".hueru.json"

async def get_bridge(session):
    """Get a connected and initialized aiohue HueBridgeV2 object."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        bridge = HueBridgeV2(config["host"], config["app_key"])
    else:
        print("Searching for Hue bridges...")
        bridges = await discover_nupnp(session)
        if not bridges:
            print("No Hue bridges found on your network.")
            return None
        
        host = bridges[0].host
        print(f"Found bridge at {host}")
        print("Please press the link button on the bridge.")
        
        try:
            app_key = await create_app_key(host, "hueru", session)
            print(f"Successfully created user: {app_key}")
            config = {"host": host, "app_key": app_key}
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f)
            bridge = HueBridgeV2(host, app_key)
        except LinkButtonNotPressed:
            print("Link button not pressed.")
            return None
        except Exception as e:
            print(f"Failed to create user: {e}")
            return None

    try:
        await bridge.initialize()
        return bridge
    except Exception as e:
        print(f"Failed to connect to bridge: {e}")
        # Config might be stale, delete it.
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        print("Removed stale config file. Please try again.")
        return None

def async_command(f):
    """A decorator to run click commands asynchronously."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

@click.group()
def main():
    """Control Philips Hue lights with hueru."""
    pass

@main.command()
@async_command
async def list():
    """List the Hue lights."""
    async with aiohttp.ClientSession() as session:
        bridge = await get_bridge(session)
        if bridge:
            for light in bridge.lights:
                if not light.owner:
                    continue
                device_id = light.owner.rid
                if device_id not in bridge.devices:
                    continue
                device = bridge.devices[device_id]
                print(f"{light.id}: {device.metadata.name}")


@main.group()
def set():
    """Set a light to a specific state."""
    pass

@set.command()
@click.argument('light_id', type=str)
@click.argument('r', type=int)
@click.argument('g', type=int)
@click.argument('b', type=int)
@async_command
async def rgb(light_id, r, g, b):
    """Set a light to an RGB color."""
    async with aiohttp.ClientSession() as session:
        bridge = await get_bridge(session)
        if bridge:
            # aiohue also uses xy, so we reuse the conversion.
            # Normalize to 0-1 range
            r_norm = r / 255.0
            g_norm = g / 255.0
            b_norm = b / 255.0

            # Apply gamma correction
            r_final = pow(r_norm, 2.2)
            g_final = pow(g_norm, 2.2)
            b_final = pow(b_norm, 2.2)

            # Convert to XYZ
            X = r_final * 0.649926 + g_final * 0.103455 + b_final * 0.197109
            Y = r_final * 0.234327 + g_final * 0.743075 + b_final * 0.022598
            Z = r_final * 0.000000 + g_final * 0.053077 + b_final * 1.035763

            # Convert to xy
            if (X + Y + Z) == 0:
                x = 0
                y = 0
            else:
                x = X / (X + Y + Z)
                y = Y / (X + Y + Z)
            
            await bridge.lights.set_state(light_id, on=True, color_xy=[x, y])
            print(f"Set light {light_id} to rgb({r},{g},{b})")

if __name__ == "__main__":
    main()
