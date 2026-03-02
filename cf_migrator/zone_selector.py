"""Interactive and programmatic zone selection."""

import logging
from typing import Optional

from rich.console import Console
from rich.table import Table

from cf_migrator.api_client import CloudflareClient

logger = logging.getLogger("cf_migrator")
console = Console()


def list_and_select_zones(
    client: CloudflareClient,
    account_id: Optional[str] = None,
    select_all: bool = False,
    zone_names: Optional[list[str]] = None,
) -> list[dict]:
    """Retrieve zones and let the user select which ones to migrate.

    Args:
        client: Authenticated CloudflareClient.
        account_id: Optional account ID filter.
        select_all: If True, return every zone without prompting.
        zone_names: If provided, filter to only these zone names.

    Returns:
        List of zone dicts selected for migration.
    """
    logger.info("Fetching zones from Cloudflare…")
    zones = client.list_zones(account_id=account_id)

    if not zones:
        logger.warning("No zones found for this account.")
        return []

    logger.info("Found %d zone(s).", len(zones))

    # Filter by explicit names if provided via CLI
    if zone_names:
        lower_names = {n.lower() for n in zone_names}
        zones = [z for z in zones if z["name"].lower() in lower_names]
        if not zones:
            logger.error("None of the specified zone names matched.")
            return []
        logger.info("Filtered to %d zone(s) by name.", len(zones))
        return zones

    if select_all:
        logger.info("--all flag set — selecting every zone.")
        return zones

    # Interactive selection
    return _interactive_select(zones)


def _interactive_select(zones: list[dict]) -> list[dict]:
    """Display a numbered table and let the user pick zones interactively."""
    table = Table(title="Available Zones", show_lines=True)
    table.add_column("#", style="bold cyan", justify="right")
    table.add_column("Zone Name", style="green")
    table.add_column("Zone ID", style="dim")
    table.add_column("Status", style="yellow")
    table.add_column("Plan", style="magenta")

    for idx, z in enumerate(zones, 1):
        table.add_row(
            str(idx),
            z.get("name", ""),
            z.get("id", ""),
            z.get("status", ""),
            z.get("plan", {}).get("name", ""),
        )

    console.print(table)
    console.print(
        "\n[bold]Enter zone numbers to migrate (comma-separated), "
        "'all' for everything, or 'q' to quit:[/bold]"
    )

    while True:
        choice = console.input("[cyan]> [/cyan]").strip().lower()

        if choice in ("q", "quit", "exit"):
            logger.info("User cancelled zone selection.")
            return []

        if choice == "all":
            return zones

        try:
            indices = [int(x.strip()) for x in choice.split(",")]
            selected = []
            for i in indices:
                if 1 <= i <= len(zones):
                    selected.append(zones[i - 1])
                else:
                    console.print(f"[red]Index {i} out of range — skipping.[/red]")
            if selected:
                names = ", ".join(z["name"] for z in selected)
                logger.info("Selected zones: %s", names)
                return selected
            console.print("[red]No valid zones selected. Try again.[/red]")
        except ValueError:
            console.print("[red]Invalid input. Enter numbers separated by commas.[/red]")
