"""SAM.gov Contract Opportunities via the public Get Opportunities API v2.

Requires SAM_API_KEY (free; generate under Account Details on sam.gov).
Docs: https://open.gsa.gov/api/get-opportunities-public-api/
"""
from __future__ import annotations

import os
import time
from datetime import date, timedelta

import requests

from ..config import ALWAYS_KEEP_AGENCIES, SPACE_KEYWORDS
from ..models import Opportunity
from ..summarize import sam_summary
from ..util import classify_agency, log, matches_space, parse_date

NAME = "sam.gov"
API = "https://api.sam.gov/opportunities/v2/search"
PAGE = 1000
MAX_429_RETRIES = 3

# Notice types: o=solicitation, p=presolicitation, r=sources sought, k=combined synopsis,
# s=special notice, i=intent to bundle, a=award. We skip awards.
PTYPES = "o,p,r,k,s"

AGENCY_QUERIES = [
    "SPACE FORCE",
    "SPACE SYSTEMS COMMAND",
    "NATIONAL AERONAUTICS AND SPACE ADMINISTRATION",
    "NATIONAL RECONNAISSANCE OFFICE",
    "SPACE DEVELOPMENT AGENCY",
    "FEDERAL ACQUISITION SERVICE",  # GSA FAS incl. Assisted Acquisition Services / FEDSIM
]

TITLE_QUERIES = ["space", "satellite", "launch", "orbit", "spacecraft", "lunar", "missile warning"]


def _paged(s: requests.Session, params: dict) -> list[dict]:
    out: list[dict] = []
    offset = 0
    throttled = 0
    while True:
        p = dict(params, limit=PAGE, offset=offset)
        r = s.get(API, params=p, timeout=90)
        if r.status_code == 429:
            if "quota" in r.text.lower():
                raise RuntimeError(f"sam.gov daily API quota exhausted: {r.text[:200]}")
            throttled += 1
            if throttled > MAX_429_RETRIES:
                r.raise_for_status()
            log.warning("sam.gov rate limited; sleeping 30s")
            time.sleep(30)
            continue
        r.raise_for_status()
        data = r.json()
        rows = data.get("opportunitiesData", [])
        out.extend(rows)
        total = int(data.get("totalRecords", 0))
        offset += PAGE
        if offset >= total or not rows:
            return out


def _to_opp(row: dict) -> Opportunity:
    path = row.get("fullParentPathName") or row.get("department") or ""
    agency = classify_agency(path) or path.split(".")[0]
    office = row.get("officeAddress") or {}
    desc = f"{path} | NAICS {row.get('naicsCode', '')} | PSC {row.get('classificationCode', '')} | " \
           f"set-aside: {row.get('typeOfSetAsideDescription') or 'none'} | " \
           f"{office.get('city', '')}, {office.get('state', '')}"
    return Opportunity(
        source=NAME,
        title=row.get("title", "").strip(),
        url=row.get("uiLink") or f"https://sam.gov/opp/{row.get('noticeId')}/view",
        agency=agency,
        notice_id=row.get("noticeId", "") or row.get("solicitationNumber", ""),
        notice_type=row.get("type", ""),
        posted=parse_date(row.get("postedDate")),
        deadline=parse_date(row.get("responseDeadLine")),
        description=desc,
        summary=sam_summary(row),
    )


def fetch(s: requests.Session, since: date) -> list[Opportunity]:
    key = os.environ.get("SAM_API_KEY")
    if not key:
        raise RuntimeError("SAM_API_KEY not set")
    base = {
        "api_key": key,
        "postedFrom": since.strftime("%m/%d/%Y"),
        "postedTo": (date.today() + timedelta(days=1)).strftime("%m/%d/%Y"),
        "ptype": PTYPES,
    }
    seen: dict[str, Opportunity] = {}

    for org in AGENCY_QUERIES:
        try:
            rows = _paged(s, dict(base, organizationName=org))
        except requests.HTTPError as e:
            log.warning("sam.gov org query %r failed: %s", org, e)
            continue
        for row in rows:
            opp = _to_opp(row)
            text = f"{opp.title} {opp.description}"
            hits = matches_space(text, SPACE_KEYWORDS)
            if opp.agency in ALWAYS_KEEP_AGENCIES or hits:
                opp.tags = hits
                seen[opp.notice_id] = opp

    for word in TITLE_QUERIES:
        try:
            rows = _paged(s, dict(base, title=word))
        except requests.HTTPError as e:
            log.warning("sam.gov title query %r failed: %s", word, e)
            continue
        for row in rows:
            opp = _to_opp(row)
            if opp.notice_id in seen:
                continue
            opp.tags = matches_space(f"{opp.title} {opp.description}")
            seen[opp.notice_id] = opp

    return list(seen.values())
