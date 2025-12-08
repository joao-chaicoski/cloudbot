"""
kpis.py

Compute daily KPIs (TPV) and send alerts when variations exceed thresholds.

Usage examples:
    # compute today's KPIs and print
    python kpis.py

    # compute KPIs for a specific date and send webhook if threshold exceeded
    python kpis.py --date 2025-03-22 --threshold 0.25 --webhook-url https://hooks.example.com/...

Environment variables:
    - GROQ_API_KEY (not required)
    - ALERT_WEBHOOK_URL (optional) - POSTs JSON payload when alert triggers

This module uses the local `cloudwalk.db` DuckDB created by `db/init_db.py`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Dict, Optional

import duckdb
import pandas as pd
import requests

DB_PATH = os.getenv("CLOUDWALK_DB", "cloudwalk.db")


def _get_tpv_by_date(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Return a DataFrame with columns `day_date` (date) and `tpv` (sum of amount_transacted)."""
    sql = """
    SELECT CAST(day AS DATE) AS day_date,
           SUM(amount_transacted) AS tpv
    FROM transactions
    GROUP BY day_date
    ORDER BY day_date
    """
    df = con.execute(sql).fetchdf()
    # ensure day_date is datetime.date
    df["day_date"] = pd.to_datetime(df["day_date"]).dt.date
    return df


def compute_daily_tpv_summary(target_date: Optional[dt.date] = None) -> Dict[str, object]:
    """Compute TPV and variations for target_date vs D-1, D-7, D-30.

    Returns a dictionary with keys:
      - date: target_date
      - tpv: float
      - tpv_d1, tpv_d7, tpv_d30: floats or None
      - pct_vs_d1, pct_vs_d7, pct_vs_d30: floats (fraction, e.g. 0.12 for +12%) or None
    """
    if target_date is None:
        target_date = dt.date.today()

    con = duckdb.connect(DB_PATH)
    try:
        df = _get_tpv_by_date(con)
    finally:
        con.close()

    # convert to dict for quick lookup
    tpv_map = {row["day_date"]: float(row["tpv"]) for _, row in df.iterrows()}

    def get_tpv(d: dt.date) -> Optional[float]:
        return tpv_map.get(d)

    tpv = get_tpv(target_date)
    d1 = target_date - dt.timedelta(days=1)
    d7 = target_date - dt.timedelta(days=7)
    d30 = target_date - dt.timedelta(days=30)

    tpv_d1 = get_tpv(d1)
    tpv_d7 = get_tpv(d7)
    tpv_d30 = get_tpv(d30)

    def pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
        if current is None or previous is None:
            return None
        try:
            if previous == 0:
                return None
            return (current - previous) / previous
        except Exception:
            return None

    res = {
        "date": target_date.isoformat(),
        "tpv": tpv,
        "tpv_d1": tpv_d1,
        "tpv_d7": tpv_d7,
        "tpv_d30": tpv_d30,
        "pct_vs_d1": pct_change(tpv, tpv_d1),
        "pct_vs_d7": pct_change(tpv, tpv_d7),
        "pct_vs_d30": pct_change(tpv, tpv_d30),
    }

    return res


def format_currency(x: Optional[float]) -> str:
    if x is None:
        return "N/A"
    return f"R$ {x:,.2f}"


def format_pct(x: Optional[float]) -> str:
    if x is None:
        return "N/A"
    sign = "+" if x >= 0 else ""
    return f"{sign}{x*100:.2f}%"


def build_alert_message(summary: Dict[str, object], triggers: Dict[str, float]) -> str:
    """Returns a plaintext alert message describing the KPI and which triggers fired."""
    lines = []
    date = summary["date"]
    lines.append(f"Daily TPV summary — {date}")
    lines.append("")
    lines.append(f"TPV: {format_currency(summary['tpv'])}")
    lines.append(f"vs D-1: {format_currency(summary['tpv_d1'])} ({format_pct(summary['pct_vs_d1'])})")
    lines.append(f"vs D-7: {format_currency(summary['tpv_d7'])} ({format_pct(summary['pct_vs_d7'])})")
    lines.append(f"vs D-30: {format_currency(summary['tpv_d30'])} ({format_pct(summary['pct_vs_d30'])})")
    lines.append("")
    return "\n".join(lines)


def send_webhook_alert(webhook_url: str, message: str, extra: Optional[dict] = None, verbose: bool = False):
    """POST a JSON payload to a webhook URL.

    By default returns `True` on HTTP 2xx and `False` otherwise (backwards compatible).
    If `verbose=True` the function returns a tuple `(ok, status_code, response_text_or_error)`
    which can help debugging delivery problems.
    """
    payload = {
        "text": message,
        "summary": (extra or {}),
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        ok = 200 <= resp.status_code < 300
        if verbose:
            return ok, resp.status_code, resp.text
        # print debug info when not verbose but non-2xx to help local troubleshooting
        if not ok:
            print(f"DEBUG: webhook responded with status={resp.status_code}, body={resp.text}")
        return ok
    except Exception as e:
        if verbose:
            return False, None, f"EXCEPTION: {type(e).__name__}: {e}"
        print(f"DEBUG: exception when sending webhook: {type(e).__name__}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Compute daily TPV summary and optionally alert.")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--threshold", type=float, default=0.25, help="Alert threshold (fraction), default 0.25 == 25%")
    parser.add_argument("--webhook-url", type=str, default=os.getenv("ALERT_WEBHOOK_URL"), help="Webhook URL to POST alerts")
    parser.add_argument("--dry-run", action="store_true", help="Don't send the webhook, only print results")
    parser.add_argument("--verbose", action="store_true", help="Print verbose webhook response details when sending alerts")
    args = parser.parse_args()

    if args.date:
        target = dt.date.fromisoformat(args.date)
    else:
        target = dt.date.today()

    summary = compute_daily_tpv_summary(target)

    triggers = {"d1": args.threshold, "d7": args.threshold, "d30": args.threshold}

    # Determine if any trigger fired
    fired = []
    for key in ("d1", "d7", "d30"):
        pct = summary.get(f"pct_vs_{key}")
        thr = triggers[key]
        if pct is not None and abs(pct) >= thr:
            fired.append(key)

    # Print summary
    print(json.dumps(summary, indent=2))

    if fired:
        msg = build_alert_message(summary, triggers)
        print("ALERT: triggers fired for:", fired)
        print(msg)
        if args.webhook_url and not args.dry_run:
                if args.verbose:
                    ok, status, body = send_webhook_alert(args.webhook_url, msg, extra=summary, verbose=True)
                    print("Webhook result -> ok:", ok, "status:", status)
                    print("Body:")
                    print(body)
                else:
                    ok = send_webhook_alert(args.webhook_url, msg, extra=summary)
                    print("Webhook sent:", ok)
    else:
        print("No triggers fired.")


if __name__ == "__main__":
    main()
