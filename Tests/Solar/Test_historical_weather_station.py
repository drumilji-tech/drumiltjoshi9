"""Historical Weather Station Table Testing Module."""

from Model.DataAccess import Databricks_Repository
from Utils.ISightConstants import (
    HISTORICAL_WS_YEAR_TMY_VALUE,
    HISTORICAL_WS_ROUNDING_COLUMN_LOOKUP,
)

conn = Databricks_Repository()
TABLE_PATHNAME = f"{conn.solar_catalog}.isight.historical_weather_station"


def test_all_unique_attribute_types_exist():
    conn = Databricks_Repository()
    spark = conn.get_session()
    df_raw = spark.table(TABLE_PATHNAME).toPandas()

    actual_output = set(df_raw["attribute"])
    expected_output = set(["PAMA TMY GHI", "SA GHI", "SA TMY GHI"])

    assert actual_output == expected_output


def test_year_ghi_sums_are_infact_correct():
    year = 2022
    period = None
    selection = None
    plant = "Adobe"

    conn = Databricks_Repository()
    spark = conn.get_session()
    df_raw = spark.table(TABLE_PATHNAME).toPandas()

    df_raw = df_raw[df_raw["plant"] == plant]
    df_raw = df_raw[df_raw["attribute"] == "SA GHI"]
    df_raw = df_raw[df_raw["year"] == year]

    expected_output = 0
    for month in range(1, 13):
        dff = df_raw[df_raw["month"] == month]
        expected_output += dff["value"].values[0]
    expected_output = expected_output.round(
        HISTORICAL_WS_ROUNDING_COLUMN_LOOKUP["GHI (solar anywhere)"]
    )

    df_actual = conn.get_historical_weather_station_table(
        year=year,
        period=period,
        selection=selection,
    )
    actual_output = df_actual.loc[
        df_actual["Plant"] == plant, "GHI SA (kWh/m²)"
    ].values[0]

    assert expected_output == actual_output


def test_quarter_ghi_sums_are_infact_correct():
    year = 2022
    period = "Quarter"
    selection = 1
    plant = "Adobe"

    conn = Databricks_Repository()
    spark = conn.get_session()
    df_raw = spark.table(TABLE_PATHNAME).toPandas()

    dff = df_raw[df_raw["plant"] == plant]
    dff = dff[dff["attribute"] == "SA GHI"]
    dff = dff[dff["year"] == year]
    dff = dff[dff["month"].isin([1, 2, 3])]  # Months Jan, Feb, and March
    expected_output = dff["value"].sum()
    expected_output = expected_output.round(
        HISTORICAL_WS_ROUNDING_COLUMN_LOOKUP["GHI (solar anywhere)"]
    )

    df_actual = conn.get_historical_weather_station_table(
        year=year,
        period=period,
        selection=selection,
    )
    actual_output = df_actual.loc[
        df_actual["Plant"] == plant, "GHI SA (kWh/m²)"
    ].values[0]
    assert actual_output == expected_output


def test_total_count_is_correct():
    plant = "Adobe"
    month = 5

    conn = Databricks_Repository()
    spark = conn.get_session()
    df_raw = spark.table(TABLE_PATHNAME).toPandas()

    # See what the count is for a given month
    dff = df_raw[df_raw["plant"] == plant]
    dff = dff[dff["year"] == 2022]
    dff = dff[dff["month"] == month]
    expected_total_count = dff["total_count"].values[0]

    # Actually count up the number of occurances of that month
    dff2 = df_raw[df_raw["plant"] == plant]
    dff2 = dff2[dff2["month"] == month]
    dff2 = dff2[dff2["attribute"] == "SA GHI"]
    actual_total_count = len(dff2)

    assert expected_total_count == actual_total_count


def test_valid_ranking_across_all_quarters():
    conn = Databricks_Repository()
    spark = conn.get_session()
    df_raw = spark.table(TABLE_PATHNAME).toPandas()

    plant = "Adobe"
    quarter = 1
    dff = df_raw[df_raw["quarter"] == quarter]
    dff = dff[dff["plant"] == plant]
    dff = dff[dff["attribute"] == "SA GHI"]

    # manually sort the GHI values, and pick the Rth value
    rank = 13
    dff_sorted = dff.sort_values(by="value", ascending=True)
    actual_val = dff_sorted.iloc[rank - 1][
        "value"
    ]  # we subtract 1 since pandas indexing starts at 0

    # Using the R from above, search via the rank column for the same value
    expected_val = dff.loc[dff["rank"] == rank, "value"].values[0]

    assert expected_val == actual_val


def test_the_year_column_has_reserved_value():
    """This test validates that a special, reserved value exists in the years.

    Namely, this test looks for the existence of a value defined by
    the constant `HISTORICAL_WS_YEAR_TMY_VALUE`.

    This test is important because this value is necessary to deliver
    correct numbers in the Historical Weather Station Table table.
    """
    conn = Databricks_Repository()
    spark = conn.get_session()
    df_raw = spark.table(TABLE_PATHNAME).toPandas()

    years = df_raw["year"].dropna()
    unique_years = years.unique()
    assert HISTORICAL_WS_YEAR_TMY_VALUE in unique_years
