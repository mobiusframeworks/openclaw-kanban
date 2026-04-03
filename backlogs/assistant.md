# Assistant Backlog

## Personal Projects

### 1. Vehicle Transition - Sell Tesla, Get Tacoma/Tundra
**Status:** TODO
**Priority:** HIGH

**Goal:** Sell 2024 Tesla Model Y, get 4x4 truck with camper for self-sufficient lifestyle

**Target Vehicles:**
| Vehicle | Spec | Years |
|---------|------|-------|
| Toyota Tacoma | 4-door (double cab), long bed, 4x4 | Any |
| Toyota Tundra | Double cab, 4x4 | 2005-2021 (NOT 2022/2023) |

**Search Regions:**
- Baja Mexico
- Los Angeles / SoCal
- San Diego
- Western USA (broader)

**Tesla Sale Tasks:**
- [ ] List Tesla Model Y 2024 for sale
- [ ] Use car-valuation dashboard to price it

**Research Tasks:**
- [ ] Research Tacoma + camper setups
- [ ] Compare: Tacoma vs Tundra vs Sprinter vs other camper 4x4 daily drivers
- [ ] Calculate payback period
- [ ] Research insurance for nomad/camper lifestyle

**Dashboard:** http://localhost:8502

---

### 1b. Daily Truck Deal Email Tool
**Status:** BACKLOG
**Priority:** HIGH
**Added:** 2026-04-03

**Goal:** Automated daily email digest with best truck deals

**Requirements:**
- Search Tacoma 4-door long bed 4x4 + Tundra double cab 4x4 (2005-2021)
- Cover: Baja Mexico, LA, San Diego, Western USA
- Daily email with:
  - Best deals found (price, mileage, condition, location)
  - Dollar-for-dollar comparison analysis
  - Why each deal stands out (value prop)
  - Comparison to camper 4x4 daily driver alternatives

**Data Sources:**
- Craigslist (LA, SD, Phoenix, Denver, etc.)
- Facebook Marketplace
- Autotrader, Cars.com, CarGurus
- MercadoLibre / Baja local listings

**Implementation:**
- [ ] Research vehicle listing APIs/scraping options
- [ ] Build price comparison model (KBB, market avg, etc.)
- [ ] Set up email delivery (SendGrid or Gmail API)
- [ ] Create daily cron job
- [ ] Add camper 4x4 alternative comparisons (Sprinter, 4Runner, etc.)

---

## Infrastructure Projects

### 2. Hermes Local LLM Agent
**Status:** TODO (was blocked, now unblocked - 5.9GB free)
**Priority:** HIGH

**Goal:** Autonomous local research agent using MLX + Qwen

**Done:**
- [x] hermes.py created at ~/hermes/
- [x] venv + dependencies installed
- [x] Obsidian indexed (304 docs)
- [x] Search working

**TODO:**
- [ ] Download Qwen 3B model
- [ ] Test chat functionality
- [ ] Set up auto-research cron jobs
- [ ] Integrate BTCautoresearch methodology
- [ ] Connect to Obsidian for knowledge storage

**Run:** `cd ~/hermes && source venv/bin/activate && python hermes.py download`

---

### 3. Disk Space Maintenance
**Status:** DONE
**Priority:** LOW

**Current:** 5.9GB free (improved from 1.4GB)
No longer blocking Hermes.

---

## Pending Items

- [ ] Google Ads MCP (waiting on credentials)
- [ ] BML blog publish (waiting on approval)

---

*Updated: 2026-04-03*
