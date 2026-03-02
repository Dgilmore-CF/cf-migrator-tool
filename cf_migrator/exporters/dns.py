"""Export DNS records for a zone."""

import logging
from typing import Any

from cf_migrator.api_client import CloudflareClient, CloudflareAPIError
from cf_migrator.audit import AuditLog

logger = logging.getLogger("cf_migrator")

# Fields that are read-only / system-managed and should not be imported
STRIP_FIELDS = {"id", "created_on", "modified_on", "meta", "locked"}


def export_dns_records(
    client: CloudflareClient,
    zone_id: str,
    zone_name: str,
    audit: AuditLog,
) -> list[dict[str, Any]]:
    """Export all DNS records for the given zone.

    Args:
        client: Authenticated CloudflareClient.
        zone_id: Cloudflare zone ID.
        zone_name: Human-readable zone name for logging.
        audit: AuditLog instance.

    Returns:
        List of cleaned DNS record dicts ready for import.
    """
    logger.info("[%s] Exporting DNS records…", zone_name)
    try:
        records = client.get_all_pages(f"/zones/{zone_id}/dns_records")
    except CloudflareAPIError as exc:
        logger.error("[%s] Failed to export DNS records: %s", zone_name, exc)
        audit.record("export", "dns", zone_name, "failure", detail=str(exc))
        return []

    cleaned: list[dict[str, Any]] = []
    for rec in records:
        entry = {k: v for k, v in rec.items() if k not in STRIP_FIELDS}
        cleaned.append(entry)

    logger.info("[%s] Exported %d DNS record(s).", zone_name, len(cleaned))
    audit.record(
        "export", "dns", zone_name, "success",
        detail=f"Exported {len(cleaned)} DNS records",
    )
    return cleaned
