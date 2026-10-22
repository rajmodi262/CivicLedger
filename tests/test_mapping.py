"""Unit tests for the source-to-target mapping and normalisation (UAT cases UT-01..UT-08)."""

import math

from civicledger.ingest import Mapping, column_map, norm_code, norm_text, parse_amount

MAPPING = Mapping.load()


def test_amount_column_resolved_per_year():
    # UT-01: each adopted-file layout maps its own amount column to "ordinance"
    for column in ["amount", "_ordinance_amount_", "appropriation_ordinance"]:
        _, meas = column_map(["fund_code", column], "adopted", MAPPING)
        assert meas["ordinance"] == column


def test_misspelled_prior_year_column_is_mapped():
    # UT-02: 2013-2020 proposed files spell it "appropration"
    _, meas = column_map(["appropration", "revised_appropriation", "recommendation"], "proposed", MAPPING)
    assert meas == {"recommendation": "recommendation", "prior_appropriation": "appropration",
                    "prior_revised": "revised_appropriation"}


def test_2012_proposed_org_columns_feed_authority():
    # UT-03: 2012 proposed has "org"/"org_description" instead of appropriation_authority
    dims, _ = column_map(["department_code", "org", "org_description"], "proposed", MAPPING)
    assert dims["department_code"] == "department_code"
    assert dims["authority_code"] == "org"
    assert dims["authority_description"] == "org_description"


def test_codes_zero_padded_and_compared_numerically():
    # UT-04: "100", "0100" and "100.0" are the same fund
    assert norm_code("100", 4) == norm_code("0100", 4) == norm_code("100.0", 4) == "0100"
    assert norm_code("5", 4) == "0005"


def test_alphanumeric_codes_kept():
    # UT-05: grant funds and sub-accounts are alphanumeric
    assert norm_code("0k38", 4) == "0K38"
    assert norm_code("909A", 4) == "909A"
    assert norm_code("", 4) is None


def test_text_normalised_for_case_and_spacing():
    # UT-06: "Corporate Fund" and "CORPORATE  FUND" describe the same fund
    assert norm_text("Corporate Fund") == norm_text("CORPORATE  FUND ") == "CORPORATE FUND"


def test_authority_description_prefix_stripped():
    # UT-07: "2005 - POLICE BOARD" vs "POLICE BOARD"
    assert norm_text("2005 - Police Board", strip_prefix=True) == "POLICE BOARD"


def test_amount_parsing():
    # UT-08: formats seen in the files, blanks, and garbage
    assert parse_amount("145000.00") == 145000.0
    assert parse_amount("$1,234.50") == 1234.5
    assert parse_amount("-500") == -500.0
    assert parse_amount("") is None
    assert math.isnan(parse_amount("N/A"))
