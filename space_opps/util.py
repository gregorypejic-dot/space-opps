from __future__ import annotations

import logging
import re
import ssl
from datetime import date, datetime
from typing import Iterable, Optional

import requests
from requests.adapters import HTTPAdapter

from .config import REAL_ESTATE_SPACE, SPACE_KEYWORDS, TARGET_AGENCIES, USER_AGENT

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
        return _safe_date(m.group(1), m.group(2), m.group(3))
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if m:
        return _safe_date(m.group(3), m.group(1), m.group(2))
    return None


def _safe_date(y: str, mo: str, d: str) -> Optional[date]:
    try:
        return date(int(y), int(mo), int(d))
    except ValueError:
        return None


def matches_space(text: str, keywords: Iterable[str] = SPACE_KEYWORDS) -> list[str]:
    low = text.lower()
    hits = []
    for kw in keywords:
        tail = r"\b" if len(kw) <= 4 else ""
        if re.search(rf"\b{re.escape(kw)}{tail}", low):
            hits.append(kw)
    if hits == ["space"] and (_is_real_estate(low) or not re.search(r"\bspace(?!r\b|rs\b)", low)):
        return []
    return hits


def _is_real_estate(low: str) -> bool:
    """'space' as in office/hangar/warehouse leasing, not outer space."""
    return any(re.search(pat, low) for pat in REAL_ESTATE_SPACE)


def classify_agency(text: str) -> Optional[str]:
    low = text.lower()
    for label, needles in TARGET_AGENCIES.items():
        if any(n in low for n in needles):
            return label
    return None


class LegacyTLSAdapter(HTTPAdapter):
    """Allows RSA-key-exchange ciphers (no forward secrecy) that Python's default
    context rejects; some government hosts still negotiate only those."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


LEGACY_TLS_HOSTS = ["https://nspires.nasaprs.com"]


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})
    for host in LEGACY_TLS_HOSTS:
        s.mount(host, LegacyTLSAdapter())
    return s


def get(s: requests.Session, url: str, **kw) -> requests.Response:
    kw.setdefault("timeout", 60)
    r = s.get(url, **kw)
    r.raise_for_status()
    return r


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
