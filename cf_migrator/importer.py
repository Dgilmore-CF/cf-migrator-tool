"""Import / push configurations into a destination Cloudflare account."""

import json
import logging
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from cf_migrator.api_client import CloudflareClient, CloudflareAPIError
from cf_migrator.audit import AuditLog

logger = logging.getLogger("cf_migrator")
console = Console()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_export_file(path: str) -> dict[str, Any]:
    """Load and validate an export JSON file."""
    logger.info("Loading export file: %s", path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "metadata" not in data or "zones" not in data:
        raise ValueError("Invalid export file — missing 'metadata' or 'zones' keys.")

    logger.info(
        "Loaded export with %d zone(s), exported at %s",
        data["metadata"].get("zone_count", "?"),
        data["metadata"].get("exported_at", "?"),
    )
    return data


def preview_import(
    data: dict[str, Any],
    zone_filter: Optional[list[str]] = None,
) -> None:
    """Display a rich preview of what would be imported without making changes.

    Args:
        data: Parsed export data dict.
        zone_filter: Optional list of zone names to limit preview.
    """
    console.print(Panel("[bold cyan]Import Preview (Dry Run)[/bold cyan]", expand=False))

    meta = data.get("metadata", {})
    console.print(f"  Source account : [green]{meta.get('source_account_id', 'N/A')}[/green]")
    console.print(f"  Exported at    : {meta.get('exported_at', 'N/A')}")
    console.print(f"  Resource types : {', '.join(meta.get('resource_types', []))}")
    console.print()

    zones = data.get("zones", {})
    for zone_name, zone_data in zones.items():
        if zone_filter and zone_name not in zone_filter:
            continue

        table = Table(title=f"Zone: {zone_name}", show_lines=True, expand=False)
        table.add_column("Resource Type", style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Sample", style="dim", max_width=60)

        _add_preview_row(table, "DNS Records", zone_data.get("dns_records"))
        _add_waf_preview(table, zone_data.get("waf", {}))
        _add_rules_preview(table, zone_data.get("rules", {}))
        _add_lb_preview(table, zone_data.get("load_balancers", {}))
        _add_cache_preview(table, zone_data.get("cache", {}))

        console.print(table)
        console.print()


def import_to_account(
    client: CloudflareClient,
    data: dict[str, Any],
    dest_account_id: str,
    audit: AuditLog,
    zone_filter: Optional[list[str]] = None,
    dry_run: bool = False,
) -> None:
    """Push exported configurations into the destination account.

    Zones must already exist in the destination account. The importer
    matches by zone name.

    Args:
        client: Authenticated CloudflareClient for the destination account.
        data: Parsed export data dict.
        dest_account_id: Destination account ID.
        audit: AuditLog instance.
        zone_filter: Optional list of zone names to limit import.
        dry_run: If True, only preview — do not make API calls.
    """
    if dry_run:
        preview_import(data, zone_filter)
        return

    # Resolve destination zone IDs by name
    dest_zones = client.list_zones(account_id=dest_account_id)
    dest_zone_map = {z["name"]: z["id"] for z in dest_zones}

    zones = data.get("zones", {})
    for zone_name, zone_data in zones.items():
        if zone_filter and zone_name not in zone_filter:
            continue

        dest_zone_id = dest_zone_map.get(zone_name)
        if not dest_zone_id:
            logger.warning(
                "[%s] Zone not found in destination account — skipping.",
                zone_name,
            )
            audit.record("import", "zone", zone_name, "skipped", detail="Zone not found in dest")
            continue

        logger.info("=" * 60)
        logger.info("Importing into zone: %s (%s)", zone_name, dest_zone_id)
        logger.info("=" * 60)

        _import_dns(client, dest_zone_id, zone_name, zone_data.get("dns_records", []), audit)
        _import_page_rules(client, dest_zone_id, zone_name, zone_data.get("rules", {}), audit)
        _import_cache_settings(client, dest_zone_id, zone_name, zone_data.get("cache", {}), audit)
        _import_load_balancers(client, dest_zone_id, zone_name, dest_account_id, zone_data.get("load_balancers", {}), audit)

    logger.info("Import complete.")


# ---------------------------------------------------------------------------
# Preview helpers
# ---------------------------------------------------------------------------

def _add_preview_row(table: Table, label: str, items: Any) -> None:
    if items is None:
        return
    if isinstance(items, list):
        sample = json.dumps(items[0], indent=2)[:120] + "…" if items else "—"
        table.add_row(label, str(len(items)), sample)
    elif isinstance(items, dict):
        table.add_row(label, "1", json.dumps(items, indent=2)[:120] + "…")


def _add_waf_preview(table: Table, waf: dict) -> None:
    for key in ("firewall_rules", "waf_packages", "custom_rulesets"):
        items = waf.get(key, [])
        _add_preview_row(table, f"WAF / {key}", items)


def _add_rules_preview(table: Table, rules: dict) -> None:
    for key, items in rules.items():
        if isinstance(items, list):
            _add_preview_row(table, f"Rules / {key}", items)


def _add_lb_preview(table: Table, lb: dict) -> None:
    for key in ("load_balancers", "pools", "monitors"):
        _add_preview_row(table, f"LB / {key}", lb.get(key, []))


def _add_cache_preview(table: Table, cache: dict) -> None:
    for key in ("zone_cache_settings", "cache_rules"):
        _add_preview_row(table, f"Cache / {key}", cache.get(key, []))
    tc = cache.get("tiered_caching")
    if tc:
        _add_preview_row(table, "Cache / tiered_caching", tc)


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------

def _import_dns(
    client: CloudflareClient,
    zone_id: str,
    zone_name: str,
    records: list[dict],
    audit: AuditLog,
) -> None:
    """Create DNS records in destination zone."""
    if not records:
        return
    logger.info("[%s] Importing %d DNS record(s)…", zone_name, len(records))
    success = 0
    for rec in records:
        payload = {
            "type": rec.get("type"),
            "name": rec.get("name"),
            "content": rec.get("content"),
            "ttl": rec.get("ttl", 1),
            "proxied": rec.get("proxied", False),
        }
        if rec.get("priority") is not None:
            payload["priority"] = rec["priority"]
        try:
            client.post(f"/zones/{zone_id}/dns_records", json_body=payload)
            success += 1
        except CloudflareAPIError as exc:
            logger.warning(
                "[%s] Failed to create DNS record %s (%s): %s",
                zone_name, rec.get("name"), rec.get("type"), exc,
            )
            audit.record(
                "import", "dns", zone_name, "failure",
                detail=f"{rec.get('name')} ({rec.get('type')}): {exc}",
            )
    logger.info("[%s] Created %d/%d DNS record(s).", zone_name, success, len(records))
    audit.record(
        "import", "dns", zone_name, "success",
        detail=f"{success}/{len(records)} records created",
    )


def _import_page_rules(
    client: CloudflareClient,
    zone_id: str,
    zone_name: str,
    rules: dict,
    audit: AuditLog,
) -> None:
    """Create page rules in destination zone."""
    page_rules = rules.get("page_rules", [])
    if not page_rules:
        return
    logger.info("[%s] Importing %d page rule(s)…", zone_name, len(page_rules))
    success = 0
    for pr in page_rules:
        payload = {
            "targets": pr.get("targets", []),
            "actions": pr.get("actions", []),
            "priority": pr.get("priority", 1),
            "status": pr.get("status", "active"),
        }
        try:
            client.post(f"/zones/{zone_id}/pagerules", json_body=payload)
            success += 1
        except CloudflareAPIError as exc:
            logger.warning("[%s] Failed to create page rule: %s", zone_name, exc)
            audit.record("import", "page_rules", zone_name, "failure", detail=str(exc))
    logger.info("[%s] Created %d/%d page rule(s).", zone_name, success, len(page_rules))
    audit.record(
        "import", "page_rules", zone_name, "success",
        detail=f"{success}/{len(page_rules)} rules created",
    )


def _import_cache_settings(
    client: CloudflareClient,
    zone_id: str,
    zone_name: str,
    cache: dict,
    audit: AuditLog,
) -> None:
    """Apply cache-related zone settings in destination zone."""
    settings = cache.get("zone_cache_settings", [])
    if not settings:
        return
    logger.info("[%s] Applying %d cache setting(s)…", zone_name, len(settings))
    success = 0
    for setting in settings:
        setting_id = setting.get("id")
        value = setting.get("value")
        if setting_id is None or value is None:
            continue
        try:
            client.patch(
                f"/zones/{zone_id}/settings/{setting_id}",
                json_body={"value": value},
            )
            success += 1
        except CloudflareAPIError as exc:
            logger.warning(
                "[%s] Failed to set %s: %s", zone_name, setting_id, exc
            )
            audit.record(
                "import", "cache_settings", zone_name, "failure",
                detail=f"{setting_id}: {exc}",
            )
    logger.info("[%s] Applied %d/%d cache setting(s).", zone_name, success, len(settings))
    audit.record(
        "import", "cache_settings", zone_name, "success",
        detail=f"{success}/{len(settings)} settings applied",
    )


def _import_load_balancers(
    client: CloudflareClient,
    zone_id: str,
    zone_name: str,
    account_id: str,
    lb_data: dict,
    audit: AuditLog,
) -> None:
    """Create monitors, pools, and load balancers in the destination."""
    monitors = lb_data.get("monitors", [])
    pools = lb_data.get("pools", [])
    lbs = lb_data.get("load_balancers", [])

    if not (monitors or pools or lbs):
        return

    monitor_id_map: dict[str, str] = {}
    pool_id_map: dict[str, str] = {}

    # Monitors first
    for mon in monitors:
        old_id = mon.pop("id", None)
        try:
            resp = client.post(
                f"/accounts/{account_id}/load_balancers/monitors",
                json_body=mon,
            )
            new_id = resp.get("result", {}).get("id")
            if old_id and new_id:
                monitor_id_map[old_id] = new_id
            audit.record("import", "lb_monitors", zone_name, "success")
        except CloudflareAPIError as exc:
            logger.warning("[%s] Failed to create monitor: %s", zone_name, exc)
            audit.record("import", "lb_monitors", zone_name, "failure", detail=str(exc))

    # Pools (remap monitor references)
    for pool in pools:
        old_id = pool.pop("id", None)
        if pool.get("monitor") and pool["monitor"] in monitor_id_map:
            pool["monitor"] = monitor_id_map[pool["monitor"]]
        try:
            resp = client.post(
                f"/accounts/{account_id}/load_balancers/pools",
                json_body=pool,
            )
            new_id = resp.get("result", {}).get("id")
            if old_id and new_id:
                pool_id_map[old_id] = new_id
            audit.record("import", "lb_pools", zone_name, "success")
        except CloudflareAPIError as exc:
            logger.warning("[%s] Failed to create pool: %s", zone_name, exc)
            audit.record("import", "lb_pools", zone_name, "failure", detail=str(exc))

    # Load Balancers (remap pool references)
    for lb in lbs:
        lb.pop("id", None)
        if "default_pools" in lb:
            lb["default_pools"] = [
                pool_id_map.get(pid, pid) for pid in lb["default_pools"]
            ]
        if "fallback_pool" in lb and lb["fallback_pool"] in pool_id_map:
            lb["fallback_pool"] = pool_id_map[lb["fallback_pool"]]
        if "region_pools" in lb:
            for region, pids in lb["region_pools"].items():
                lb["region_pools"][region] = [
                    pool_id_map.get(pid, pid) for pid in pids
                ]
        try:
            client.post(f"/zones/{zone_id}/load_balancers", json_body=lb)
            audit.record("import", "load_balancers", zone_name, "success")
        except CloudflareAPIError as exc:
            logger.warning("[%s] Failed to create load balancer: %s", zone_name, exc)
            audit.record("import", "load_balancers", zone_name, "failure", detail=str(exc))

    logger.info("[%s] Load balancer import finished.", zone_name)
