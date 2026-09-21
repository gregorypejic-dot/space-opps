"""One-sentence, plain-language summary of what each opportunity is.

Sources rarely expose a real abstract without extra API calls (SAM.gov's notice text costs one
quota-limited request per notice), so the sentence is built from whatever structured data the
listing already carries: notice type, buying office, PSC/NAICS titles, set-aside and place for
SAM.gov; the first prose sentence of the surrounding text for HTML sources; a fixed template
otherwise.
"""
from __future__ import annotations

import json
import re
from importlib import resources

from .models import Opportunity

MAX_LEN = 220

_DATA = resources.files(__package__) / "data"
NAICS_TITLES: dict[str, str] = json.loads((_DATA / "naics.json").read_text())
PSC_TITLES: dict[str, str] = json.loads((_DATA / "psc.json").read_text())

_NOTICE_TYPES = {
    "solicitation": "Solicitation",
    "combined synopsis/solicitation": "Combined synopsis/solicitation",
    "presolicitation": "Presolicitation",
    "sources sought": "Sources-sought notice (market research)",
    "special notice": "Special notice",
    "intent to bundle requirements (dod-funded)": "Intent-to-bundle notice",
}

_NSPIRES_TYPES = {
    "NRA": "NASA research announcement",
    "CAN": "NASA cooperative agreement notice",
    "AO": "NASA announcement of opportunity",
    "RFP": "NASA request for proposals",
    "RFI": "NASA request for information",
}

_SOURCE_TEMPLATES = {
    "nasa-sbir": "NASA SBIR/STTR program solicitation or announcement.",
    "nasa-sbir-sttr-portal": "Page on the NASA SBIR/STTR portal.",
    "spacewerx": "SpaceWERX (Space Force innovation arm) announcement.",
    "sda": "Space Development Agency opportunities-page item.",
    "diu": "Defense Innovation Unit commercial solutions opening.",
    "dod-sbir": "DoD SBIR/STTR topic.",
    "nstxl-spec": "Space Enterprise Consortium (NSTXL) item; full RFPs are member-only.",
    "gsa-aas": "GSA Assisted Acquisition Services industry page link.",
    "ssc-events": "Space Systems Command Front Door industry event.",
    "ssc-front-door": "Space Systems Command Front Door item.",
    "grants.gov": "Federal grant funding opportunity.",
}


def _title(code: str, table: dict[str, str]) -> str:
    name = table.get(code.strip().upper()) if code else None
    if not name:
        return ""
    name = re.sub(r"\s*\([^)]*\)", "", name)  # drop "(except …)" qualifiers
    return name.capitalize() if name.isupper() else name


def _clip(text: str, limit: int = MAX_LEN) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:—-") + "…"


def _sentence(text: str) -> str:
    if text.endswith((".", "!", "?")):
        return text
    return text + "."


def sam_summary(row: dict) -> str:
    ntype = _NOTICE_TYPES.get((row.get("type") or "").lower(), row.get("type") or "Notice")
    psc = _title(row.get("classificationCode") or "", PSC_TITLES)
    naics = _title(row.get("naicsCode") or "", NAICS_TITLES)
    path = [p.strip() for p in (row.get("fullParentPathName") or "").split(".") if p.strip()]
    office = path[-1].title() if len(path) > 1 else ""
    office = re.sub(r"^Fa\d{4}\s+", "", office)
    office = re.sub(r"\b(Ssc|Pnt|Sda|Nasa|Ussf|Cons|Pk|Peo|Hq|Sfb)\b", lambda m: m.group(0).upper(), office)
    set_aside = row.get("typeOfSetAsideDescription") or ""
    addr = row.get("officeAddress") or {}
    place = ", ".join(p for p in (addr.get("city", "").title(), addr.get("state", "")) if p)

    what = psc.lower() if psc else naics.lower() if naics else "goods or services"
    parts = [f"{ntype} for {what}"]
    if office:
        parts.append(f"from {office}")
    tail = []
    if set_aside and set_aside.lower() not in ("none", "no set aside used"):
        tail.append(set_aside.lower())
    if place:
        tail.append(place)
    text = " ".join(parts) + (f"; {'; '.join(tail)}" if tail else "")
    return _clip(_sentence(text))


def _first_prose_sentence(opp: Opportunity) -> str:
    text = re.sub(r"\s+", " ", opp.description or "").strip()
    if not text or " | " in text or " — status:" in text or " — listed on " in text:
        return ""
    title = re.sub(r"\s+", " ", opp.title).strip().lower()
    if text.lower().startswith(title):
        text = text[len(title):].lstrip(" -—:|")
    for sent in re.split(r"(?<!\bU\.S)(?<!\bU\.S\.A)(?<=[.!?])\s+", text):
        low = sent.lower()
        if len(sent) < 25 or low.startswith(title) or title.startswith(low.rstrip(".")):
            continue
        if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", sent) or re.match(r"(posted|response|offers?|due)\b", low):
            continue
        return _clip(_sentence(sent))
    return ""


def summarize(opp: Opportunity) -> str:
    if opp.summary:
        return opp.summary
    if opp.source == "nspires":
        kind = _NSPIRES_TYPES.get(opp.notice_type.upper(), "NASA solicitation")
        number = (opp.description or "").split(" — ")[0].strip()
        return _sentence(f"{kind} {number} open for proposals on NSPIRES".replace("  ", " "))
    if opp.source == "nasa-sbir":
        dates = re.findall(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", opp.description or "")
        when = f"; opens {dates[0]}, closes {dates[1]}" if len(dates) >= 2 else ""
        return f"NASA SBIR/STTR program solicitation{when}."
    if opp.source == "dtic-dod-agencies":
        agency = opp.description or "a Defense Agency"
        return f"Link to {agency}'s solicitation/BAA page, listed on the DTIC Defense Innovation Marketplace."
    prose = _first_prose_sentence(opp)
    if prose:
        return prose
    return _SOURCE_TEMPLATES.get(opp.source, f"Item found on the {opp.source} page.")
