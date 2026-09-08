"""Grants.gov search2 API (no key required). Covers NASA grants/cooperative agreements
and space-related opportunities from other agencies."""
from __future__ import annotations

from datetime import date

import requests

from ..models import Opportunity
from ..util import log, matches_space, parse_date

NAME = "grants.gov"
API = "https://api.grants.gov/v1/api/search2"
ROWS = 500

QUERIES = [
    {"agencies": "NASA", "keyword": ""},
    {"agencies": "", "keyword": "space"},
    {"agencies": "", "keyword": "satellite"},
    {"agencies": "DOD", "keyword": "space"},
]


def fetch(s: requests.Session, since: date) -> list[Opportunity]:
    seen: dict[str, Opportunity] = {}
    for q in QUERIES:
        payload = {
            "keyword": q["keyword"],
            "agencies": q["agencies"],
            "oppStatuses": "forecasted|posted",
            "rows": ROWS,
            "startRecordNum": 0,
        }
        try:
            r = s.post(API, json=payload, timeout=60)
            r.raise_for_status()
            hits = r.json().get("data", {}).get("oppHits", [])
        except (requests.RequestException, ValueError) as e:
            log.warning("grants.gov query %r failed: %s", q, e)
            continue
        for h in hits:
            oid = str(h.get("id"))
            if oid in seen:
                continue
            posted = parse_date(h.get("openDate"))
            if posted and posted < since and (h.get("oppStatus") or "").lower() != "forecasted":
                continue
            title = h.get("title", "")
            kw = matches_space(f"{title} {h.get('agency', '')}")
            if q["agencies"] != "NASA" and not kw:
                continue
            seen[oid] = Opportunity(
                source=NAME,
                title=title,
                url=f"https://www.grants.gov/search-results-detail/{oid}",
                agency=h.get("agencyCode") or h.get("agency", ""),
                notice_id=h.get("number", oid),
                notice_type=h.get("oppStatus", ""),
                posted=posted,
                deadline=parse_date(h.get("closeDate")),
                description=h.get("agency", ""),
                tags=kw,
            )
    return list(seen.values())
