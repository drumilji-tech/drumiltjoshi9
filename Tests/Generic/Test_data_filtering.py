"""Test helper functions in our Repository."""

from datetime import datetime

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from Model.DataAccess import Databricks_Repository

def test_filter_valid_measurements_pandas():
    conn = Databricks_Repository()
    df = pd.DataFrame({
        "col1": [1.0, np.nan, 3.0, 4.0],
        "col2": [np.nan, 2.0, 3.0, 4.0], 
        "col3": [1.0, 2.0, np.nan, 4.0],
        "col4": [1.0, 2.0, 3.0, 4.0]
    })
    
    measurement_columns = ["col1", "col2", "col3", "col4"]
    result_df = conn._filter_valid_measurements(df, measurement_columns)
    assert len(result_df) == len(df)

def test_filter_valid_measurements_pandas_drop_rows():
    conn = Databricks_Repository()
    df = pd.DataFrame({
        "col1": [1.0, np.nan, 3.0, np.nan],
        "col2": [np.nan, 2.0, 3.0, np.nan], 
        "col3": [1.0, 2.0, np.nan, np.nan],
        "col4": [1.0, 2.0, 3.0, np.nan]
    })
    result_df = conn._filter_valid_measurements(df, list(df.columns))
    assert len(result_df) == 3

def test_filter_valid_measurements_pyspark_drop_most_rows():
    conn = Databricks_Repository()
    spark = conn.get_session()

    data = [
        (None, None, None, None),
        (None, None, None, None),
        (None, None, None, None),
        (4.0, 4.0, 4.0, 4.0)
    ]
    column_array = ["col1", "col2", "col3", "col4"]
    df = spark.createDataFrame(data, column_array)
    result_df = conn._filter_valid_measurements(df, column_array)
    result_count = result_df.count()
    assert result_count == 1
