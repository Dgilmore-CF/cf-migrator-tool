# Cloudflare Migration Tool (`cf-migrator`)

> **DISCLAIMER:** This is an **independent, community-developed** tool. It is **not** an official Cloudflare product, nor is it endorsed, supported, maintained, or affiliated with Cloudflare, Inc. in any way. Use of this tool is entirely at your own risk. Please refer to the [full disclaimer](#disclaimer) below before use.

A Python CLI utility to **export** Cloudflare zone configurations from one account and **import** them into another. Supports DNS records, WAF rules, Page Rules, Transform/Redirect/Origin Rules, Load Balancers, and Cache settings — with comprehensive logging, auditing, and a dry-run preview mode.

---

## Features

| Capability | Details |
|---|---|
| **Zone Selection** | Export all zones, pick interactively, or pass specific zone names via CLI. |
| **DNS Records** | A, AAAA, CNAME, MX, TXT, SRV, CAA, NS, and all other record types. |
| **WAF** | Classic firewall rules, managed WAF packages, and new custom rulesets. |
| **Rules** | Page Rules, Transform Rules, Redirect Rules, Configuration Rules, Origin Rules, Cache Rules. |
| **Load Balancers** | Load balancers, origin pools, and health monitors with automatic ID remapping on import. |
| **Cache** | Zone-level cache settings, Cache Rules (ruleset engine), and Tiered Caching config. |
| **Preview / Dry Run** | Inspect exactly what will be imported before committing any changes. |
| **Audit Trail** | Every action is recorded to a timestamped JSON audit log. |
| **Logging** | Dual output — console (human-friendly) and file (detailed debug trace). |
| **Error Handling** | Automatic retries, rate-limit back-off, and per-record error reporting. |

---

## Prerequisites

- **Python 3.10+**
- A Cloudflare **API Token** for the source account with at least **read** permissions on:
  - Zone / Zone Settings
  - DNS
  - Firewall Services
  - Page Rules
  - Load Balancers
- A Cloudflare **API Token** for the destination account with **read + write** permissions on the same scopes.

> **Tip:** Use the [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens) page to create scoped tokens.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/<your-org>/cf-migrator-tool.git
cd cf-migrator-tool

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install the CLI tool (editable mode for development)
pip install -e .
```

---

## Configuration

Copy the example `.env` file and fill in your tokens:

```bash
cp .env.example .env
```

```dotenv
# Source Cloudflare account (export from)
CF_SOURCE_API_TOKEN=your_source_api_token_here
CF_SOURCE_ACCOUNT_ID=your_source_account_id_here

# Destination Cloudflare account (import to)
CF_DEST_API_TOKEN=your_destination_api_token_here
CF_DEST_ACCOUNT_ID=your_destination_account_id_here
```

Environment variables can also be passed directly via CLI flags (`--api-token`, `--account-id`).

---

## Usage

### 1. Export

```bash
# Export ALL zones and ALL resource types (interactive if --all-zones omitted)
cf-migrator export --all-zones

# Export specific zones
cf-migrator export --zones example.com --zones example.org

# Export only DNS and cache for one zone
cf-migrator export --zones example.com --resources dns --resources cache

# Override tokens via CLI flags
cf-migrator export \
  --api-token <TOKEN> \
  --account-id <ACCOUNT_ID> \
  --all-zones \
  --output-dir ./my-exports
```

The export creates a timestamped JSON file in the `exports/` directory (default).

### 2. Preview / Dry Run

Before importing, review what would change:

```bash
# Quick preview
cf-migrator preview exports/cf_export_20260302_150000.json

# Preview only specific zones
cf-migrator preview exports/cf_export_20260302_150000.json --zones example.com

# Dry run through the import command
cf-migrator import exports/cf_export_20260302_150000.json --dry-run
```

### 3. Import

```bash
# Import with confirmation prompt (shows preview first)
cf-migrator import exports/cf_export_20260302_150000.json

# Import specific zones, skip confirmation
cf-migrator import exports/cf_export_20260302_150000.json \
  --zones example.com --yes

# Override destination credentials
cf-migrator import exports/cf_export_20260302_150000.json \
  --api-token <DEST_TOKEN> \
  --account-id <DEST_ACCOUNT_ID>
```

> **Important:** Target zones must already exist in the destination account. The importer matches zones **by name**.

### 4. Audit Log

Inspect any audit log:

```bash
cf-migrator audit audit/audit_20260302_150000.json
```

---

## CLI Reference

```
Usage: cf-migrator [OPTIONS] COMMAND [ARGS]...

Commands:
  export   Export zone configurations from a Cloudflare account.
  preview  Preview the contents of an export file.
  import   Import configurations into a destination account.
  audit    Display a formatted view of an audit log file.

Global Options:
  --version  Show the version and exit.
  --help     Show this message and exit.
```

### `export` Options

| Flag | Env Var | Description |
|---|---|---|
| `--api-token` | `CF_SOURCE_API_TOKEN` | Source API token (required). |
| `--account-id` | `CF_SOURCE_ACCOUNT_ID` | Source account ID (required). |
| `--all-zones` | — | Export every zone without prompting. |
| `--zones` | — | Specific zone name(s), repeatable. |
| `--resources` | — | Resource types to export (`dns`, `waf`, `rules`, `load_balancers`, `cache`). Repeatable. Default: all. |
| `--output-dir` | — | Output directory (default: `exports`). |
| `--log-level` | — | `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |

### `import` Options

| Flag | Env Var | Description |
|---|---|---|
| `--api-token` | `CF_DEST_API_TOKEN` | Destination API token (required). |
| `--account-id` | `CF_DEST_ACCOUNT_ID` | Destination account ID (required). |
| `--zones` | — | Limit import to specific zone name(s). |
| `--dry-run` | — | Preview only, no API calls. |
| `--yes` | — | Skip interactive confirmation. |
| `--log-level` | — | Logging level. |

---

## Project Structure

```
cf-migrator-tool/
├── cf_migrator/
│   ├── __init__.py            # Package version
│   ├── cli.py                 # Click CLI entry point
│   ├── api_client.py          # Cloudflare REST client (retries, rate limits)
│   ├── logger.py              # Dual file + console logging setup
│   ├── audit.py               # JSON audit trail
│   ├── zone_selector.py       # Interactive / programmatic zone selection
│   ├── exporter.py            # Top-level export orchestrator
│   ├── importer.py            # Import engine with preview & commit
│   └── exporters/
│       ├── __init__.py
│       ├── dns.py             # DNS record exporter
│       ├── waf.py             # WAF / firewall rule exporter
│       ├── rules.py           # Page Rules, Transform, Redirect, etc.
│       ├── load_balancers.py  # LB, pools, monitors exporter
│       └── cache.py           # Cache settings exporter
├── .env.example               # Template for environment variables
├── .gitignore
├── requirements.txt
├── setup.py
└── README.md
```

---

## Export File Format

The JSON export is structured as:

```json
{
  "metadata": {
    "exported_at": "2026-03-02T21:00:00+00:00",
    "source_account_id": "abc123",
    "zone_count": 2,
    "resource_types": ["cache", "dns", "load_balancers", "rules", "waf"]
  },
  "zones": {
    "example.com": {
      "zone_id": "...",
      "zone_name": "example.com",
      "status": "active",
      "plan": "Pro",
      "dns_records": [ ... ],
      "waf": { "firewall_rules": [...], "waf_packages": [...], "custom_rulesets": [...] },
      "rules": { "page_rules": [...], "transform_rules": [...], ... },
      "load_balancers": { "load_balancers": [...], "pools": [...], "monitors": [...] },
      "cache": { "zone_cache_settings": [...], "cache_rules": [...], "tiered_caching": {...} }
    }
  }
}
```

---

## Logging

- **Console:** Timestamps + level + message (human-readable).
- **File:** Full detail including module, function, and line number. Stored in `logs/` with a timestamped filename.

Set the level with `--log-level DEBUG` for maximum verbosity.

---

## Audit Trail

Every export and import action is recorded:

```json
{
  "timestamp": "2026-03-02T21:00:00+00:00",
  "action": "export",
  "resource_type": "dns",
  "zone": "example.com",
  "status": "success",
  "detail": "Exported 42 DNS records"
}
```

Audit files are saved to `audit/` and can be viewed with:

```bash
cf-migrator audit audit/audit_20260302_150000.json
```

---

## Error Handling

- **Automatic retries** (3 attempts with exponential back-off) for transient network errors.
- **Rate-limit detection** — sleeps and retries on HTTP 429.
- **Per-record error reporting** — a single failed DNS record does not abort the entire import.
- **Token verification** — tokens are validated before any work begins.
- **Graceful degradation** — if a resource type is unavailable on the current plan, it is skipped with a log entry.

---

## Security

- **Never commit `.env`** — it is listed in `.gitignore`.
- Use **scoped API tokens** with the minimum required permissions.
- Export files may contain sensitive data (e.g., origin IPs). Store and transfer them securely.

---

## Disclaimer

This software is an **independent, unofficial, community-developed** utility. It is provided on an **"as-is" basis without any warranties or guarantees** of any kind, whether express or implied.

**This project is not affiliated with, endorsed by, sponsored by, or in any way officially connected to Cloudflare, Inc.** The Cloudflare name, logo, and associated trademarks are the property of Cloudflare, Inc. Their use in this project is solely for the purpose of describing the tool's functionality and does not imply any official relationship or endorsement.

This tool interacts with the publicly available [Cloudflare API](https://developers.cloudflare.com/api/) and is subject to Cloudflare's API terms of use and rate limits. Users are solely responsible for:

- Ensuring they have proper authorization to access and modify configurations in both source and destination Cloudflare accounts.
- Reviewing all exported data and previewing all changes **before** committing them to a destination account.
- Complying with Cloudflare's [Terms of Service](https://www.cloudflare.com/terms/), [Self-Serve Subscription Agreement](https://www.cloudflare.com/terms/), and any applicable Enterprise agreements.
- Any consequences resulting from the use or misuse of this tool, including but not limited to service disruptions, data loss, or security incidents.

**For official Cloudflare migration guidance and support, please contact [Cloudflare Support](https://support.cloudflare.com/) or your designated Cloudflare account team.**

The authors and contributors of this project accept **no liability** for damages, losses, or service disruptions arising from its use.

---

## License

MIT
