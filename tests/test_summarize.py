from space_opps.models import Opportunity
from space_opps.summarize import MAX_LEN, sam_summary, summarize


def _sam_row(**over):
    row = {
        "type": "Sources Sought",
        "fullParentPathName": "DEPT OF DEFENSE.DEPT OF THE AIR FORCE.SPACE SYSTEMS COMMAND.FA8819 SDA AND COMBAT POWER SZK-LA",
        "naicsCode": "541715",
        "classificationCode": "1810",
        "typeOfSetAsideDescription": "No Set aside used",
        "officeAddress": {"city": "EL SEGUNDO", "state": "CA"},
    }
    row.update(over)
    return row


def test_sam_summary_uses_psc_title_office_and_place():
    s = sam_summary(_sam_row())
    assert s == "Sources-sought notice (market research) for space vehicles from SDA And Combat Power Szk-La; El Segundo, CA."


def test_sam_summary_falls_back_to_naics_and_mentions_set_aside():
    s = sam_summary(_sam_row(classificationCode="", typeOfSetAsideDescription="Small Business Set Aside - Total"))
    assert s == ("Sources-sought notice (market research) for research and development in the physical, "
                 "engineering, and life sciences from SDA And Combat Power Szk-La; small business set aside - "
                 "total; El Segundo, CA.")


def test_sam_summary_handles_unknown_codes():
    s = sam_summary(_sam_row(classificationCode="ZZZZ", naicsCode="000000", type="Solicitation"))
    assert s.startswith("Solicitation for goods or services from")


def test_nspires_summary_from_type_and_number():
    o = Opportunity(source="nspires", title="A.17 Hydrosphere", url="u", notice_type="NRA",
                    description="NNH25ZDA001N-HYDRO — status: Due in 30 Days")
    assert summarize(o) == "NASA research announcement NNH25ZDA001N-HYDRO open for proposals on NSPIRES."


def test_html_summary_skips_title_echo_and_date_lines():
    o = Opportunity(source="sda", title="SDA Requests Proposals for RMWT Ground Entry Points", url="u",
                    description="SDA Requests Proposals for RMWT Ground Entry Points Posted On: September 18, 2026 "
                                "Responses Due: November 2, 2026. SDA seeks proposals for ground entry points that "
                                "downlink missile warning data from LEO satellites.")
    assert summarize(o) == ("SDA seeks proposals for ground entry points that downlink missile warning data from "
                            "LEO satellites.")


def test_html_summary_template_when_no_prose():
    o = Opportunity(source="diu", title="CSO Space Threat Intelligence", url="u")
    assert summarize(o) == "Defense Innovation Unit commercial solutions opening."


def test_dtic_summary_names_agency():
    o = Opportunity(source="dtic-dod-agencies", title="DARPA: BAA", url="u", description="DARPA")
    assert summarize(o).startswith("Link to DARPA's solicitation/BAA page")


def test_long_summary_is_clipped_at_word_boundary():
    o = Opportunity(source="spacewerx", title="T", url="u", description="word " * 100)
    s = summarize(o)
    assert s.endswith("word…") and len(s) <= MAX_LEN + 1
