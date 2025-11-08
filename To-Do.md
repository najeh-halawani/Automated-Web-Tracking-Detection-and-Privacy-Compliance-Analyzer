# Group Work Plan – Online Tracking and Privacy Automation

- **Repository:** `najeh-halawani/Online-Tracking-and-Privacy-Automation`
- **Assignment reference:** `OTP-25-Assignment-2.pdf` (v0.1, 8 pages)
- **Last update:** 2025-11-08 18:45 UTC

---

## Team Coordination

| Role / Focus | Primary owner | Backup | Notes |
| --- | --- | --- | --- |
| Crawler implementation (Playwright scripting) | _(name)_ | _(name)_ | Owns `crawl.py`, consent logic, timings, block mode |
| Data engineering (HAR ➜ structured dataset) | _(name)_ | _(name)_ | Designs export pipeline, validates data completeness |
| Analysis & visualization | _(name)_ | _(name)_ | Maintains `analysis/`, notebooks, plots, tables |
| Reporting & QA | _(name)_ | _(name)_ | Compiles `report.pdf`, proofreading, consistency checks |

> Fill in names once the team is confirmed; revisit ownership weekly.

---

## Milestones (proposed)

- **31 Oct 2025** – Group formation deadline (complete ✔️)
- **11 Nov 2025** – Crawler runs all three modes on 5 sites without critical failures
- **13 Nov 2025** – Consolidated dataset (`results.json` + metadata) ready for analysis
- **15 Nov 2025** – First draft of figures/tables for questions 1–10
- **17 Nov 2025** – Full report v0.9 + peer review
- **18 Nov 2025 23:59 CET** – Final submission (zip structured per PDF)

Adapt dates if progress shifts. Hold a 10-minute daily stand-up during the final week.

---

## Implementation Workstreams

### A. Repository & environment

- [ ] Create / update `requirements.txt` (Playwright, pandas, PyPDF2, dnspython, seaborn, etc.)
- [ ] Document setup in `crawler_src/README.md`
- [ ] Normalize `utils.setup_logging`: fix `crawl_data_block ` (trailing space)
- [ ] Add helper scripts in `crawler_src/` for batch runs (optional)
- [x] Configure `.gitignore` (HAR, screenshots, `.pdf`, `__pycache__`)

### B. Crawler (`crawl.py` + `runs.py`)

- [x] Baseline CLI with `-m` and `-l`
- [ ] Adjust waits to assignment requirements (10s → consent → 5s → scroll → 5s)
- [ ] Implement `run_reject` with multi-step flow (customize → save/reject all)
- [ ] Implement `run_block` reusing accept flow and blocking domains (Advertising, Analytics, Social, FingerprintingInvasive, FingerprintingGeneral) using `disconnect_blocklist.json`
- [ ] Integrate blocklist via Playwright `route.fulfill`/`route.abort`
- [ ] Add retries and per-domain failure tracking (log + summary CSV)
- [ ] Validate capture outputs: HAR, pre/post screenshots, visit video
- [ ] Record per-visit metadata (timestamps, initial HTTP status, consent result)

### C. Consent & interaction (`cookie_consent_handler.py`, `utils.py`)

- [x] Detect and accept consent banners (accept mode)
- [ ] Add support for "Reject", "Essentials", "Save preferences" buttons
- [ ] Handle dialogs across multiple iframes and two-step flows
- [ ] Extend `words.json` with missing languages (e.g., German, Italian)
- [ ] Implement keyboard fallback when buttons are not visible (accessibility)

### D. Structured data export

- [x] Design `results.json` schema (per crawl, per site): requests, headers, cookies, redirects, errors
- [x] Build HAR ➜ JSONL converter (`har_to_results.py`)
- [ ] Enrich records with country (`site_list.csv`) and crawl mode (verify mapping for all domains)
- [ ] Add Disconnect entity metadata & third-party stats QA assertions
- [ ] Validate dataset size/results (sample QA scripts)
- [ ] Generate checksum/file index for integrity control

### E. Run automation

- [ ] Create batch runner (`runs.py` or separate CLI) for sequential modes
- [ ] Add `--dry-run` flag for quick tests (limit 3 sites)
- [ ] Produce compact per-domain logging (`logs/summary.csv`)

---

## Analysis Checklist (per PDF)

| # | Task | Required data | Status | Owner |
| --- | --- | --- | --- | --- |
| 1 | Boxplots per crawl: total requests, third-party requests, third-party domains, entities | Consolidated dataset + Disconnect mapping | [ ] | |
| 2 | Comparison table Accept/Reject/Block (min/median/max for metrics 1a–d) | Same as #1 | [ ] | |
| 3a | Bar chart: sites sending Advertising-category requests (by crawl) | Requests + Disconnect categories | [ ] | |
| 3b | Bar chart: sites sending Analytics-category requests (by crawl) | Requests + Disconnect categories | [ ] | |
| 4 | Table US vs Europe (Accept crawl, metrics 1a–d) | Dataset + country from `site_list.csv` | [ ] | |
| 5a | Bar chart Advertising: US vs Europe (Accept crawl) | Same as #4 | [ ] | |
| 5b | Bar chart Analytics: US vs Europe (Accept crawl) | Same as #4 | [ ] | |
| 6 | Detect cookies created via `document.cookie` (Accept crawl) | HAR cookies + Set-Cookie headers | [ ] | |
| 7 | Top 10 third-party domains per crawl + Disconnect categories | Dataset + entity map | [ ] | |
| 8 | Top 10 sites by # of third-party domains (each crawl) | Dataset | [ ] | |
| 9 | Top 10 visits by distinct server IP count (all crawls) | HAR (IPs) | [ ] | |
| 10 | Permissions-Policy: disabled permissions frequency (per crawl) | Headers | [ ] | |
| 11 | Non-default Referrer-Policy counts (per crawl, by policy) | Headers | [ ] | |
| 12 | High-entropy Accept-CH hints: top 3 per crawl | Headers | [ ] | |
| 13 | Cross-entity redirects (table per crawl) | Redirect chains + entity map | [ ] | |
| 14 | CNAME cloaking detection (table per crawl) | DNS lookups + Disconnect | [ ] | |
| 15 | Qualitative summary (challenges, surprises) | Team notes | [ ] | |

Keep this table updated each sync. Link to scripts/notebooks (e.g., `analysis/q01_boxplots.ipynb`).

---

## Final deliverables

- [ ] `crawler_src/README.md` with installation/run instructions
- [ ] `analysis/` folder containing labeled scripts/notebooks (Q1, Q2, ...)
- [ ] `report.pdf` with figures/tables (clear titles and captions)
- [ ] Curated `logs/` directory (retain only relevant logs)
- [ ] Final zip following the PDF structure
- [ ] Cross-check review (QA) + submission checklist

---

## Risks & mitigation

- **HAR integrity:** run sanity checks (size, readability) before 15 Nov.
- **IP blocking:** avoid parallel runs; schedule pauses and prepare fallback IP.
- **Analysis time:** automate HAR ingestion with pandas to limit manual work.
- **External dependencies:** pin versions in `requirements.txt` and document Playwright browser install.
- **Version control:** work via feature branches, PRs, and peer reviews for major changes.

Log new risks here and assign owners.
