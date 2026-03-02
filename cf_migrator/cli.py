"""CLI entry point for the Cloudflare Migration Tool."""

import sys

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from cf_migrator import __version__
from cf_migrator.api_client import CloudflareClient, CloudflareAPIError
from cf_migrator.audit import AuditLog
from cf_migrator.exporter import export_zones
from cf_migrator.importer import import_to_account, load_export_file, preview_import
from cf_migrator.logger import setup_logging
from cf_migrator.zone_selector import list_and_select_zones

console = Console()

RESOURCE_TYPES = ["dns", "waf", "rules", "load_balancers", "cache"]


@click.group()
@click.version_option(version=__version__, prog_name="cf-migrator")
def cli() -> None:
    """Cloudflare Migration Tool — export and import zone configurations."""
    load_dotenv()


# -----------------------------------------------------------------------
# EXPORT command
# -----------------------------------------------------------------------
@cli.command()
@click.option("--api-token", envvar="CF_SOURCE_API_TOKEN", required=True, help="Source Cloudflare API token.")
@click.option("--account-id", envvar="CF_SOURCE_ACCOUNT_ID", required=True, help="Source account ID.")
@click.option("--all-zones", is_flag=True, default=False, help="Export all zones without prompting.")
@click.option("--zones", "zone_names", multiple=True, help="Specific zone name(s) to export (repeatable).")
@click.option("--resources", "resource_list", multiple=True, type=click.Choice(RESOURCE_TYPES, case_sensitive=False), help="Resource types to export (repeatable). Default: all.")
@click.option("--output-dir", default="exports", show_default=True, help="Directory for export files.")
@click.option("--log-level", default="INFO", show_default=True, type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False))
def export(api_token, account_id, all_zones, zone_names, resource_list, output_dir, log_level):
    """Export zone configurations from a Cloudflare account."""
    logger = setup_logging(level=log_level)
    audit = AuditLog()

    console.print(Panel(f"[bold green]Cloudflare Migrator v{__version__} — Export[/bold green]", expand=False))

    client = CloudflareClient(api_token)

    # Verify token
    console.print("[dim]Verifying API token…[/dim]")
    if not client.verify_token():
        console.print("[bold red]API token verification failed. Check your token and try again.[/bold red]")
        logger.error("API token verification failed.")
        sys.exit(1)
    console.print("[green]✓ Token verified.[/green]\n")

    # Select zones
    try:
        zones = list_and_select_zones(
            client,
            account_id=account_id,
            select_all=all_zones,
            zone_names=list(zone_names) if zone_names else None,
        )
    except CloudflareAPIError as exc:
        logger.error("Failed to list zones: %s", exc)
        console.print(f"[bold red]Error listing zones: {exc}[/bold red]")
        sys.exit(1)

    if not zones:
        console.print("[yellow]No zones selected — nothing to export.[/yellow]")
        sys.exit(0)

    # Run export
    resources = list(resource_list) if resource_list else None
    try:
        output_path = export_zones(
            client, zones, account_id, audit,
            output_dir=output_dir, resources=resources,
        )
    except Exception as exc:
        logger.exception("Export failed: %s", exc)
        console.print(f"[bold red]Export failed: {exc}[/bold red]")
        sys.exit(1)

    # Save audit log
    audit_path = audit.save()
    summary = audit.summary()

    console.print()
    console.print(Panel(
        f"[bold green]Export complete![/bold green]\n\n"
        f"  Export file : [cyan]{output_path}[/cyan]\n"
        f"  Audit log   : [cyan]{audit_path}[/cyan]\n"
        f"  Summary     : {summary}",
        title="Results",
        expand=False,
    ))


# -----------------------------------------------------------------------
# PREVIEW command
# -----------------------------------------------------------------------
@cli.command()
@click.argument("export_file", type=click.Path(exists=True))
@click.option("--zones", "zone_names", multiple=True, help="Limit preview to specific zone name(s).")
def preview(export_file, zone_names):
    """Preview the contents of an export file without making any changes."""
    setup_logging(level="INFO")
    data = load_export_file(export_file)
    zone_filter = list(zone_names) if zone_names else None
    preview_import(data, zone_filter=zone_filter)


# -----------------------------------------------------------------------
# IMPORT command
# -----------------------------------------------------------------------
@cli.command(name="import")
@click.argument("export_file", type=click.Path(exists=True))
@click.option("--api-token", envvar="CF_DEST_API_TOKEN", required=True, help="Destination Cloudflare API token.")
@click.option("--account-id", envvar="CF_DEST_ACCOUNT_ID", required=True, help="Destination account ID.")
@click.option("--zones", "zone_names", multiple=True, help="Limit import to specific zone name(s).")
@click.option("--dry-run", is_flag=True, default=False, help="Preview changes without applying them.")
@click.option("--yes", is_flag=True, default=False, help="Skip confirmation prompt.")
@click.option("--log-level", default="INFO", show_default=True, type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False))
def import_cmd(export_file, api_token, account_id, zone_names, dry_run, yes, log_level):
    """Import configurations from an export file into a destination account."""
    logger = setup_logging(level=log_level)
    audit = AuditLog()

    console.print(Panel(f"[bold green]Cloudflare Migrator v{__version__} — Import[/bold green]", expand=False))

    data = load_export_file(export_file)
    zone_filter = list(zone_names) if zone_names else None

    if dry_run:
        preview_import(data, zone_filter=zone_filter)
        console.print("[yellow]Dry run — no changes were made.[/yellow]")
        return

    # Show preview first
    preview_import(data, zone_filter=zone_filter)

    if not yes:
        console.print()
        if not click.confirm("Proceed with import?", default=False):
            console.print("[yellow]Import cancelled by user.[/yellow]")
            logger.info("Import cancelled by user.")
            return

    client = CloudflareClient(api_token)

    console.print("[dim]Verifying destination API token…[/dim]")
    if not client.verify_token():
        console.print("[bold red]Destination API token verification failed.[/bold red]")
        logger.error("Destination API token verification failed.")
        sys.exit(1)
    console.print("[green]✓ Token verified.[/green]\n")

    try:
        import_to_account(
            client, data, account_id, audit,
            zone_filter=zone_filter, dry_run=False,
        )
    except Exception as exc:
        logger.exception("Import failed: %s", exc)
        console.print(f"[bold red]Import failed: {exc}[/bold red]")
        sys.exit(1)

    audit_path = audit.save()
    summary = audit.summary()

    console.print()
    console.print(Panel(
        f"[bold green]Import complete![/bold green]\n\n"
        f"  Audit log : [cyan]{audit_path}[/cyan]\n"
        f"  Summary   : {summary}",
        title="Results",
        expand=False,
    ))


# -----------------------------------------------------------------------
# AUDIT command — inspect an existing audit log
# -----------------------------------------------------------------------
@cli.command()
@click.argument("audit_file", type=click.Path(exists=True))
def audit(audit_file):
    """Display a formatted view of an audit log file."""
    import json

    with open(audit_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    from rich.table import Table

    table = Table(title=f"Audit Log — {data.get('generated_at', '?')}", show_lines=True)
    table.add_column("Timestamp", style="dim")
    table.add_column("Action", style="cyan")
    table.add_column("Resource", style="green")
    table.add_column("Zone", style="yellow")
    table.add_column("Status", style="bold")
    table.add_column("Detail", style="dim", max_width=50)

    for entry in data.get("entries", []):
        status_style = {
            "success": "[green]success[/green]",
            "failure": "[red]failure[/red]",
            "skipped": "[yellow]skipped[/yellow]",
            "previewed": "[cyan]previewed[/cyan]",
        }.get(entry.get("status", ""), entry.get("status", ""))

        table.add_row(
            entry.get("timestamp", ""),
            entry.get("action", ""),
            entry.get("resource_type", ""),
            entry.get("zone", ""),
            status_style,
            entry.get("detail", "") or "",
        )

    console.print(table)
    console.print(f"\nTotal entries: {data.get('total_entries', 0)}")


def main() -> None:
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
