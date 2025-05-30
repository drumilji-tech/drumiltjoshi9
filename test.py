"""Hooking up the Clear Sky."""
import re
import os
from datetime import datetime

import numpy as np
import pandas as pd
from Model.DataAccess import Databricks_Repository
from Charts.Solar.Helpers import (
    extract_weather_station,
    extract_power_conversion_station,
    extract_plant,
)

conn = Databricks_Repository()

# start_date = datetime(year=2024, month=1, day=1)
# end_date = datetime(year=2024, month=12, day=31)
str_start_date = "2024-07-30"
str_end_date = "2024-07-31"
start_date = datetime.strptime(str_start_date, "%Y-%m-%d")
end_date = datetime.strptime(str_end_date, "%Y-%m-%d")

df = conn.get_self_perform_plants()
print(df)