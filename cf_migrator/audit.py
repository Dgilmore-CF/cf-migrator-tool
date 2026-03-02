"""Audit trail for all migration operations."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional


class AuditLog:
    """Records every significant action taken during export/import for traceability."""

    def __init__(self, audit_dir: str = "audit"):
        self.audit_dir = audit_dir
        os.makedirs(audit_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.audit_file = os.path.join(audit_dir, f"audit_{timestamp}.json")
        self.entries: list[dict[str, Any]] = []

    def record(
        self,
        action: str,
        resource_type: str,
        zone: str,
        status: str,
        detail: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> None:
        """Record an audit entry.

        Args:
            action: The operation performed (export, import, preview, skip, error).
            resource_type: Type of resource (dns, waf, rules, lb, cache, zone).
            zone: The zone name or ID the action relates to.
            status: Outcome (success, failure, skipped, previewed).
            detail: Optional human-readable detail string.
            data: Optional dict of extra context.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "resource_type": resource_type,
            "zone": zone,
            "status": status,
            "detail": detail,
            "data": data,
        }
        self.entries.append(entry)

    def save(self) -> str:
        """Persist audit log to disk and return the file path."""
        with open(self.audit_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "total_entries": len(self.entries),
                    "entries": self.entries,
                },
                f,
                indent=2,
            )
        return self.audit_file

    def summary(self) -> dict[str, int]:
        """Return a status summary count."""
        counts: dict[str, int] = {}
        for e in self.entries:
            s = e["status"]
            counts[s] = counts.get(s, 0) + 1
        return counts
