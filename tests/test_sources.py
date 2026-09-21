import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from space_opps import publish
from space_opps.sources import html_pages

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
    assert urls["nspires"].startswith("https://nspires.nasaprs.com/external/solicitations/solicitationsJSON.do")
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
