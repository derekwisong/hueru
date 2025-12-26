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
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import aiohttp
import click
from aiohue import LinkButtonNotPressed, create_app_key
from aiohue.discovery import discover_nupnp
from aiohue.v2 import HueBridgeV2

from hueru.colors import rgb_to_xy
from hueru.screen import ScreenScanner

CONFIG_FILE = Path.home() / ".hueru.json"
RETRY_DELAY_SECONDS = 5
MAX_RETRIES = 12  # Gives 60 seconds for the user to press the button


@asynccontextmanager
async def get_bridge(reset_key=False):
    """A context manager to discover, configure, and connect to a Hue bridge."""
    config = {}
    if CONFIG_FILE.exists() and CONFIG_FILE.stat().st_size > 0:
        try:
            config = json.loads(CONFIG_FILE.read_text())
        except json.JSONDecodeError:
            print(
                f"Warning: Could not parse config file at {CONFIG_FILE}. Starting fresh."
            )
            config = {}

    host = config.get("host")
    app_key = config.get("app_key")
    bridge = None

    async with aiohttp.ClientSession() as session:
        if host and app_key:
            # Try to connect with existing host and app_key
            try:
                # aiohue doesn't have a simple "check connection" so we try to init
                bridge = HueBridgeV2(host, app_key)
                await bridge.initialize()
                print(f"Connected to previously known bridge at {host}")
            except Exception as e:
                print(
                    f"Could not connect to bridge at {host} with app_key {app_key}.",
                    file=sys.stderr,
                )
                if reset_key:
                    if "app_key" in config:
                        del config["app_key"]
                        CONFIG_FILE.write_text(json.dumps(config, indent=2))
                        print(
                            "Removed potentially invalid application key. Please try again.",
                            file=sys.stderr,
                        )
                else:
                    print(
                        "To reset the application key, run with the --reset-key flag.",
                        file=sys.stderr,
                    )
                sys.exit(1)

        if not host:
            print("Searching for Hue bridges...")
            bridges = await discover_nupnp(session)
            if not bridges:
                print("No Hue bridges found on your network.", file=sys.stderr)
                sys.exit(1)
            host = bridges[0].host
            config["host"] = host
            CONFIG_FILE.write_text(json.dumps(config, indent=2))
            print(f"Found bridge at {host}. Updating config.")

        if not app_key and reset_key:
            print(
                "No application key found. Please press the link button on the bridge."
            )
            for i in range(MAX_RETRIES):
                try:
                    app_key = await create_app_key(host, "hueru", session)
                    config["app_key"] = app_key
                    CONFIG_FILE.write_text(json.dumps(config, indent=2))
                    print(f"Successfully created application key: {app_key}")
                    break
                except LinkButtonNotPressed:
                    print(
                        f"Button not pressed. Retrying in {RETRY_DELAY_SECONDS}s... ({i+1}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                except Exception as e:
                    print(f"An unexpected error occurred: {e}", file=sys.stderr)
                    sys.exit(1)
            else:
                print("Link button was not pressed.", file=sys.stderr)
                sys.exit(1)
        elif not app_key:
            print(
                "No application key found. To create one, run with the --reset-key flag.",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            # Final connection attempt with all details
            if not bridge:
                bridge = HueBridgeV2(host, app_key)
                await bridge.initialize()

            yield bridge

        except Exception as e:
            print(f"Failed to connect to Hue bridge: {e}", file=sys.stderr)
            if reset_key:
                if "app_key" in config:
                    del config["app_key"]
                    CONFIG_FILE.write_text(json.dumps(config, indent=2))
                    print(
                        "Removed potentially invalid application key. Please try again.",
                        file=sys.stderr,
                    )
            else:
                print(
                    "To reset the application key, run with the --reset-key flag.",
                    file=sys.stderr,
                )
            sys.exit(1)
        finally:
            if bridge:
                await bridge.close()


@click.group()
@click.option(
    "--reset-key", is_flag=True, help="Reset the application key if connection fails."
)
@click.pass_context
def main(ctx, reset_key):
    """Control Philips Hue lights with hueru."""
    ctx.obj = {"reset_key": reset_key}


async def run_command(ctx, coro):
    """Runs a command that requires a bridge object."""
    async with get_bridge(ctx.obj.get("reset_key", False)) as bridge:
        ctx.obj["bridge"] = bridge
        await coro(ctx)


@main.command()
@click.pass_context
def list(ctx):
    """List the Hue lights."""

    async def command(ctx):
        bridge = ctx.obj["bridge"]
        for light in sorted(bridge.lights, key=lambda l: l.id):
            if not light.owner:
                continue
            device_id = light.owner.rid
            if device_id not in bridge.devices:
                continue
            device = bridge.devices[device_id]
            print(f"{light.id}: {device.metadata.name}")

    asyncio.run(run_command(ctx, command))


@main.group()
def set():
    """Set a light to a specific state."""
    pass


@set.command()
@click.argument("light_id", type=str)
@click.pass_context
def on(ctx, light_id):
    """Turn a light on."""

    async def command(ctx):
        bridge = ctx.obj["bridge"]
        await bridge.lights.set_state(light_id, on=True)
        print(f"Turned light {light_id} on")

    asyncio.run(run_command(ctx, command))


@set.command()
@click.argument("light_id", type=str)
@click.pass_context
def off(ctx, light_id):
    """Turn a light off."""

    async def command(ctx):
        bridge = ctx.obj["bridge"]
        await bridge.lights.set_state(light_id, on=False)
        print(f"Turned light {light_id} off")

    asyncio.run(run_command(ctx, command))


@set.command()
@click.argument("light_id", type=str)
@click.argument("r", type=int)
@click.argument("g", type=int)
@click.argument("b", type=int)
@click.pass_context
def rgb(ctx, light_id, r, g, b):
    """Set a light to an RGB color."""

    async def command(ctx):
        bridge = ctx.obj["bridge"]
        x, y = rgb_to_xy(r, g, b)
        await bridge.lights.set_state(light_id, on=True, color_xy=[x, y])
        print(f"Set light {light_id} to rgb({r},{g},{b})")

    asyncio.run(run_command(ctx, command))

@main.group()
def screen():
    """Commands for screen based automations."""

    pass

@screen.command()
@click.argument("light_id", type=str)
@click.pass_context
def bottom(ctx, light_id):
    """Continuously set a light to the average color of the bottom of the screen."""

    async def command(ctx):
        bridge = ctx.obj["bridge"]
        try:
            with ScreenScanner() as scanner:
                while True:
                    r, g, b = scanner.get_region_color(0, 0.75, 1, 1)
                    x, y = rgb_to_xy(r, g, b)
                    await bridge.lights.set_state(light_id, on=True, color_xy=[x, y])
                    print(f"Set light {light_id} to rgb({r},{g},{b})")
                    await asyncio.sleep(0.1)  # prevent busy-looping
        except RuntimeError as e:
            print(f"Error during screen capture: {e}", file=sys.stderr)
            sys.exit(1)

    asyncio.run(run_command(ctx, command))


if __name__ == "__main__":
    main()
