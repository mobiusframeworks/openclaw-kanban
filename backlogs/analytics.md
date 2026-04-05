---
doc_type: agent_memory
project: none
priority: 5
compression_level: L2-COOL
age_days: 5.1
tags: [agent_memory, L2-COOL]
spatial_x: 1774942480
spatial_y: 5.0
updated: 2026-04-05
---

# Analytics Agent Backlog

## Pending

- [ ] **Google Ads MCP - Complete OAuth Flow**
  - Server code: Done (`bridge/mcp/google-ads/`)
  - Library: Installed
  - Credentials in Keychain: developer_token ✓, client_id ✓, client_secret ✓
  - **Missing:** refresh_token (needs browser OAuth)
  - Run: `python mcp/google-ads/get_refresh_token.py`
  - Account: 941-733-0691
  - *Updated: 2026-03-29*

## Completed

- [x] GA4 Integration - Working (`~/dbt data basew/`)
- [x] BML GA4 tracking fix - Deployed 2026-03-29
- [x] Weekly SEO audit - Reports sent to CEOs
