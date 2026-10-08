"""Fund registry for the US spot Zcash ETF complex.

Multi-issuer by design. One fund trades today (Grayscale ZCSH); Winklevoss has
filed. Everything else that shows up in a "Zcash ETF" search is either a
1940-Act derivative product or a European ETP — both listed here so they are
never miscounted as US spot flow.

Verified 8 Oct 2026 — see README for sources.
"""

# Grayscale publishes one daily-performance workbook per product, keyed by a
# product UUID, in a publicly listable S3 bucket. See README for how to find a
# new product's UUID if Grayscale launches another Zcash fund.
GRAYSCALE_BUCKET = "https://reporting-prod-20231113144948145500000003.s3.amazonaws.com"

FUNDS = [
    {
        "ticker": "ZCSH",
        "issuer": "Grayscale",
        "name": "The Zcash ETF",
        "exchange": "NYSE Arca",
        "status": "live",
        "adapter": "grayscale_xlsx",
        "fee": 0.025,
        "stakes": False,          # Zcash is proof-of-work
        "first_trade": "2026-08-25",
        "cik": "1720265",
        "product_uuid": "c131f37d-6f8f-4af9-8645-346503081d6a",
        "source": f"{GRAYSCALE_BUCKET}/product-performance/c131f37d-6f8f-4af9-8645-346503081d6a.xlsx",
        "fund_page": "https://etfs.grayscale.com/zcsh",
        # 3-for-1 forward split: announced 18 Sep, record 28 Sep, distributed
        # 29 Sep, effective before the open on 30 Sep 2026. Grayscale restates
        # the published history, so no artificial flow appears — but update.py
        # still runs a detector in case a future split is published unadjusted.
        "splits": [{"date": "2026-09-30", "ratio": 3.0, "note": "3-for-1 forward split"}],
    },
    {
        "ticker": "WINK",
        "issuer": "Winklevoss Asset Services",
        "name": "Winklevoss Zcash ETF (proposed)",
        "exchange": "Nasdaq (proposed)",
        "status": "filed_s1",
        "adapter": None,
        "fee": 0.0025,
        "stakes": False,
        "cik": "2158471",
        "note": (
            "S-1 filed 6 Oct 2026 — the only filing on the CIK. No 8-A12B, 424B3, "
            "EFFECT or CERT, so it is nowhere near trading. Proposed unified fee of "
            "0.25%, a tenth of ZCSH's, with Gemini as ZEC custodian. If it lists, it "
            "is the first fee competition this complex has seen."
        ),
    },
]

# Deliberately excluded from the flow series, listed so they are not miscounted:
#
#   Bitwise ZEC Strategy ETF — Bitwise Funds Trust (CIK 1928561), 485APOS filed
#     30 Dec 2025. A 1940-Act series, not a spot '33 Act trust; siblings in the
#     same filing hold a mix of token and derivatives. Sometimes tagged "spot"
#     by third-party trackers — that tag does not match the filing.
#   The 2x Zcash ETF and The ZCSH High Income ETF — Grayscale Funds Trust
#     (CIK 1976672), 485APOS 9 Sep and 25 Sep 2026. Options/futures on ZCSH, no
#     direct ZEC.
#   21Shares Zcash ETP (ticker ZCASH, ISIN CH1608218801) — Euronext Paris and
#     Amsterdam, trading since ~21 Sep 2026, 2.50%. Not US-listed.

LIVE = [f for f in FUNDS if f["status"] == "live"]
WATCH_CIKS = {f["cik"]: f["ticker"] for f in FUNDS if f.get("cik") and f["status"] != "live"}
