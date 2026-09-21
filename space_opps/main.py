"""CLI: scrape all sources, dedupe against state, write JSON/CSV/Markdown digest.

    python -m space_opps.main --since-days 7 --out out/
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from .models import Opportunity
from .software import software_tags
from .sources import grants_gov, html_pages, sam_gov
from .summarize import summarize
from .util import log, session

AGENCY_ORDER = ["USSF", "SDA", "NASA", "NRO", "GSA-AAS", "DIU", "MDA", "DOD"]


def collect(since: date, only: set[str] | None) -> tuple[list[Opportunity], dict[str, str]]:
    s = session()
    opps: list[Opportunity] = []
    status: dict[str, str] = {}

    if not only or "sam.gov" in only:
        try:
            got = sam_gov.fetch(s, since)
            opps += got
            status["sam.gov"] = f"ok ({len(got)})"
        except Exception as e:  # noqa: BLE001 - one source must never kill the run
            log.error("sam.gov failed: %s", e)
            status["sam.gov"] = f"FAILED: {e}"

    if not only or "grants.gov" in only:
        try:
            got = grants_gov.fetch(s, since)
            opps += got
            status["grants.gov"] = f"ok ({len(got)})"
        except Exception as e:  # noqa: BLE001
            log.error("grants.gov failed: %s", e)
            status["grants.gov"] = f"FAILED: {e}"

    page_only = {n for n in (only or set()) if n not in {"sam.gov", "grants.gov"}}
    if not only or page_only:
        for name, got in html_pages.fetch_all(s, since, page_only or None).items():
            if got is None:
                status[name] = "FAILED: fetch error"
                continue
            opps += got
            status[name] = f"ok ({len(got)})" if got else "0 results"

    for o in opps:
        o.summary = summarize(o)
        o.software = software_tags(o)
    return opps, status


def load_seen(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def write_outputs(out: Path, opps: list[Opportunity], new_keys: set[str], status: dict[str, str], since: date) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    rows = [o.to_dict() | {"new": o.key in new_keys} for o in opps]
    (out / "opportunities.json").write_text(json.dumps(rows, indent=2))
    with (out / "opportunities.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["key"])
        w.writeheader()
        w.writerows(rows)

    software = [o for o in opps if o.software]
    md = [f"# Space opportunities digest — {date.today().isoformat()}",
          f"Window: posted since {since.isoformat()}. {len(opps)} total, **{len(new_keys)} new** since last run, "
          f"**{len(software)} software-related**.", ""]
    md.append("## Source status")
    for k, v in status.items():
        md.append(f"- {k}: {v}")
    md.append("")

    def sort_key(o: Opportunity):
        return (o.key not in new_keys, o.deadline or date.max, o.title.lower())

    def bullet(o: Opportunity) -> list[str]:
        flag = ("**NEW** " if o.key in new_keys else "") + ("**SOFTWARE** " if o.software else "")
        meta = []
        if o.notice_type:
            meta.append(o.notice_type)
        if o.posted:
            meta.append(f"posted {o.posted.isoformat()}")
        if o.deadline:
            meta.append(f"due {o.deadline.isoformat()}")
        meta.append(o.source)
        lines = [f"- {flag}[{o.title}]({o.url}) — {', '.join(meta)}"]
        if o.summary:
            lines.append(f"  {o.summary}")
        if o.software:
            lines.append(f"  Software: {', '.join(o.software[:4])}")
        return lines

    md.append(f"## Software-related ({len(software)})")
    md.append("Opportunities that are fundamentally software work (development, modernization, sustainment), "
              "flagged from software NAICS/PSC codes and keywords. Also marked **SOFTWARE** in the agency lists below.")
    for o in sorted(software, key=lambda o: (o.key not in new_keys, o.agency, o.deadline or date.max)):
        md += bullet(o)
    md.append("")

    by_agency: dict[str, list[Opportunity]] = {}
    for o in opps:
        by_agency.setdefault(o.agency or "Other", []).append(o)
    ordered = sorted(by_agency, key=lambda a: (AGENCY_ORDER.index(a) if a in AGENCY_ORDER else 99, a))
    for agency in ordered:
        items = sorted(by_agency[agency], key=sort_key)
        md.append(f"## {agency} ({len(items)})")
        for o in items:
            md += bullet(o)
        md.append("")
    digest = out / "digest.md"
    digest.write_text("\n".join(md))
    return digest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-days", type=int, default=7)
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--state", type=Path, default=Path("state/seen.json"))
    ap.add_argument("--sources", help="comma list, e.g. sam.gov,grants.gov,nspires")
    ap.add_argument("--no-update-state", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    since = date.today() - timedelta(days=args.since_days)
    only = set(args.sources.split(",")) if args.sources else None
    opps, status = collect(since, only)

    seen = load_seen(args.state)
    new_keys = {o.key for o in opps if o.key not in seen}
    digest = write_outputs(args.out, opps, new_keys, status, since)

    if not args.no_update_state:
        args.state.parent.mkdir(parents=True, exist_ok=True)
        for o in opps:
            seen.setdefault(o.key, {"first_seen": date.today().isoformat(), "title": o.title, "url": o.url})
        args.state.write_text(json.dumps(seen, indent=1))

    log.info("%d opportunities (%d new). Digest: %s", len(opps), len(new_keys), digest)
    failed = [k for k, v in status.items() if v.startswith("FAILED")]
    return 1 if failed and len(failed) == len(status) else 0


if __name__ == "__main__":
    sys.exit(main())
