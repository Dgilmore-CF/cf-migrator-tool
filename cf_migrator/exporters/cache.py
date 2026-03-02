"""Export cache-related configurations for a zone."""

import logging
from typing import Any

from cf_migrator.api_client import CloudflareClient, CloudflareAPIError
from cf_migrator.audit import AuditLog

logger = logging.getLogger("cf_migrator")


def export_cache_config(
    client: CloudflareClient,
    zone_id: str,
    zone_name: str,
    audit: AuditLog,
) -> dict[str, Any]:
    """Export caching settings for a zone.

    Collects:
      - Zone-level settings (cache_level, browser_cache_ttl, etc.)
      - Cache Rules (via ruleset phase)
      - Tiered Cache settings

    Returns a dict keyed by sub-resource.
    """
    logger.info("[%s] Exporting cache configuration…", zone_name)
    result: dict[str, Any] = {}

    # --- Zone settings (cache-relevant subset) ---
    cache_setting_keys = [
        "cache_level",
        "browser_cache_ttl",
        "always_online",
        "development_mode",
        "sort_query_string_for_cache",
        "edge_cache_ttl",
    ]
    try:
        resp = client.get(f"/zones/{zone_id}/settings")
        all_settings = resp.get("result", [])
        cache_settings = [s for s in all_settings if s.get("id") in cache_setting_keys]
        result["zone_cache_settings"] = cache_settings
        logger.info(
            "[%s] Exported %d cache-related zone setting(s).",
            zone_name,
            len(cache_settings),
        )
        audit.record(
            "export", "cache_settings", zone_name, "success",
            detail=f"{len(cache_settings)} settings",
        )
    except CloudflareAPIError as exc:
        logger.warning("[%s] Could not export zone settings: %s", zone_name, exc)
        audit.record("export", "cache_settings", zone_name, "failure", detail=str(exc))
        result["zone_cache_settings"] = []

    # --- Cache Rules (ruleset phase) ---
    try:
        resp = client.get(
            f"/zones/{zone_id}/rulesets/phases/http_request_cache_settings/entrypoint"
        )
        rules = resp.get("result", {}).get("rules", [])
        result["cache_rules"] = rules
        logger.info("[%s] Exported %d cache rule(s).", zone_name, len(rules))
        audit.record(
            "export", "cache_rules", zone_name, "success",
            detail=f"{len(rules)} cache rules",
        )
    except CloudflareAPIError as exc:
        logger.debug("[%s] No cache rules found: %s", zone_name, exc)
        audit.record("export", "cache_rules", zone_name, "skipped", detail=str(exc))
        result["cache_rules"] = []

    # --- Tiered Cache ---
    try:
        resp = client.get(f"/zones/{zone_id}/argo/tiered_caching")
        result["tiered_caching"] = resp.get("result", {})
        logger.info("[%s] Exported tiered caching settings.", zone_name)
        audit.record("export", "tiered_caching", zone_name, "success")
    except CloudflareAPIError as exc:
        logger.debug("[%s] Tiered caching not available: %s", zone_name, exc)
        audit.record("export", "tiered_caching", zone_name, "skipped", detail=str(exc))
        result["tiered_caching"] = {}

    return result
