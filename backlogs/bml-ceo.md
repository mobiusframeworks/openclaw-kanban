# Bitcoin ML CEO - Backlog

## Approved Tasks (Ready to Execute)

### 1. Power Law Blog Post - Add Disclaimers
**Status:** ✅ COMPLETE (2026-03-28)
**Priority:** HIGH - Do First
**Description:** Add financial disclaimer per Gemini's technical review:
- State this is observation, not prediction
- Add "past performance ≠ future results" caveat
- Clarify limitations of mathematical models
**Result:** Disclaimers added to HTML. Live at bitcoinmachinelearning.com/blog/power-law-model.html

### 2. TradingView Interactive Charts
**Status:** APPROVED (Council Item #10)
**Priority:** HIGH
**Description:** Upgrade power law chart with interactive features:
- Zoom in/out functionality
- Click and drag to pan
- TradingView-style professional UX
**Implementation:** Use TradingView Lightweight Charts (MIT license, 40KB gzipped)
**Future:** Consider paid indicator tool once user base established

### 3. Medium & Substack Setup
**Status:** APPROVED (Council Item #11)
**Priority:** MEDIUM
**Description:**
- Create Medium publication (Bitcoin Machine Learning)
- Create Substack newsletter
- Cross-post all blog articles to both platforms
- Set canonical URLs to main site
- Build email subscriber list via Substack

### 4. Power Law Bands Visualization
**Status:** APPROVED (previous)
**Priority:** MEDIUM
**Description:** Add color-coded standard deviation bands to power law chart:
- +2σ / -2σ bands (overvalued/undervalued zones)
- Current deviation indicator
- Historical zone visualization

---

## Completed

- [x] Launch tweet thread (manual post, 2026-03-27)
- [x] Power law blog post draft
- [x] Council approval for blog (with revisions)
- [x] Council approval for TradingView charts
- [x] Council approval for Medium/Substack
- [x] Power law blog post disclaimers + published (2026-03-28)
- [x] Power law bands visualization (already in dashboard)
- [x] 200 MA statistical analysis blog post (2026-03-29)
- [x] 200 MA Twitter thread (6 tweets) drafted (2026-03-29)
- [x] Flows vs Power Law research report (2026-03-28)
- [x] Retail vs institutional ownership research (2026-03-29)

---

## Execution Order

1. **Today:** Add disclaimer to blog post, publish
2. **This week:** Set up Medium + Substack accounts
3. **This week:** Cross-post blog to Medium/Substack
4. **Next sprint:** Implement TradingView Lightweight Charts
5. **Next sprint:** Add power law bands visualization

---

---

## Research & Data Pipeline (NEW 2026-03-28)

### 5. Supply-Demand Calculator + ML Factor Scoring
**Status:** PLANNING
**Priority:** HIGH
**Spec:** `workspace/bitcoinml/research/supply-demand-calculator-spec.md`

**Data Infrastructure (FOUND):**
- X10 SQLite: `/Volumes/Crucial X10/repos/Bitcoin-Unified-Dashboard/data/bitcoin_prices.db`
- On-chain CSV: `bitcoin_live.csv` (has halving features, forward returns)
- ETF data: `etf-btc-total.csv` (Jan 2024 - Dec 2025)

**Subtasks:**
- [ ] Update X10 data to current (last: Jan 2026)
- [ ] Set up BGeometrics API (free tier: bitcoin-data.com/api/scalar.html)
- [ ] Add whale wallet count column (needs API)
- [ ] Add exchange balance column (needs API)
- [ ] Calculate ETF daily flows from holdings diff
- [ ] Run ML factor importance with flow features
- [ ] Test: do flows shorten halving cycles?

**Blocked on:**
- BGeometrics API setup
- Data refresh script

### 6. BTCautoresearch Integration
**Status:** BACKLOG
**Priority:** MEDIUM
**Repo:** https://github.com/CBaquero/BTCautoresearch

**What it does:** Autonomous model discovery - 50.5% improvement over baseline power law using mean-reversion with 180-day decay.

**Our use:** Reference for autonomous experimentation methodology. Uses only time-based features (no external data).

**Subtasks:**
- [ ] Clone repo for reference
- [ ] Analyze their walk-forward validation approach
- [ ] Compare their R² to ours
- [ ] Consider adding their mean-reversion correction

### 7. Flows vs Power Law Research Report
**Status:** ✅ COMPLETE (2026-03-28)
**File:** `knowledge/bitcoin/flows-vs-power-law.md`

**Key findings:**
- Power law at -54% deviation (near historical floor)
- ETF flows 12x mining supply
- Whale accumulation at ATH
- S2F invalidated, power law holds

---

## Notes

- Twitter API requires $100/mo Basic tier - using manual queue workflow
- All blog posts require Gemini review + Council approval
- Canonical URLs always point to bitcoinmachinelearning.com
- X10 drive has existing BTC data infrastructure - use SQLite for storage
