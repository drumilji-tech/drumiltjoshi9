"""Test Plants."""

from Model.DataAccess import Databricks_Repository


def test_all_plants():
    conn = Databricks_Repository()
    actual_output = conn.get_plants()

    expected_output = [
        "ADB",
        "APX",
        "BFC",
        "BFM",
        "BLD",
        "BWS",
        "CIM",
        "CLP",
        "CVS",
        "DCS",
        "DPS",
        "EPS",
        "GLA",
        "GLB",
        "GVS",
        "GW1",
        "HEN",
        "LAM",
        "LHS",
        "MOR",
        "MSS",
        "NSS",
        "PAW",
        "RFD",
        "RRK",
        "SAH",
        "SAK",
        "SHS",
        "SLS",
        "SOC",
        "SPM",
        "SSO",
        "TRQ",
    ]
    assert set(actual_output) == set(expected_output)
