"""Generic link scrapers for portals without an API.

Each page config lists the URL, agency label, and a CSS selector scoping the region
whose <a> links are treated as opportunities. Links are kept if they match space
keywords or, for space-only portals, always. These are best-effort: site redesigns
will silently reduce results, so main.py warns when a page yields zero links.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urljoin, urlparse

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
        # Salesforce Experience Cloud site: the event list is rendered client-side, so the
        # plain-HTML pass usually yields 0 results. Kept so the digest reports the gap.
        "name": "ssc-events",
        "agency": "USSF",
        "url": "https://sscfrontdoor.experience.crmforce.mil/SSCFrontDoor/s/events",
        "scope": "main, body",
        "space_only": False,
        "link_filter": None,
        "extra_keywords": ["event", "industry day", "reverse industry", "webinar", "pitch", "opportunit", "rfi", "rfp"],
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
        "url": "https://info.nstxl.org/spec",
        "scope": "main, #content, body",
        "space_only": False,
        "link_filter": None,
        "extra_keywords": ["spec", "rfp", "rwp", "rfs", "rfi", "solicitation", "industry day", "opportunit",
                           "register", "event", "summit", "gmm"],
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
    {
        "name": "dtic-dod-agencies",
        "agency": "DoD-DAFA",
        "url": "https://defenseinnovationmarketplace.dtic.mil/business-opportunities/dod-agencies/",
        "parser": "dtic_accordion",
        "extra_keywords": ["solicitation", "opportunit", "baa", "broad agency", "rfp", "rfi", "sbir", "sttr",
                           "needipedia", "innovation", "acquisition", "partnering", "doing business", "needs"],
    },
    # Department of Commerce: Office of Space Commerce (OSC) and NOAA. OSC is a WordPress site;
    # the article body is `article .entry-content`, which skips the very large site menu.
    {
        "name": "osc-doc-opportunities",
        "agency": "DOC-OSC",
        "url": "https://space.commerce.gov/links/resources-for-space-entrepreneurs/opportunities-department-of-commerce-agencies/",
        "scope": "article .entry-content, article, main",
        "space_only": False,
        "link_filter": None,
        "extra_keywords": ["tracss", "commercial data", "acquisition", "technology partnerships", "data buy"],
    },
    {
        "name": "osc-noaa-satellite-architecture",
        "agency": "NOAA",
        "url": "https://space.commerce.gov/business-with-noaa/future-noaa-satellite-architecture/",
        "scope": "article .entry-content, article, main",
        "space_only": True,
        "link_filter": None,
    },
    {
        "name": "osc-tracss",
        "agency": "DOC-OSC",
        "url": "https://space.commerce.gov/traffic-coordination-system-for-space-tracss/",
        "scope": "article .entry-content, article, main",
        "space_only": False,
        "link_filter": None,
        "extra_keywords": ["tracss", "registration", "waitlist", "forum", "specification", "dataset", "presentation",
                           "pathfinder", "user agreement", "listening session"],
    },
    {
        "name": "osc-cdp-industry-day",
        "agency": "NOAA",
        "url": "https://space.commerce.gov/commercial-data-program-industry-day-april-9/",
        "scope": "article .entry-content, article, main",
        "space_only": True,
        "link_filter": None,
    },
    {
        # OSC news feed: catches future industry days, RFIs and TraCSS calls as they are posted.
        "name": "osc-news",
        "agency": "DOC-OSC",
        "url": "https://space.commerce.gov/feed/",
        "parser": "rss",
        "extra_keywords": ["industry day", "rfi", "rfp", "solicitation", "call for", "request for", "tracss",
                           "commercial data", "waitlist", "registration", "forum", "workshop", "listening session"],
    },
    {
        "name": "noaa-tpo",
        "agency": "NOAA",
        "url": "https://techpartnerships.noaa.gov/",
        "scope": "#content, main, body",
        "space_only": False,
        "link_filter": None,
        "extra_keywords": ["funding opportunit", "sbir", "nofo", "crada", "partner with noaa"],
    },
    {
        "name": "noaa-sbir",
        "agency": "NOAA",
        "url": "https://techpartnerships.noaa.gov/sbir/fundingopportunities/",
        "scope": "#content, main, body",
        "space_only": False,
        "link_filter": None,
        "extra_keywords": ["nofo", "notice of funding", "sbir", "solicitation", "grants.gov", "phase i", "phase ii"],
        "self_item": True,  # between NOFOs the page has no links; report the page's own status text
    },
]

NAV_NOISE = {"home", "about", "contact", "login", "log in", "sign in", "privacy", "accessibility",
             "faq", "faqs", "search", "menu", "skip to main content", "back to top", "careers", "news"}

# CTA anchors whose text says nothing about the item; the nearest preceding heading is used instead.
GENERIC_LINK_TEXT = {"register here", "register now", "register", "learn more", "read more", "click here",
                     "more info", "more information", "view", "details", "apply now", "apply here", "here"}


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


def _scrape_dtic_accordion(s: requests.Session, page: dict, since: date) -> list[Opportunity]:
    """DTIC's DoD agencies page is one accordion panel per Defense Agency/Field Activity, each
    holding links to that agency's solicitation pages, plus a 'Contract Opportunities' table.
    Panel links are titled '<Agency>: <link text>'; table rows are kept only while still open."""
    soup = BeautifulSoup(get(s, page["url"]).text, "html.parser")
    keywords = SPACE_KEYWORDS + page.get("extra_keywords", [])
    out: dict[str, Opportunity] = {}
    for panel in soup.select(".sow-accordion-panel"):
        title_el = panel.select_one(".sow-accordion-title")
        agency = clean(title_el.get_text(" ")) if title_el else ""
        for a in panel.find_all("a", href=True):
            text = clean(a.get_text(" "))
            href = a["href"].strip()
            if not text or href.startswith(("#", "mailto:", "javascript:")) or href.lower().endswith(".pdf"):
                continue
            hits = matches_space(text, keywords)
            if not hits:
                continue
            url = urljoin(page["url"], href)
            if url in out or urlparse(url).netloc.endswith("fbo.gov"):  # FBO.gov retired 2019
                continue
            out[url] = Opportunity(
                source=page["name"],
                title=f"{agency}: {text}"[:200] if agency else text[:200],
                url=url,
                agency=page["agency"],
                notice_id=url,
                description=agency,
                tags=hits,
            )
    today = date.today()
    for row in soup.select("table.tablepress tbody tr"):
        cells = [clean(td.get_text(" ")) for td in row.find_all("td")]
        if len(cells) < 5:
            continue
        agency, posted, title, due, number = cells[:5]
        deadline = parse_date(due)
        if deadline is None or deadline < today:
            continue
        url = f"https://sam.gov/search/?keywords={quote(number)}"
        out[url] = Opportunity(
            source=page["name"],
            title=f"{agency}: {title}"[:200],
            url=url,
            agency=page["agency"],
            notice_id=number,
            posted=parse_date(posted),
            deadline=deadline,
            description=f"{number} — listed on DTIC Defense Innovation Marketplace",
            tags=matches_space(title, keywords),
        )
    return list(out.values())


def _scrape_rss(s: requests.Session, page: dict, since: date) -> list[Opportunity]:
    """RSS 2.0 feed (WordPress `/feed/`): one item per post, kept on a keyword hit and posted >= since."""
    r = get(s, page["url"])
    root = ET.fromstring(r.content)
    keywords = SPACE_KEYWORDS + page.get("extra_keywords", [])
    out: list[Opportunity] = []
    for item in root.iter("item"):
        title = clean(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        posted = None
        pub = item.findtext("pubDate")
        if pub:
            try:
                posted = parsedate_to_datetime(pub).date()
            except (TypeError, ValueError):
                posted = None
        if posted and posted < since:
            continue
        blurb = clean(BeautifulSoup(item.findtext("description") or "", "html.parser").get_text(" "))
        hits = matches_space(f"{title} {blurb}", keywords)
        if not hits:
            continue
        out.append(Opportunity(
            source=page["name"],
            title=title[:200],
            url=link,
            agency=page["agency"],
            notice_id=link,
            notice_type="news",
            posted=posted,
            description=blurb[:300],
            tags=hits,
        ))
    return out


def _scrape(s: requests.Session, page: dict, since: date) -> list[Opportunity]:
    if page.get("parser") == "nspires_json":
        return _scrape_nspires_json(s, page, since)
    if page.get("parser") == "dtic_accordion":
        return _scrape_dtic_accordion(s, page, since)
    if page.get("parser") == "rss":
        return _scrape_rss(s, page, since)
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
        if text.lower().rstrip(".!»") in GENERIC_LINK_TEXT:
            heading = a.find_previous(["h1", "h2", "h3", "h4", "strong"])
            heading_text = clean(heading.get_text(" ")) if heading else ""
            if len(heading_text) >= 8:
                text = f"{heading_text} ({text})"
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
    if not out and page.get("self_item"):
        heading = scope.find(["h1", "h2"]) or soup.find("title")
        out[page["url"]] = Opportunity(
            source=page["name"],
            title=(clean(heading.get_text(" ")) if heading else page["name"])[:200],
            url=page["url"],
            agency=page["agency"],
            notice_id=page["url"],
            description=clean(scope.get_text(" "))[:300],
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
