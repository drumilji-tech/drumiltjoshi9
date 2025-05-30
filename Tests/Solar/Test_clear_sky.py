"""Clear Sky Testing Module."""

from datetime import datetime

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from Model.DataAccess import Databricks_Repository
from Charts.Solar.Tornado import gen_clearsky_ratios_for_tooltip

def test_keep_only_clear_sky_days():
    conn = Databricks_Repository()
    df = pd.DataFrame({
        'date': pd.date_range(start='2024-07-26', periods=5),
        'ADB-BLK01-PCS002-WS1-GHI_cosine': [1, 2, 4, 8, np.nan],
        'TRQ-BLK03-PCS106-WS4-POA_pct_diff': [1, 2, 4, 8, 16],
        'TRQ-BLK06-PCS083-WS3-POA_pct_diff': [1, 2, 4, 8, 16],
    })
    clear_sky_df = pd.DataFrame({
        'date': ['2024-07-28'],
        'plant': ['TRQ'],
        'is_clear_sky_day': [1]
    })
    result_df = conn.keep_only_clear_sky_days(
        metrics_df=df,
        clear_sky_df=clear_sky_df,
    )
    expected_df = pd.DataFrame({
        'date': pd.date_range(start='2024-07-26', periods=5),
        'ADB-BLK01-PCS002-WS1-GHI_cosine': [1, 2, 4, 8, np.nan],
        'TRQ-BLK03-PCS106-WS4-POA_pct_diff': [1, 2, np.nan, 8, 16],
        'TRQ-BLK06-PCS083-WS3-POA_pct_diff': [1, 2, np.nan, 8, 16],
    })
    assert_frame_equal(result_df, expected_df, check_dtype=False, check_like=True)

def test_aggr_pandas_numeric_cols_avg():
    conn = Databricks_Repository()
    df = pd.DataFrame({
        'date': pd.date_range(start='2024-07-26', periods=5),
        'ADB-BLK01-PCS002-WS1-GHI_cosine': [1, 2, 4, 8, np.nan],
        'TRQ-BLK03-PCS106-WS4-POA_pct_diff': [1, 2, np.nan, 8, 16],
        'TRQ-BLK06-PCS083-WS3-POA_pct_diff': [1, 2, np.nan, 8, 16],
    })
    result_df = conn.aggr_pandas_numeric_cols(df, "avg")
    expected_df = pd.DataFrame({
        'ADB-BLK01-PCS002-WS1-GHI_cosine': [3.75],
        'TRQ-BLK03-PCS106-WS4-POA_pct_diff': [6.75],
        'TRQ-BLK06-PCS083-WS3-POA_pct_diff': [6.75],
    })
    assert_frame_equal(result_df, expected_df, check_dtype=False, check_like=True)

def test_aggr_pandas_numeric_cols_sum():
    conn = Databricks_Repository()
    df = pd.DataFrame({
        'date': pd.date_range(start='2024-07-26', periods=5),
        'ADB-BLK01-PCS002-WS1-GHI_cosine': [1, 2, 4, 8, np.nan],
        'TRQ-BLK03-PCS106-WS4-POA_pct_diff': [1, 2, np.nan, 8, 16],
        'TRQ-BLK06-PCS083-WS3-POA_pct_diff': [1, 2, np.nan, 8, 16],
    })
    result_df = conn.aggr_pandas_numeric_cols(df, "sum")
    expected_df = pd.DataFrame({
        'ADB-BLK01-PCS002-WS1-GHI_cosine': [15],
        'TRQ-BLK03-PCS106-WS4-POA_pct_diff': [27],
        'TRQ-BLK06-PCS083-WS3-POA_pct_diff': [27],
    })
    assert_frame_equal(result_df, expected_df, check_dtype=False, check_like=True)

def test_clear_sky_methods_match():
    """Make sure that `df_clear_sky` and `get_all_clear_sky_ratios` work sensibly."""
    conn = Databricks_Repository()

    str_start_date = "2024-07-30"
    str_end_date = "2024-07-31"
    start_date = datetime.strptime(str_start_date, "%Y-%m-%d")
    end_date = datetime.strptime(str_end_date, "%Y-%m-%d")

    all_plants = [
        "ADB",
        "APX",
        "BFC",
        "BFM",
        "BLD",
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
        "SHS",
        "SLS",
        "SOC",
        "SPM",
        "SSO",
        "TRQ",
    ]
    df_clear_sky = conn.get_clear_sky(start_date, end_date)
    all_clear_sky_ratios = conn.get_all_clear_sky_ratios(
        start_date=start_date, end_date=end_date,
    )

    for this_plant in all_plants:
        clear_sky_day_count = len(df_clear_sky[df_clear_sky["plant"] == this_plant])
        total_days_count = (end_date - start_date).days + 1
        expected_ratio = clear_sky_day_count / total_days_count

        actual_ratio = all_clear_sky_ratios[all_clear_sky_ratios["plant"] == this_plant]["ratio"].values[0]
        assert expected_ratio == actual_ratio

def test_gen_clearsky_ratios_for_tooltip_noclearskydays():
    raw_distance_data = pd.Series(
        index=["ADB-kiwi", "TRQ-apple", "PAW-orange", "CLP-pear"],
        data=[0 for _ in range(4)],
    )
    all_clear_sky_ratios = pd.DataFrame({
        "plant": [],
        "clear_sky_day_count": [],
        "total_days_count": [],
        "ratio": [],
    })
    result_output = gen_clearsky_ratios_for_tooltip(
        raw_distance_data=raw_distance_data,
        all_clear_sky_ratios=all_clear_sky_ratios,
    )
    expected_output = [-111, -111, -111, -111]
    assert result_output == expected_output

def test_gen_clearsky_ratios_for_tooltip_someclearskydays():
    raw_distance_data = pd.Series(
        index=["ADB-kiwi", "TRQ-apple", "PAW-orange", "CLP-pear"],
        data=[0 for _ in range(4)],
    )
    all_clear_sky_ratios = pd.DataFrame(
        {
            "plant": ["ADB", "CLP", "PAW", "TRQ"],
            "clear_sky_day_count": [1, 4, 3, 2],
            "total_days_count": [10, 10, 10, 10],
        }
    )
    result_output = gen_clearsky_ratios_for_tooltip(
        raw_distance_data=raw_distance_data,
        all_clear_sky_ratios=all_clear_sky_ratios,
    )
    expected_output = ['1/10', '2/10', '3/10', '4/10']
    assert result_output == expected_output

def test_gen_clearsky_ratios_for_tooltip_invalidplant():
    raw_distance_data = pd.Series(
        index=["ADB-kiwi", "12374689-apple", "PAW-orange", "CLP-pear"],
        data=[0 for _ in range(4)],
    )
    all_clear_sky_ratios = pd.DataFrame(
        {
            "plant": ["ADB", "CLP", "PAW", "TRQ"],
            "ratio": [0.1, 0.4, 0.3, 0.2],
            "clear_sky_day_count": [1, 4, 3, 2],
            "total_days_count": [10, 10, 10, 10],
        }
    )
    result_output = gen_clearsky_ratios_for_tooltip(
        raw_distance_data=raw_distance_data,
        all_clear_sky_ratios=all_clear_sky_ratios,
    )
    expected_output = ['1/10', -333, '3/10', '4/10']
    assert result_output == expected_output

def test_gen_clearsky_ratios_for_tooltip_invalidplant():
    raw_distance_data = pd.Series(
        index=["ABC", "123", "123", "123", "123", "ABC"],
        data=[0 for _ in range(6)],
    )
    all_clear_sky_ratios = pd.DataFrame(
        {
            "plant": ["ABC", "123"],
            "clear_sky_day_count": [1, 3],
            "total_days_count": [10, 10],
        }
    )
    result_output = gen_clearsky_ratios_for_tooltip(
        raw_distance_data=raw_distance_data,
        all_clear_sky_ratios=all_clear_sky_ratios,
    )
    expected_output = ['1/10', '3/10', '3/10', '3/10', '3/10', '1/10']
    assert result_output == expected_output

def test_gen_clearsky_ratios_for_tooltip_floatsinput():
    raw_distance_data = pd.Series(
        index=["ABC", "ABC", "ABC"],
        data=[123 for _ in range(3)],
    )
    all_clear_sky_ratios = pd.DataFrame(
        {
            "plant": ["ABC"],
            "clear_sky_day_count": [2.0],
            "total_days_count": [9.0],
        }
    )
    result_output = gen_clearsky_ratios_for_tooltip(
        raw_distance_data=raw_distance_data,
        all_clear_sky_ratios=all_clear_sky_ratios,
    )
    expected_output = ['2/9', '2/9', '2/9']
    assert result_output == expected_output

