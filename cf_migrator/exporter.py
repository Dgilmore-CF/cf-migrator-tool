"""Top-level export orchestrator — collects all resource types for selected zones."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from cf_migrator.api_client import CloudflareClient
from cf_migrator.audit import AuditLog
from cf_migrator.exporters.cache import export_cache_config
from cf_migrator.exporters.dns import export_dns_records
from cf_migrator.exporters.load_balancers import export_load_balancers
from cf_migrator.exporters.rules import export_rules
from cf_migrator.exporters.waf import export_waf_config

logger = logging.getLogger("cf_migrator")


def export_zones(
    client: CloudflareClient,
    zones: list[dict],
    account_id: str,
    audit: AuditLog,
    output_dir: str = "exports",
    resources: Optional[list[str]] = None,
) -> str:
    """Export configurations for all selected zones to a single JSON file.

    Args:
        client: Authenticated CloudflareClient.
        zones: List of zone dicts (must contain 'id' and 'name').
        account_id: Source Cloudflare account ID.
        audit: AuditLog instance.
        output_dir: Directory for the output file.
        resources: Optional list of resource types to export.
                   Accepted values: dns, waf, rules, load_balancers, cache.
                   None means export everything.

    Returns:
        Path to the generated JSON export file.
    """
    all_resources = {"dns", "waf", "rules", "load_balancers", "cache"}
    selected = set(resources) & all_resources if resources else all_resources

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"cf_export_{timestamp}.json")

    export_data: dict[str, Any] = {
        "metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source_account_id": account_id,
            "zone_count": len(zones),
            "resource_types": sorted(selected),
        },
        "zones": {},
    }

    for zone in zones:
        zone_id = zone["id"]
        zone_name = zone["name"]
        logger.info("=" * 60)
        logger.info("Exporting zone: %s (%s)", zone_name, zone_id)
        logger.info("=" * 60)

        zone_data: dict[str, Any] = {
            "zone_id": zone_id,
            "zone_name": zone_name,
            "status": zone.get("status"),
            "plan": zone.get("plan", {}).get("name"),
        }

        audit.record("export", "zone", zone_name, "success", detail="Started export")

        if "dns" in selected:
            zone_data["dns_records"] = export_dns_records(
                client, zone_id, zone_name, audit
            )

        if "waf" in selected:
            zone_data["waf"] = export_waf_config(client, zone_id, zone_name, audit)

        if "rules" in selected:
            zone_data["rules"] = export_rules(client, zone_id, zone_name, audit)

        if "load_balancers" in selected:
            zone_data["load_balancers"] = export_load_balancers(
                client, zone_id, zone_name, account_id, audit
            )

        if "cache" in selected:
            zone_data["cache"] = export_cache_config(client, zone_id, zone_name, audit)

        export_data["zones"][zone_name] = zone_data

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, default=str)

    logger.info("Export complete — written to %s", output_file)
    audit.record(
        "export", "file", "all", "success",
        detail=f"Written to {output_file}",
    )
    return output_file
