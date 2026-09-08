from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Iterable, Optional

import requests

from .config import SPACE_KEYWORDS, TARGET_AGENCIES, USER_AGENT

log = logging.getLogger("space_opps")

_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%Y %H:%M:%S",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%d %B %Y",
]


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+0000"
    value = re.sub(r"([+-]\d\d):(\d\d)$", r"\1\2", value)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if m:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    return None


def matches_space(text: str, keywords: Iterable[str] = SPACE_KEYWORDS) -> list[str]:
    low = text.lower()
    hits = []
    for kw in keywords:
        if len(kw) <= 4:
            if re.search(rf"\b{re.escape(kw)}\b", low):
                hits.append(kw)
        elif kw in low:
            hits.append(kw)
    return hits


def classify_agency(text: str) -> Optional[str]:
    low = text.lower()
    for label, needles in TARGET_AGENCIES.items():
        if any(n in low for n in needles):
            return label
    return None


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})
    return s


def get(s: requests.Session, url: str, **kw) -> requests.Response:
    kw.setdefault("timeout", 60)
    r = s.get(url, **kw)
    r.raise_for_status()
    return r


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
