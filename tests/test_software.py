from datetime import date

from space_opps.main import write_outputs
from space_opps.models import Opportunity
from space_opps.software import is_software, software_tags


def _opp(title, desc="", summary=""):
    return Opportunity(source="sam.gov", title=title, url="https://sam.gov/x", description=desc, summary=summary)


def test_greenfield_development_keyword():
    assert "software" in software_tags(_opp("Mission Planning Software Development"))


def test_brownfield_maintenance_and_modernization():
    assert is_software(_opp("Legacy System Modernization for GPS OCX"))
    assert is_software(_opp("Annual software maintenance and sustainment"))
    assert is_software(_opp("Ground segment DevSecOps support"))


def test_software_naics_and_psc_from_sam_description():
    tags = software_tags(_opp("Ground Segment Support", "USSF | NAICS 541511 | PSC D302 | set-aside: none | CO"))
    assert tags[0].startswith("NAICS 541511")
    assert tags[1].startswith("PSC D302")
    assert software_tags(_opp("Apps", "X | NAICS 541330 | PSC DA01 | set-aside: none | ,"))[0].startswith("PSC DA01")
    assert software_tags(_opp("Licenses", "X | NAICS 000000 | PSC 7030 | set-aside: none | ,"))[0].startswith("PSC 7030")


def test_non_software_is_not_flagged():
    for title in ["Termite Fumigation at VSFB", "Rocket propellant tank fabrication",
                  "Facility modernization of Building 12", "Chapel music services",
                  "Satellite dish hardware repair (NAICS 334220, PSC 5985)"]:
        assert not is_software(_opp(title, "USSF | NAICS 561710 | PSC S200 | set-aside: none | CA")), title


def test_digest_marks_software(tmp_path):
    sw = _opp("Flight software sustainment")
    sw.software = software_tags(sw)
    hw = _opp("Antenna hardware")
    md = write_outputs(tmp_path, [sw, hw], {sw.key}, {"sam.gov": "ok (2)"}, date(2026, 1, 1)).read_text()
    assert "**1 software-related**" in md
    assert "## Software-related (1)" in md
    assert "**NEW** **SOFTWARE** [Flight software sustainment]" in md
    assert "  Software: software, flight software, software sustainment" in md
    assert "**SOFTWARE** [Antenna hardware]" not in md
    csv_text = (tmp_path / "opportunities.csv").read_text()
    assert "is_software" in csv_text.splitlines()[0]
