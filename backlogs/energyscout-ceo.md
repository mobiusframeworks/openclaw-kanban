# EnergyScout CEO - Backlog

## Calculator Accuracy Fixes

### 1. ITC Tax Credit Display
**Status:** DONE (Sprint 3)
**Priority:** HIGH
**Issue:** Calculator currently shows 30% ITC for all purchase types
**Fix:** Dynamic ITC rate - shows 0% for cash/loan (expired), 30% for lease

### 2. NEM 3.0 Bill Coverage Accuracy
**Status:** DONE (Sprint 3)
**Priority:** HIGH
**Issue:** Calculator shows $0 bill for 100% solar coverage with cash purchase
**Fix:** Added NEM 3.0 calculation (60% self-consumption at retail, 40% export at 25%), $15/mo minimum grid charge, and disclaimer banner for CA

### 3. Zip Code Search Bug
**Status:** DONE (Sprint 3)
**Priority:** HIGH
**Issue:** Zip search returning wrong location (95030 → Germany)
**Fix:** Added US zip code detection, forces `country: 'US'` for Nominatim searches

---

## Business Ideas

### Solar Loan + ITC Arbitrage Model
**Status:** RESEARCH
**Priority:** MEDIUM
**Added:** 2026-03-29

#### Concept Summary
A financing company that offers a **better alternative to solar leases** by combining loan ownership with ITC capture:

1. **Structure:** Company finances solar installation and initially owns the system
2. **ITC Capture:** Company claims 30% federal tax credit (still available for commercial entities)
3. **Savings Pass-through:** Lower monthly payments to homeowner (ITC benefit baked in)
4. **Ownership Path:** Homeowner pays off loan and owns system outright (unlike leases)
5. **Exit Strategy:** Sell loan portfolios to banks (like mortgage securitization)

#### Why Better Than Leases
| Factor | Lease | This Model |
|--------|-------|------------|
| Ownership | Never | Yes, after payoff |
| ITC Benefit | Captured by lessor | Passed to homeowner via lower payment |
| Lock-in | 20-25 year contract | Pay off anytime |
| Home Sale | Complicated transfer | Clean title after payoff |
| Long-term ROI | Lower | Higher |

#### Target Market
- Credit-qualified homeowners
- Good solar sites (high production potential)
- States with strong net metering or TOU rates
- Homes likely to sell within 10-15 years

#### Business Model
- Partner with local installers (white-label financing)
- Origination fee + interest spread
- Portfolio sale to banks/credit unions
- Could offer PPA hybrid ($/kWh until buyout)

#### To-Do List
- [x] Research ITC transfer rules for commercial → residential (DONE 2026-03-31)
- [x] Model financials: required spread, default risk, breakeven (DONE 2026-03-31)
- [ ] Identify regulatory requirements (lending license by state)
- [ ] Competitive analysis: Sunrun, Mosaic, GoodLeap models
- [ ] Talk to 3+ local installers about financing pain points
- [ ] Draft term sheet structure (rates, terms, buyout formula)
- [ ] Explore bank partnerships for loan sales
- [ ] Legal review: can commercial entity claim ITC then transfer system?
- [ ] Build financial calculator/underwriting model
- [ ] Identify pilot market (CA? TX? FL?)

---

## SEO / AI Visibility (energyscout.org)

### 1. Fix SPA Invisibility for AI Crawlers
**Status:** DONE (2026-04-01)
**Priority:** HIGH
**Added:** 2026-03-29

**Solution:** Implemented Vite SSG (Static Site Generation) - content now pre-renders server-side.

**Verification (2026-04-01):**
- ✅ HTML contains full content (navigation, hero, FAQ, footer)
- ✅ robots.txt allows all AI crawlers (GPTBot, ClaudeBot, PerplexityBot, etc.)
- ✅ sitemap.xml present with 11 URLs
- ✅ `__VITE_REACT_SSG_HASH__` confirms SSG active

**Note:** battery.energyscout.org (Next.js) is fine - has SSR, robots.ts, sitemap.ts

### 2. Add robots.txt to energyscout.org
**Status:** DONE (2026-03-31)
**Priority:** MEDIUM
**File:** `/workspace/scout/public/robots.txt`

### 3. Add sitemap.xml to energyscout.org
**Status:** DONE (2026-03-31)
**Priority:** MEDIUM
**File:** `/workspace/scout/public/sitemap.xml`

---

## Content Updates Needed

### 1. SGIP Waitlist Warning
**Status:** DONE (2026-03-31)
**Priority:** HIGH
**Added:** 2026-03-29

Add banner to all utility pages: SGIP is waitlisted statewide as of Dec 31, 2025.

### 2. Add RSSE AB 209 Info
**Status:** BACKLOG
**Priority:** MEDIUM

Add info about new $280M low-income program ($1,100/kWh storage) to utility pages.

### 3. Create OCPA Battery Rebate Page
**Status:** BACKLOG
**Priority:** LOW

Orange County Power Authority - deadline May 15, 2026.

### 4. Brand Tone Audit
**Status:** BACKLOG
**Priority:** MEDIUM
**Added:** 2026-03-29

Review all pages for brand compliance:
- Transparent, not clickbait
- Authoritative, cite sources
- Informative, not salesy
- Honest about limitations

---

## Approved Tasks (from Sprint 2)

- [x] SMUD FAQ page restored
- [x] Misleading copy fixed
- [x] PG&E battery rebate page
- [x] SCE battery rebate page
- [x] SDG&E battery rebate page
- [x] 3CE battery rebate page
- [x] MCE battery rebate page
- [x] EBCE battery rebate page

---

---

## Solar Loan + ITC Arbitrage (Business Idea)

### Completed Research
- [x] ITC transfer rules research (2026-03-31)
- [x] Financial model: spread, default, breakeven (2026-03-31)
- [x] Legal research: recapture rules, ownership structures (2026-03-31)

### Next Steps (Requires Human Decision)
- [ ] **Engage tax attorney** for formal ITC opinion letter ($15-30K)
- [ ] **Engage licensing attorney** for California CFL application ($10-20K)
- [ ] Identify regulatory requirements by state
- [ ] Competitive analysis: Sunrun, Mosaic, GoodLeap models
- [ ] Talk to 3+ local installers about financing pain points

*Updated: 2026-03-31*
