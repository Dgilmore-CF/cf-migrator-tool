"""Export Load Balancer configurations for a zone."""

import logging
from typing import Any

from cf_migrator.api_client import CloudflareClient, CloudflareAPIError
from cf_migrator.audit import AuditLog

logger = logging.getLogger("cf_migrator")

STRIP_FIELDS = {"id", "created_on", "modified_on"}


def export_load_balancers(
    client: CloudflareClient,
    zone_id: str,
    zone_name: str,
    account_id: str,
    audit: AuditLog,
) -> dict[str, Any]:
    """Export load balancers, pools, and monitors.

    Returns:
        Dict with keys: load_balancers, pools, monitors.
    """
    logger.info("[%s] Exporting load balancer configuration…", zone_name)
    result: dict[str, Any] = {}

    # --- Load Balancers (zone-level) ---
    try:
        lbs = client.get_all_pages(f"/zones/{zone_id}/load_balancers")
        result["load_balancers"] = _strip_list(lbs)
        logger.info("[%s] Exported %d load balancer(s).", zone_name, len(lbs))
        audit.record(
            "export", "load_balancers", zone_name, "success",
            detail=f"{len(lbs)} load balancers",
        )
    except CloudflareAPIError as exc:
        logger.warning("[%s] Could not export load balancers: %s", zone_name, exc)
        audit.record("export", "load_balancers", zone_name, "failure", detail=str(exc))
        result["load_balancers"] = []

    # --- Pools (account-level) ---
    try:
        pools = client.get_all_pages(f"/accounts/{account_id}/load_balancers/pools")
        result["pools"] = _strip_list(pools)
        logger.info("[%s] Exported %d pool(s).", zone_name, len(pools))
        audit.record(
            "export", "lb_pools", zone_name, "success",
            detail=f"{len(pools)} pools",
        )
    except CloudflareAPIError as exc:
        logger.warning("[%s] Could not export pools: %s", zone_name, exc)
        audit.record("export", "lb_pools", zone_name, "failure", detail=str(exc))
        result["pools"] = []

    # --- Monitors (account-level) ---
    try:
        monitors = client.get_all_pages(
            f"/accounts/{account_id}/load_balancers/monitors"
        )
        result["monitors"] = _strip_list(monitors)
        logger.info("[%s] Exported %d monitor(s).", zone_name, len(monitors))
        audit.record(
            "export", "lb_monitors", zone_name, "success",
            detail=f"{len(monitors)} monitors",
        )
    except CloudflareAPIError as exc:
        logger.warning("[%s] Could not export monitors: %s", zone_name, exc)
        audit.record("export", "lb_monitors", zone_name, "failure", detail=str(exc))
        result["monitors"] = []

    return result


def _strip_list(items: list[dict]) -> list[dict]:
    """Remove system-managed fields from each dict."""
    return [{k: v for k, v in item.items() if k not in STRIP_FIELDS} for item in items]
