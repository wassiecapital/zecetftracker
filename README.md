# zecetftracker

Daily net creation flows for US-listed **spot Zcash ETFs**, rebuilt by GitHub
Actions and served as a static page. Same architecture and design as
[`ltcetftracker`](../ltcetftracker) and [`nearetftracker`](../nearetftracker).

Live page: `https://<you>.github.io/zecetftracker/`

---

## Method

```
flow_t = (shares_outstanding_t − shares_outstanding_t−1) × NAV_t
```

Grayscale publishes a daily-performance workbook per product carrying shares
outstanding, NAV per share, market price and AUM for every session back to the
trust's 2021 inception. The script rebuilds the whole series each run, so it is
idempotent — a missed day repairs itself on the next run.

Only sessions from the **first trade date (25 Aug 2026)** carry a flow. Before
that ZCSH was a Reg-D trust with no redemption programme, so share changes were
private placements rather than two-way creation flow. Those rows are kept in the
file under `trust_era` for context and excluded from every headline number.

**Conversion day carries no flow.** The trust's assets arrived years earlier;
they were not created on day one.

## The complex, as of 8 Oct 2026

**Trading — one fund.**

| Fund | Ticker | Venue | Listed | Fee | Stakes |
|---|---|---|---|---|---|
| The Zcash ETF (Grayscale) | ZCSH | NYSE Arca | 25 Aug 2026 | 2.50% | No — Zcash is proof-of-work |

First US privacy-coin ETF. CIK 1720265. Custody with Coinbase Custody, with
Anchorage Digital added as a second custodian per the 5 Oct 2026 prospectus
supplement.

**Filed.** *Winklevoss Zcash ETF* (proposed ticker **WINK**, Nasdaq, CIK
2158471) filed its S-1 on 6 Oct 2026 — the only filing on the CIK, so no 8-A12B,
424B3, EFFECT or CERT. Proposed unified fee **0.25%**, a tenth of ZCSH's, with
Gemini as ZEC custodian. If it lists, it is the first fee competition this
complex has seen, and the listing-watch panel will flag the 8-A within a day of
it appearing.

**Deliberately excluded, so they are never miscounted:** Bitwise ZEC Strategy
ETF (CIK 1928561, 485APOS 30 Dec 2025 — a 1940-Act series, not a spot trust,
despite being tagged "spot" by some third-party trackers); Grayscale's 2x Zcash
ETF and ZCSH High Income ETF (CIK 1976672, options/futures on ZCSH, no direct
ZEC); and the 21Shares Zcash ETP on Euronext Paris/Amsterdam (ticker ZCASH,
~21 Sep 2026, 2.50%) which is not US-listed.

## The share split — why there is a detector

ZCSH ran a **3-for-1 forward split**: announced 18 Sep, record 28 Sep,
distributed 29 Sep, effective before the open on **30 Sep 2026**. A split
triples shares outstanding with zero creation flow, so a naive Δshares × NAV
model would print a spurious nine-figure inflow on that session.

Grayscale **restates** its published history across a split, so shares and NAV
sit on one basis throughout and nothing artificial reaches the series — verified
here: AUM equals shares × NAV on all 1,252 published rows, and no discontinuity
exists at the split boundary.

That is a property of the publisher, not a guarantee. So `update.py` also runs a
detector on every build: a session where shares move by more than 1.5× either
way **and** NAV moves by close to the inverse (preserving AUM) is a split, not a
creation. Anything it finds is listed on the page's **Corporate actions** panel
with its flow suppressed. The declared 30 Sep split is in `funds.py` as a
belt-and-braces second line.

## Layout

```
index.html                 the dashboard
assets/styles.css          light + dark theme tokens  (identical across all three trackers)
assets/app.js              renderer                    (identical across all three trackers)
scripts/funds.py           fund registry — add a fund here
scripts/update.py          workbook fetch + flow builder, writes data/zec_flows.json
data/zec_flows.json        the series (committed, so the page is static)
.github/workflows/update.yml   twice-daily rebuild + commit
```

## Running it locally

```bash
pip install -r requirements.txt
python scripts/update.py
python -m http.server 8000     # then open http://localhost:8000
```

## Deploying

1. Create a repo named `zecetftracker`, push to `main`.
2. Settings → Pages → Deploy from a branch, `main`, `/ (root)`.
3. Settings → Actions → General → Workflow permissions → **Read and write**.
4. Actions → *update flows* → Run workflow once. Schedule is 22:45 UTC Mon–Fri
   and 10:45 UTC Tue–Sat.

## Gotchas

- **The S3 bucket occasionally answers a spurious `NoSuchBucket` 404** on
  identical back-to-back requests. `fetch_grayscale` retries six times with
  backoff and validates the body size rather than failing the run.
- **Do not send a browser-like User-Agent to the bucket.** It is plain public
  S3; some egress paths rewrite such requests and the bucket then 404s.
- **The workbook is validated before use**: AUM must equal shares × NAV on at
  least 98% of rows, or the script raises rather than writing a wrong series.
- **Finding another Grayscale product's workbook:** the reporting bucket is
  anonymously listable —
  `https://reporting-prod-20231113144948145500000003.s3.amazonaws.com/?max-keys=1000`
  returns every `product-performance/<uuid>.xlsx` and `fact-sheet/<uuid>.pdf`.
  Match a UUID to a product by reading page 1 of its factsheet PDF. ZCSH is
  `c131f37d-6f8f-4af9-8645-346503081d6a`.
- **`data.sec.gov` 403s descriptive bot user agents** and accepts browser-like
  ones. Override with the `EDGAR_UA` env var if that flips.

## Reading the output

- **Flow excludes price**, and for ZEC price is the larger number most days. The
  *Price & fee effect* tile names that gap explicitly so you are not inferring it.
- **This is the one tracker of the three that prints real outflows.** A converted
  trust carries legacy holders who can finally redeem; a cold-launch fund like
  NRR has no equivalent seller queued up. Do not read ZCSH's redemption pattern
  across to the others.
- **Cadence beats magnitude.** Creations arrive in baskets, so a zero day means
  no basket cleared, not that demand vanished. The *Sessions since a print* tile
  and the 10-session average line on the flow chart are the cadence read.

Sources: Grayscale's published ZCSH daily-performance workbook ·
[ZCSH 424B3, 25 Aug 2026](https://www.sec.gov/Archives/edgar/data/0001720265/000119312526364568/zcsh__424b3_08.25.2026.htm) ·
[8-K confirming the 25 Aug first trade](https://www.sec.gov/Archives/edgar/data/0001720265/000119312526385317/zcsh-ex99_1.htm) ·
[8-K confirming the 3-for-1 split effective 30 Sep](https://www.sec.gov/Archives/edgar/data/0001720265/000119312526408382/zcsh-ex99_1.htm) ·
[Winklevoss Zcash ETF S-1](https://www.sec.gov/Archives/edgar/data/0002158471/000110465926113940/tm2626975-1_s1.htm) ·
[SEC EDGAR submissions API](https://data.sec.gov/submissions/CIK0001720265.json)

Not investment advice. Verify against the issuer before citing.
