#!/usr/bin/env python3
"""Rebuild data/zec_flows.json — daily net creation flows for US spot Zcash ETFs.

Method
------
Grayscale publishes a daily-performance workbook per product containing shares
outstanding, NAV per share, market price and AUM for every session back to the
trust's 2021 inception. Flow is derived the same way the aggregators derive
theirs:

    flow_t = (shares_outstanding_t - shares_outstanding_t-1) * NAV_t

Only sessions from the ETF's first trade date carry a flow. Before that ZCSH was
a Reg-D trust with no redemption programme, so share changes there are private
placements, not two-way creation flow — the pre-ETF series is kept in the file
as context (`trust_era`) but excluded from every headline number.

Because Grayscale ships the full history each day, this script rebuilds the whole
series every run and is idempotent — a missed day repairs itself next run.

Share splits
------------
ZCSH ran a 3-for-1 forward split effective 30 Sep 2026. Grayscale restates the
published history, so shares and NAV are already on one basis and no artificial
flow appears. That is a property of the publisher, not a guarantee, so the script
also runs a detector: a session where shares jump by a large factor and NAV moves
by close to its inverse is a split, not a creation. Detected splits are recorded
and their flow suppressed rather than printed as a multi-hundred-million-dollar
day.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import pathlib
import sys
import time

import openpyxl
import requests

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from funds import FUNDS, LIVE, WATCH_CIKS  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "zec_flows.json"

UA = None  # see fetch_grayscale
EDGAR_UA = os.environ.get("EDGAR_UA", "Mozilla/5.0")

# A split is flagged when shares move by more than this factor either way AND
# NAV moves by close to the inverse (so AUM is roughly preserved).
SPLIT_SHARE_FACTOR = 1.5
SPLIT_PRODUCT_TOL = 0.12


def fetch_grayscale(url: str, tries: int = 6) -> "list[dict]":
    # Plain public S3, no auth and no UA needed. It does answer a spurious
    # NoSuchBucket 404 now and then — observed on identical back-to-back
    # requests — so treat any non-200 or short body as transient and retry
    # rather than failing the run.
    body = None
    last = ""
    for i in range(tries):
        try:
            r = requests.get(url, timeout=180)
            if r.status_code == 200 and len(r.content) >= 20_000:
                body = r.content
                break
            last = f"HTTP {r.status_code}, {len(r.content)} bytes"
        except Exception as e:
            last = str(e)[:160]
        time.sleep(2 * (i + 1))
    if body is None:
        raise RuntimeError(f"could not fetch {url} after {tries} tries — last: {last}")

    wb = openpyxl.load_workbook(io.BytesIO(body), data_only=True, read_only=True)
    if "Daily Performance" not in wb.sheetnames:
        raise RuntimeError(f"no 'Daily Performance' sheet; got {wb.sheetnames}")

    rows = []
    for v in wb["Daily Performance"].iter_rows(min_row=2, values_only=True):
        # Product Name, Product ID, OTC Ticker, Date, Shares, NAV, NAV 1d %, Mkt px, AUM
        if not v or len(v) < 9 or v[3] in (None, ""):
            continue
        try:
            shares, nav, aum = float(v[4]), float(v[5]), float(v[8])
        except (TypeError, ValueError):
            continue
        if not shares or not nav:
            continue
        rows.append({
            "date": str(v[3])[:10],
            "shares": shares,
            "nav": round(nav, 6),
            "market_price": float(v[7]) if v[7] not in (None, "", 0) else None,
            "net_assets": round(aum, 2),
            "nav_change_pct": float(v[6]) if v[6] not in (None, "") else None,
        })
    rows.sort(key=lambda x: x["date"])

    # Internal consistency: AUM should equal shares x NAV. If it stops holding,
    # the publisher changed something and the flow maths is no longer safe.
    bad = [r for r in rows
           if abs(r["shares"] * r["nav"] - r["net_assets"]) / max(r["net_assets"], 1) > 0.02]
    if len(bad) > len(rows) * 0.02:
        raise RuntimeError(f"AUM != shares x NAV on {len(bad)}/{len(rows)} rows — layout changed?")

    coins_per_share = None
    if "Holdings" in wb.sheetnames:
        for v in wb["Holdings"].iter_rows(min_row=2, values_only=True):
            if v and v[0] and str(v[0]).upper() == "ZEC" and v[2]:
                coins_per_share = {"zec_per_share": float(v[2]), "as_of": str(v[1])[:10]}
                break
    return rows, coins_per_share


def detect_splits(rows: "list[dict]") -> "list[dict]":
    found = []
    for a, b in zip(rows, rows[1:]):
        sr = b["shares"] / a["shares"]
        nr = b["nav"] / a["nav"]
        if (sr > SPLIT_SHARE_FACTOR or sr < 1 / SPLIT_SHARE_FACTOR) \
                and abs(sr * nr - 1) < SPLIT_PRODUCT_TOL:
            found.append({"date": b["date"], "share_ratio": round(sr, 4),
                          "nav_ratio": round(nr, 4),
                          "note": "detected in published data — flow suppressed"})
    return found


def check_edgar_listings() -> list:
    out = []
    for cik, ticker in WATCH_CIKS.items():
        try:
            j = requests.get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json",
                             headers={"User-Agent": EDGAR_UA}, timeout=60).json()
        except Exception as e:
            out.append({"ticker": ticker, "error": str(e)[:200]})
            continue
        rec = j.get("filings", {}).get("recent", {})
        forms, dates = rec.get("form", []), rec.get("filingDate", [])
        listed = any(f in ("8-A12B", "8-A12G") for f in forms)
        out.append({
            "ticker": ticker, "cik": cik, "exchanges": j.get("exchanges", []),
            "has_8a": listed,
            "latest_form": forms[0] if forms else None,
            "latest_form_date": dates[0] if dates else None,
            "action": "LISTING IMMINENT — add an adapter" if listed else "no 8-A yet",
        })
    return out


def main() -> int:
    per_fund, trust_era, coins, splits = {}, {}, {}, {}

    for f in LIVE:
        if f["adapter"] != "grayscale_xlsx":
            continue
        rows, cps = fetch_grayscale(f["source"])
        if cps:
            coins[f["ticker"]] = cps

        declared = {s["date"] for s in f.get("splits", [])}
        detected = detect_splits(rows)
        suppress = declared | {s["date"] for s in detected}
        splits[f["ticker"]] = {
            "declared": f.get("splits", []),
            "detected_in_data": detected,
            "note": ("Grayscale restates history across a split, so a declared split "
                     "normally does not appear in the data. A detected one would."),
        }

        start = f["first_trade"]
        trust_era[f["ticker"]] = [r for r in rows if r["date"] < start]
        series = [dict(r) for r in rows if r["date"] >= start]
        prev = None
        for i, rec in enumerate(series):
            if i == 0:
                # Conversion day: the trust's existing assets are not a creation.
                rec["flow"] = 0.0
                rec["conversion"] = True
            elif rec["date"] in suppress:
                rec["flow"] = 0.0
                rec["split_adjusted"] = True
            else:
                rec["flow"] = round((rec["shares"] - prev["shares"]) * rec["nav"], 2)
            prev = rec
        per_fund[f["ticker"]] = series
        print(f"{f['ticker']}: {len(series)} ETF sessions from {start}, "
              f"{len(trust_era[f['ticker']])} trust-era sessions before it")

    dates = sorted({r["date"] for s in per_fund.values() for r in s})
    series, cum = [], 0.0
    for d in dates:
        row = {"date": d, "by_fund": {}, "flow": 0.0, "net_assets": 0.0}
        for tk, s in per_fund.items():
            m = next((x for x in s if x["date"] == d), None)
            if not m:
                continue
            row["by_fund"][tk] = m
            row["flow"] += m["flow"]
            row["net_assets"] += m["net_assets"]
        cum += row["flow"]
        row.update(flow=round(row["flow"], 2), net_assets=round(row["net_assets"], 2),
                   cum_flow=round(cum, 2))
        series.append(row)

    payload = {
        "asset": "ZEC",
        "asset_name": "Zcash",
        "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "method": ("flow = change in shares outstanding x NAV, per fund, per trading day, "
                   "from the ETF's first trade date; NAV and shares come from the issuer's "
                   "own daily workbook and are split-restated"),
        "funds": FUNDS,
        "live_tickers": sorted(per_fund),
        "coins_held": coins,
        "coins_total": ({"amount": round(sum(
                             coins[tk]["zec_per_share"] * per_fund[tk][-1]["shares"]
                             for tk in coins if per_fund.get(tk)), 4),
                         "unit": "ZEC",
                         "as_of": next(iter(coins.values()))["as_of"]} if coins else None),
        "splits": splits,
        "trust_era": {k: v[-120:] for k, v in trust_era.items()},  # tail only, for context
        "series": series,
        "listing_watch": check_edgar_listings(),
        "caveats": [
            "Flow excludes price movement. Net assets can fall hard on a zero-flow day — "
            "ZEC is the most volatile of the three assets tracked here.",
            "Conversion day carries no flow: the trust's existing assets arrived years "
            "earlier, they did not get created on 25 Aug 2026.",
            "Pre-ETF sessions are excluded from every headline number. The trust had no "
            "redemption programme, so its share changes were private placements.",
            "ZCSH ran a 3-for-1 forward split effective 30 Sep 2026. Grayscale restates "
            "the published history, so shares and NAV sit on one basis throughout.",
            "Unlike a cold-launch fund, a converted trust carries legacy holders who can "
            "finally redeem — which is why this complex prints genuine outflows.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1))
    last = series[-1]
    print(f"wrote {OUT.relative_to(ROOT)}: {len(series)} sessions through {last['date']}, "
          f"last flow ${last['flow']:,.0f}, cumulative ${last['cum_flow']:,.0f}")
    for h in payload["listing_watch"]:
        print("  watch:", h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
