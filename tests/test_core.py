from datetime import date

from space_opps.models import Opportunity
from space_opps.sources import sam_gov
from space_opps.util import classify_agency, matches_space, parse_date


def test_parse_date_formats():
    assert parse_date("2026-09-01T10:00:00-04:00") == date(2026, 9, 1)
    assert parse_date("09/01/2026") == date(2026, 9, 1)
    assert parse_date("Sep 1, 2026") == date(2026, 9, 1)
    assert parse_date("garbage") is None
    assert parse_date(None) is None


def test_matches_space_word_boundaries():
    assert "space" in matches_space("Space Force launch support")
    assert matches_space("Geoffrey's office") == []  # 'geo' must be a whole word
    assert "leo" in matches_space("LEO constellation")


def test_classify_agency():
    assert classify_agency("DEPT OF DEFENSE.DEPT OF THE AIR FORCE.SPACE FORCE.SPACE SYSTEMS COMMAND") == "USSF"
    assert classify_agency("NATIONAL AERONAUTICS AND SPACE ADMINISTRATION.GODDARD") == "NASA"
    assert classify_agency("GENERAL SERVICES ADMINISTRATION.FEDERAL ACQUISITION SERVICE.FEDSIM") == "GSA-AAS"
    assert classify_agency("DEPT OF AGRICULTURE") is None


def test_sam_row_to_opp():
    row = {
        "noticeId": "abc123",
        "title": "Satellite Ground Station Support",
        "fullParentPathName": "DEPT OF DEFENSE.SPACE FORCE.SPACE SYSTEMS COMMAND",
        "postedDate": "2026-09-01",
        "responseDeadLine": "2026-09-30T17:00:00-04:00",
        "type": "Sources Sought",
        "naicsCode": "517410",
        "uiLink": "https://sam.gov/opp/abc123/view",
        "officeAddress": {"city": "El Segundo", "state": "CA"},
    }
    opp = sam_gov._to_opp(row)
    assert opp.agency == "USSF"
    assert opp.deadline == date(2026, 9, 30)
    assert "517410" in opp.description
    assert opp.key == Opportunity(source="sam.gov", title="x", url="y", notice_id="abc123").key
