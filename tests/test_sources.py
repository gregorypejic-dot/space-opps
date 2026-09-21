import json
import re
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from space_opps import publish
from space_opps.sources import html_pages
from space_opps.util import matches_space, parse_date

NSPIRES_PAGE = next(p for p in html_pages.PAGES if p["name"] == "nspires")


def _nspires(monkeypatch, rows, since):
    class R:
        def json(self):
            return {"aaData": rows}

    monkeypatch.setattr(html_pages, "get", lambda s, url: R())
    return html_pages._scrape(None, NSPIRES_PAGE, since)


def test_nspires_row_to_opportunity(monkeypatch):
    row = {
        "title": "Early Stage Innovations (ESI26)",
        "solicitation_number": "NNH26ZOA001N-ESI26",
        "release_date": "2026-09-15",
        "proposal_due": "2026-10-13",
        "status": "Open",
        "sId": "{6C484060-6A93-367A-DBC6-394F5FA30B96}",
        "announcement_type": "NRA",
    }
    (opp,) = _nspires(monkeypatch, [row], date(2026, 9, 13))
    assert opp.source == "nspires" and opp.agency == "NASA"
    assert opp.notice_id == "NNH26ZOA001N-ESI26"
    assert opp.posted == date(2026, 9, 15) and opp.deadline == date(2026, 10, 13)
    assert opp.url == (
        "https://nspires.nasaprs.com/external/solicitations/summary!init.do"
        "?solId=%7B6C484060-6A93-367A-DBC6-394F5FA30B96%7D&path=open"
    )


def test_nspires_window_rule(monkeypatch):
    since = date.today() - timedelta(days=8)
    soon = (date.today() + timedelta(days=10)).isoformat()
    rows = [
        {"title": "In window", "sId": "{1}", "solicitation_number": "A", "release_date": since.isoformat()},
        {"title": "Old but closing", "sId": "{2}", "solicitation_number": "B",
         "release_date": "2012-01-01", "proposal_due": soon},
        {"title": "Old, far deadline", "sId": "{3}", "solicitation_number": "C",
         "release_date": "2025-01-01", "proposal_due": "2027-06-01"},
        {"title": "No dates", "sId": "{4}", "solicitation_number": "D"},
    ]
    got = _nspires(monkeypatch, rows, since)
    assert sorted(o.notice_id for o in got) == ["A", "B"]


def test_nspires_bad_json_is_isolated(monkeypatch):
    class R:
        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(html_pages, "get", lambda s, url: R())
    results = html_pages.fetch_all(None, date(2026, 1, 1), {"nspires"})
    assert results == {"nspires": None}


def test_page_urls_are_current():
    urls = {p["name"]: p["url"] for p in html_pages.PAGES}
    assert urls["gsa-aas"] == "https://www.gsa.gov/assisted-acquisition-services/industry"
    assert urls["nstxl-spec"] == "https://info.nstxl.org/spec"
    assert urls["ssc-events"] == "https://sscfrontdoor.experience.crmforce.mil/SSCFrontDoor/s/events"
    assert urls["dtic-dod-agencies"] == "https://defenseinnovationmarketplace.dtic.mil/business-opportunities/dod-agencies/"
    assert urls["nspires"].startswith("https://nspires.nasaprs.com/external/solicitations/solicitationsJSON.do")
    assert urls["osc-news"] == "https://space.commerce.gov/feed/"
    assert urls["osc-tracss"] == "https://space.commerce.gov/traffic-coordination-system-for-space-tracss/"
    assert urls["noaa-tpo"] == "https://techpartnerships.noaa.gov/"
    assert all(u.startswith("https://") for u in urls.values())
    assert len(urls) == len(html_pages.PAGES), "duplicate source names"


def test_generic_link_text_uses_nearest_heading(monkeypatch):
    html = """
    <main>
      <h2>Space Enterprise Consortium (SpEC) GPS Gen4 Ground PTX</h2>
      <p>Details</p><a href="/gps-gen4">Register Here</a>
      <h2>Unrelated cooking class</h2><a href="/cooking">Register Now</a>
    </main>"""

    class R:
        text = html

    monkeypatch.setattr(html_pages, "get", lambda s, url: R())
    page = {"name": "t", "agency": "USSF", "url": "https://info.nstxl.org/spec", "scope": "main",
            "space_only": False, "link_filter": None, "extra_keywords": ["spec"]}
    got = html_pages._scrape(None, page, date(2026, 1, 1))
    assert [o.url for o in got] == ["https://info.nstxl.org/gps-gen4"]
    assert got[0].title.startswith("Space Enterprise Consortium (SpEC) GPS Gen4")


def test_rss_feed_keeps_recent_keyword_posts_only(monkeypatch):
    recent = (date.today() - timedelta(days=2)).strftime("%a, %d %b %Y 12:00:00 +0000")
    xml = f"""<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>OSC Seeks Proposals for Space Economy Study</title>
        <link>https://space.commerce.gov/osc-seeks-proposals/</link><pubDate>{recent}</pubDate>
        <description><![CDATA[<p>OSC requires a study of the U.S. commercial space economy.</p>]]></description></item>
      <item><title>Staff picnic photos</title><link>https://space.commerce.gov/picnic/</link>
        <pubDate>{recent}</pubDate><description>Fun was had.</description></item>
      <item><title>Old TraCSS industry day</title><link>https://space.commerce.gov/old/</link>
        <pubDate>Mon, 01 Jan 2024 00:00:00 +0000</pubDate><description>x</description></item>
      <item><title>Bad link space item</title><link>javascript:alert(1)</link><pubDate>{recent}</pubDate></item>
    </channel></rss>"""

    class R:
        content = xml.encode()

    monkeypatch.setattr(html_pages, "get", lambda s, url: R())
    page = next(p for p in html_pages.PAGES if p["name"] == "osc-news")
    got = html_pages._scrape(None, page, date.today() - timedelta(days=8))
    assert [o.url for o in got] == ["https://space.commerce.gov/osc-seeks-proposals/"]
    assert got[0].agency == "DOC-OSC" and got[0].posted == date.today() - timedelta(days=2)
    assert got[0].description == "OSC requires a study of the U.S. commercial space economy."


def test_self_item_page_reports_its_own_status_when_linkless(monkeypatch):
    class R:
        text = "<div id='content'><h1>SBIR Funding Opportunities</h1><p>*** The next NOFO opens Fall 2026. ***</p></div>"

    monkeypatch.setattr(html_pages, "get", lambda s, url: R())
    page = next(p for p in html_pages.PAGES if p["name"] == "noaa-sbir")
    (opp,) = html_pages._scrape(None, page, date(2026, 1, 1))
    assert opp.title == "SBIR Funding Opportunities" and opp.url == page["url"]
    assert "NOFO opens Fall 2026" in opp.description


def test_dtic_accordion_titles_links_by_agency_and_keeps_open_table_rows(monkeypatch):
    html = """
    <div class="sow-accordion-panel"><div class="sow-accordion-title">Missile Defense Agency (MDA)</div>
      <a href="http://www.mda.mil/business/advanced_research.html">Advanced Research BAA</a>
      <a href="https://www.fbo.gov/?id=1">Old BAA solicitation</a>
      <a href="/about">About the agency</a></div>
    <table class="tablepress"><tbody>
      <tr><td>Air Force</td><td>2019-09-27</td><td>Old BAA</td><td>2024-10-01</td><td>FA8650-19-S-1932</td></tr>
      <tr><td>Army</td><td>2026-09-01</td><td>Open BAA</td><td>2099-01-01</td><td>W56KGU-26-R-0001</td></tr>
      <tr><td>Navy</td><td>2018-14-01</td><td>Bad date</td><td>2018-99-99</td><td>N00001</td></tr>
    </tbody></table>"""

    class R:
        text = html

    monkeypatch.setattr(html_pages, "get", lambda s, url: R())
    page = next(p for p in html_pages.PAGES if p["name"] == "dtic-dod-agencies")
    got = html_pages._scrape(None, page, date(2026, 1, 1))
    assert [o.title for o in got] == ["Missile Defense Agency (MDA): Advanced Research BAA", "Army: Open BAA"]
    assert got[1].notice_id == "W56KGU-26-R-0001"
    assert got[1].url == "https://sam.gov/search/?keywords=W56KGU-26-R-0001"
    assert got[1].deadline == date(2099, 1, 1)


@pytest.mark.parametrize("title", [
    "General Services Administration (GSA) seeks to lease office space in Bismarck, ND",
    "Hangar Space in or Near Alpine, Texas",
    "USDA seeking 2,300-2,722 ABOA SF, Office/Warehouse/Scientific Support Space, in Cocoa, FL",
    "U.S. Government Space Required: Woodland, CA",
    "Confined Space Assessment - Beltsville MD",
    "53--SPACER,SLEEVE",
    "Marine Corps Cyberspace Environment (MCCE) Operational Support Services",
    "CMC Greenspace IFB",
])
def test_real_estate_and_compound_space_is_not_outer_space(title):
    assert matches_space(title) == []


@pytest.mark.parametrize("title", [
    "Industry Day: Vandenberg Space Force Base (VSFB) Spaceport of the Future",
    "ARPA-H Comprehensive Organ System Modeling in Outer Space (COSMOS)",
    "Laser Interferometer Space Antenna (LISA) Frequency Reference System",
    "Pituffik Space Base Project Delivery Method Market Research",
    "Space Systems Command leases ground station capacity for satellite downlink",
])
def test_outer_space_titles_still_match(title):
    assert "space" in matches_space(title)


def test_parse_date_rejects_impossible_dates():
    assert parse_date("2018-14-01") is None
    assert parse_date("13/45/2020") is None
    assert parse_date("2026-09-21") == date(2026, 9, 21)


def test_publish_copies_indexes_and_imports_legacy(tmp_path: Path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "digest.md").write_text(
        "# Space opportunities digest — 2026-09-28\n"
        "Window: posted since 2026-09-20. 52 total, **7 new** since last run.\n\n"
        "## Source status\n- nspires: ok (47)\n- diu: FAILED: fetch error\n"
    )
    (out / "opportunities.csv").write_text("source,title\n")
    legacy = tmp_path / "digests"
    legacy.mkdir()
    (legacy / "2026-09-21.md").write_text("# old\nWindow: posted since 2026-09-13. 168 total, **168 new** since last run.\n")
    (legacy / "2026-09-21.csv").write_text("source,title\n")
    (legacy / "notes.md").write_text("ignored: not a dated digest\n")

    docs = tmp_path / "docs"
    runs = publish.publish(out, docs, "2026-09-28", legacy)
    assert json.loads((docs / "digests" / "index.json").read_text()) == runs
    assert [r["date"] for r in runs] == ["2026-09-28", "2026-09-21"]
    assert runs[0] == {
        "date": "2026-09-28", "total": 52, "new": 7, "failed_sources": ["diu"],
        "md": "digests/2026-09-28.md", "csv": "digests/2026-09-28.csv",
    }
    assert not (docs / "digests" / "notes.md").exists()
    for r in runs:  # every indexed path must exist on disk
        assert (docs / r["md"]).exists() and (docs / r["csv"]).exists()


def test_publish_rejects_bad_date(tmp_path: Path):
    with pytest.raises(SystemExit):
        publish.publish(tmp_path, tmp_path / "docs", "../evil")


def test_index_html_reads_index_json_from_the_published_path():
    html = Path(__file__).resolve().parents[1] / "docs" / "index.html"
    text = html.read_text()
    assert 'fetch("digests/index.json"' in text
    assert (html.parent / "assets" / "cognition-lockup-black.svg").exists()
    assert BeautifulSoup(text, "html.parser").find("img", alt="Cognition") is not None


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_index_html_escapes_hrefs_exactly_once():
    html = (Path(__file__).resolve().parents[1] / "docs" / "index.html").read_text()
    script = re.search(r"<script>([\s\S]*?)</script>", html).group(1)
    fns = re.search(r"function esc[\s\S]*?\n  }\n[\s\S]*?function inline[\s\S]*?\n  }\n", script).group(0)
    js = fns + '\nprocess.stdout.write(inline("- **NEW** [A & B <x>](https://h/s?solId=%7B1%7D&path=open) — sam.gov"));'
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    assert 'href="https://h/s?solId=%7B1%7D&amp;path=open"' in out
    assert "&amp;amp;" not in out
    assert ">A &amp; B &lt;x&gt;</a>" in out


@pytest.mark.parametrize("path,label", [
    ("COMMERCE, DEPARTMENT OF.NATIONAL OCEANIC AND ATMOSPHERIC ADMINISTRATION.OFFICE OF SPACE COMMERCE", "DOC-OSC"),
    ("COMMERCE, DEPARTMENT OF.NATIONAL OCEANIC AND ATMOSPHERIC ADMINISTRATION.NESDIS", "NOAA"),
    ("COMMERCE, DEPARTMENT OF.NATIONAL OCEANIC AND ATMOSPHERIC ADMINISTRATION.NMFS", "NOAA"),
])
def test_commerce_agencies_are_classified(path, label):
    from space_opps.config import ALWAYS_KEEP_AGENCIES
    from space_opps.util import classify_agency

    assert classify_agency(path) == label
    # OSC is always in scope; the rest of NOAA (fisheries, ships, weather) needs a space keyword.
    assert (label in ALWAYS_KEEP_AGENCIES) == (label == "DOC-OSC")
