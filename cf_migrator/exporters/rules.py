"""Export Page Rules, Transform Rules, Redirect Rules, and other rule types."""

import logging
from typing import Any

from cf_migrator.api_client import CloudflareClient, CloudflareAPIError
from cf_migrator.audit import AuditLog

logger = logging.getLogger("cf_migrator")


def export_rules(
    client: CloudflareClient,
    zone_id: str,
    zone_name: str,
    audit: AuditLog,
) -> dict[str, Any]:
    """Export all rule-type configurations for a zone.

    Collects:
      - Page Rules
      - Transform Rules (URL Rewrite, Header Modification, etc.)
      - Redirect Rules (Bulk Redirects at zone level)
      - Configuration Rules
      - Origin Rules

    Returns a dict keyed by sub-resource type.
    """
    logger.info("[%s] Exporting rules…", zone_name)
    result: dict[str, Any] = {}

    # --- Page Rules ---
    try:
        page_rules = client.get_all_pages(f"/zones/{zone_id}/pagerules")
        result["page_rules"] = page_rules
        logger.info("[%s] Exported %d page rule(s).", zone_name, len(page_rules))
        audit.record(
            "export", "page_rules", zone_name, "success",
            detail=f"{len(page_rules)} page rules",
        )
    except CloudflareAPIError as exc:
        logger.warning("[%s] Could not export page rules: %s", zone_name, exc)
        audit.record("export", "page_rules", zone_name, "failure", detail=str(exc))
        result["page_rules"] = []

    # --- Rulesets by phase (Transform, Redirect, Config, Origin) ---
    phases = {
        "http_request_transform": "transform_rules",
        "http_request_late_transform": "late_transform_rules",
        "http_response_headers_transform": "response_header_rules",
        "http_request_redirect": "redirect_rules",
        "http_config_settings": "configuration_rules",
        "http_request_origin": "origin_rules",
        "http_request_cache_settings": "cache_rules",
        "http_request_dynamic_redirect": "dynamic_redirect_rules",
    }

    for phase, key in phases.items():
        try:
            resp = client.get(f"/zones/{zone_id}/rulesets/phases/{phase}/entrypoint")
            ruleset = resp.get("result", {})
            rules = ruleset.get("rules", [])
            result[key] = rules
            logger.info("[%s] Exported %d %s.", zone_name, len(rules), key)
            audit.record(
                "export", key, zone_name, "success",
                detail=f"{len(rules)} rules",
            )
        except CloudflareAPIError as exc:
            # Some phases may not exist for all plans — that's okay
            logger.debug("[%s] Phase %s not available: %s", zone_name, phase, exc)
            audit.record("export", key, zone_name, "skipped", detail=str(exc))
            result[key] = []

    return result
