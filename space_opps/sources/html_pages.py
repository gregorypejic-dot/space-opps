"""Generic link scrapers for portals without an API.

Each page config lists the URL, agency label, and a CSS selector scoping the region
whose <a> links are treated as opportunities. Links are kept if they match space
keywords or, for space-only portals, always. These are best-effort: site redesigns
will silently reduce results, so main.py warns when a page yields zero links.
"""
from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from ..config import SPACE_KEYWORDS
from ..models import Opportunity
from ..util import clean, get, log, matches_space, parse_date

PAGES = [
    {
        "name": "nspires",
        "agency": "NASA",
        "url": "https://nspires.nasaprs.com/external/solicitations/solicitationsJSON.do?path=open",
        "parser": "nspires_json",
    },
    {
        "name": "nasa-sbir",
        "agency": "NASA",
        "url": "https://sbir.nasa.gov/solicitations",
        "scope": "main, #main-content, body",
        "space_only": True,
        "link_filter": "solicit",
    },
    {
        "name": "nasa-sbir-sttr-portal",
        "agency": "NASA",
        "url": "https://www.nasa.gov/sbir_sttr/",
        "scope": "main, #main, body",
        "space_only": False,
        "link_filter": None,
        "extra_keywords": ["sbir", "sttr", "solicitation", "opportunit", "phase i", "phase ii", "ignite", "topic"],
    },
    {
        "name": "ssc-front-door",
        "agency": "USSF",
        "url": "https://www.ssc.spaceforce.mil/Front-Door",
        "scope": "main, #dnn_content, body",
        "space_only": True,
        "link_filter": None,
    },
    {
        "name": "spacewerx",
        "agency": "USSF",
        "url": "https://spacewerx.us/",
        "scope": "main, body",
        "space_only": False,
        "link_filter": None,
        "extra_keywords": ["challenge", "open topic", "sbir", "sttr", "prime", "solicitation", "call"],
    },
    {
        "name": "sda",
        "agency": "SDA",
        "url": "https://www.sda.mil/opportunities/",
        "scope": "main, article, body",
        "space_only": True,
        "link_filter": None,
    },
    {
        "name": "diu",
        "agency": "DIU",
        "url": "https://www.diu.mil/work-with-us/open-solicitations",
        "scope": "main, body",
        "space_only": False,
        "link_filter": "submit-solution",
    },
    {
        "name": "dod-sbir",
        "agency": "DOD",
        "url": "https://www.dodsbirsttr.mil/topics-app/",
        "scope": "body",
        "space_only": False,
        "link_filter": None,
    },
    {
        "name": "nstxl-spec",
        "agency": "USSF",
        "url": "https://nstxl.org/nstxl-opportunities/",
        "scope": "main, #content, body",
        "space_only": False,
        "link_filter": None,
        "extra_keywords": ["spec", "rfp", "rwp", "rfs", "rfi", "solicitation", "industry day", "opportunit"],
    },
    {
        "name": "gsa-aas",
        "agency": "GSA-AAS",
        "url": "https://www.gsa.gov/assisted-acquisition-services/industry",
        "scope": "main, body",
        "space_only": False,
        "link_filter": None,
        "extra_keywords": ["opportunit", "forecast", "solicitation", "industry day", "rfi", "rfq", "rfp", "dashboard", "interact"],
    },
]

NAV_NOISE = {"home", "about", "contact", "login", "log in", "sign in", "privacy", "accessibility",
             "faq", "faqs", "search", "menu", "skip to main content", "back to top", "careers", "news"}


NSPIRES_SUMMARY = "https://nspires.nasaprs.com/external/solicitations/summary!init.do?solId={sid}&path=open"


def _scrape_nspires_json(s: requests.Session, page: dict, since: date) -> list[Opportunity]:
    """NSPIRES renders its open-solicitations table client-side from a DataTables JSON feed.
    Keeps solicitations released in the window or with a proposal deadline in the next 30 days."""
    rows = get(s, page["url"]).json().get("aaData", [])
    horizon = date.today() + timedelta(days=30)
    out = []
    for row in rows:
        released = parse_date(row.get("release_date"))
        due = parse_date(row.get("proposal_due")) or parse_date(row.get("noi_due"))
        recent = released is not None and released >= since
        closing = due is not None and since <= due <= horizon
        if not (recent or closing):
            continue
        sid = row.get("sId", "")
        number = clean(row.get("solicitation_number", ""))
        out.append(Opportunity(
            source=page["name"],
            title=clean(row.get("title", ""))[:200],
            url=NSPIRES_SUMMARY.format(sid=quote(sid, safe="")),
            agency=page["agency"],
            notice_id=number or sid,
            notice_type=clean(row.get("announcement_type", "")),
            posted=released,
            deadline=due,
            description=f"{number} — status: {clean(row.get('status', ''))}",
            tags=matches_space(row.get("title", "")),
        ))
    return out


def _scrape(s: requests.Session, page: dict, since: date) -> list[Opportunity]:
    if page.get("parser") == "nspires_json":
        return _scrape_nspires_json(s, page, since)
    r = get(s, page["url"])
    soup = BeautifulSoup(r.text, "html.parser")
    scope = None
    for sel in page["scope"].split(","):
        scope = soup.select_one(sel.strip())
        if scope:
            break
    scope = scope or soup
    out: dict[str, Opportunity] = {}
    keywords = SPACE_KEYWORDS + page.get("extra_keywords", [])

    for a in scope.find_all("a", href=True):
        text = clean(a.get_text(" "))
        href = a["href"].strip()
        if not text or len(text) < 8 or text.lower() in NAV_NOISE:
            continue
        if href.startswith(("#", "mailto:", "javascript:")):
            continue
        url = urljoin(page["url"], href)
        if page.get("link_filter") and page["link_filter"] not in url.lower() and page["link_filter"] not in text.lower():
            continue
        hits = matches_space(text, keywords)
        if not page["space_only"] and not hits:
            continue
        # try to pick up a date in the surrounding row/list item
        container = a.find_parent(["tr", "li", "article", "div"])
        ctx = clean(container.get_text(" ")) if container else text
        posted = None
        for token in ctx.split("  "):
            posted = parse_date(token)
            if posted:
                break
        if url in out:
            continue
        out[url] = Opportunity(
            source=page["name"],
            title=text[:200],
            url=url,
            agency=page["agency"],
            notice_id=url,
            posted=posted,
            description=ctx[:300] if ctx != text else "",
            tags=hits,
        )
    return list(out.values())


def fetch_all(s: requests.Session, since: date, only: set[str] | None = None) -> dict[str, list[Opportunity] | None]:
    """Returns name -> opportunities, or None when the fetch itself failed."""
    results: dict[str, list[Opportunity] | None] = {}
    for page in PAGES:
        if only and page["name"] not in only:
            continue
        try:
            opps = _scrape(s, page, since)
        except (requests.RequestException, ValueError) as e:
            log.warning("%s: fetch failed: %s", page["name"], e)
            results[page["name"]] = None
            continue
        if not opps:
            log.warning("%s: page parsed but yielded 0 links (site layout may have changed)", page["name"])
        results[page["name"]] = opps
    return results
