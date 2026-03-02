"""Export WAF (Web Application Firewall) configurations for a zone."""

import logging
from typing import Any

from cf_migrator.api_client import CloudflareClient, CloudflareAPIError
from cf_migrator.audit import AuditLog

logger = logging.getLogger("cf_migrator")


def export_waf_config(
    client: CloudflareClient,
    zone_id: str,
    zone_name: str,
    audit: AuditLog,
) -> dict[str, Any]:
    """Export WAF-related configurations.

    Collects:
      - WAF custom rules (firewall rules)
      - WAF packages and rule overrides (managed rulesets)
      - Custom WAF rulesets (new ruleset engine)

    Returns a dict keyed by sub-resource type.
    """
    logger.info("[%s] Exporting WAF configuration…", zone_name)
    result: dict[str, Any] = {}

    # --- Firewall rules (classic) ---
    try:
        fw_rules = client.get_all_pages(f"/zones/{zone_id}/firewall/rules")
        result["firewall_rules"] = fw_rules
        logger.info("[%s] Exported %d firewall rule(s).", zone_name, len(fw_rules))
        audit.record(
            "export", "waf_firewall_rules", zone_name, "success",
            detail=f"{len(fw_rules)} firewall rules",
        )
    except CloudflareAPIError as exc:
        logger.warning("[%s] Could not export firewall rules: %s", zone_name, exc)
        audit.record("export", "waf_firewall_rules", zone_name, "failure", detail=str(exc))
        result["firewall_rules"] = []

    # --- WAF managed rulesets / packages ---
    try:
        packages = client.get_all_pages(f"/zones/{zone_id}/firewall/waf/packages")
        result["waf_packages"] = packages
        logger.info("[%s] Exported %d WAF package(s).", zone_name, len(packages))
        audit.record(
            "export", "waf_packages", zone_name, "success",
            detail=f"{len(packages)} WAF packages",
        )
    except CloudflareAPIError as exc:
        logger.warning("[%s] Could not export WAF packages: %s", zone_name, exc)
        audit.record("export", "waf_packages", zone_name, "failure", detail=str(exc))
        result["waf_packages"] = []

    # --- Custom rulesets (new ruleset engine) ---
    try:
        resp = client.get(f"/zones/{zone_id}/rulesets")
        rulesets = resp.get("result", [])
        detailed_rulesets = []
        for rs in rulesets:
            if rs.get("kind") in ("zone", "custom"):
                try:
                    detail = client.get(f"/zones/{zone_id}/rulesets/{rs['id']}")
                    detailed_rulesets.append(detail.get("result", rs))
                except CloudflareAPIError:
                    detailed_rulesets.append(rs)
        result["custom_rulesets"] = detailed_rulesets
        logger.info("[%s] Exported %d custom ruleset(s).", zone_name, len(detailed_rulesets))
        audit.record(
            "export", "waf_custom_rulesets", zone_name, "success",
            detail=f"{len(detailed_rulesets)} custom rulesets",
        )
    except CloudflareAPIError as exc:
        logger.warning("[%s] Could not export custom rulesets: %s", zone_name, exc)
        audit.record("export", "waf_custom_rulesets", zone_name, "failure", detail=str(exc))
        result["custom_rulesets"] = []

    return result
