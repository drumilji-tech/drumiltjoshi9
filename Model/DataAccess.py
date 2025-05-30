import json
import os

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


import numpy as np

from databricks.connect import DatabricksSession
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from pyspark.sql import functions as F
from pyspark.sql import SparkSession
from pyspark.sql.functions import avg as pyspark_avg
from pyspark.sql.functions import sum as pyspark_sum
from pyspark.sql.functions import round as pyspark_round
from pyspark.sql.functions import min as pyspark_min
from pyspark.sql.functions import max as pyspark_max

from pyspark.sql.functions import (
    asc,
    count,
    col,
    expr,
    concat,
    first,
    concat_ws,
    lower,
    lit,
    regexp_extract,
    to_date,
    try_divide,
    from_json,
    map_values,
    collect_list,
)
from pyspark.sql.types import MapType, StringType, DoubleType

import pandas as pd
import urllib
from sqlalchemy import create_engine
from Charts.Solar.Helpers import (
    extract_plant,
    extract_weather_station,
    extract_measurement,
)
from Utils.ISightConstants import (
    DATABASE_METRIC_TRANSLATOR,
    HISTORICAL_WS_RENAMED_COLUMN_LOOKUP,
    HISTORICAL_WS_YEAR_TMY_VALUE,
    HISTORICAL_WS_SCALE_COLUMN_LOOKUP,
    HISTORICAL_WS_ROUNDING_COLUMN_LOOKUP,
    TOOLTIP_LOST_ENERGY_DECIMAL_ROUNDING,
    PI_TAG_REGEX_PATTERN_LOOKUP,
)
from Utils.UiConstants import (
    PERFORMANCE_METRICS,
    TURBINE_FAULT_DELIM,
    DESCRIPTION_CODE_DELIM,
)
from Utils.Enums import DataSourceType, ComponentTypes


class RepositoryFactory:
    """A factory for creating data repositories."""

    def create_repository(
        data_source_type=DataSourceType.MS_SQL_DATABASE,
        data_file_path=None,
        data=None,
        data_file_index=0,
        data_file_parse_dates=True,
    ):
        """Creates a new data repository.

        Args:
            data_source_type (DataSourceType): The type of data source to use.
            data_file_path (str): The path to the CSV file to use as the data source (if `data_source_type` is `DataSourceType.CSV`).
            data_file_index (int): The column to use as the index of the data (if `data_source_type` is `DataSourceType.CSV`).
            data_file_parse_dates (bool): Whether to parse dates in the CSV file (if `data_source_type` is `DataSourceType.CSV`).

        Returns:
            A new data repository.
        """
        repo = None
        if data_source_type == DataSourceType.MS_SQL_DATABASE:
            repo = MSSQL_Repository()

        if data_source_type == DataSourceType.CSV:
            repo = CSV_Repository(
                data_file_path=data_file_path,
                data=data,
                data_file_index=data_file_index,
                data_file_parse_dates=data_file_parse_dates,
            )
        return repo


class CSV_Repository:
    """A repository that reads data from a CSV file."""

    def __init__(
        self,
        data_file_path=None,
        data=None,
        data_file_index=0,
        data_file_parse_dates=True,
        freq=None,
    ):
        """Initializes a new instance of the CSV_Repository class.

        Args:
            data_file_path (str): The path to the CSV file to use as the data source.
            data (pandas.DataFrame): can pass in a dataframe instead of a path.
            data_file_index (int): The column to use as the index of the data.
            data_file_parse_dates (bool): Whether to parse dates in the CSV file.
        """
        self._path = data_file_path
        self._data_file_index = data_file_index
        self._data_file_parse_dates = data_file_parse_dates
        self._data = data
        self._main_freq = freq if freq is not None else "10T"
        self._dataframes = []

        if data is not None:
            self._dataframes.append(data)

    @property
    def data(self):
        """Gets the data from the CSV file.

        Returns:
            pandas.DataFrame: The data from the CSV file.
        """
        if self._data is None:
            self._data = self.get_data()

        return self._data

    def get_data(self):
        """Reads the data from the CSV file.

        Returns:
            pandas.DataFrame: The data from the CSV file.
        """
        if self._path:
            data = pd.read_csv(
                self._path,
                index_col=self._data_file_index,
                parse_dates=self._data_file_parse_dates,
            )

            return data
        else:
            return None

    def add_data(self, new_data, freq=None):
        """Adds new data to the repository."""

        new_freq = freq if freq is not None else pd.infer_freq(new_data.index)

        if new_freq is None:
            raise ValueError("Frequency of new dataset could not be inferred")

        # If the main dataframe is None, assign new_data to it
        if self.data is None:
            self._data = new_data
            return
        main_freq = self._main_freq

        if main_freq is None:
            raise ValueError("Frequency of main dataset could not be inferred")

        if main_freq == new_freq:
            # Check for overlapping columns
            overlapping_columns = set(self._data.columns).intersection(
                set(new_data.columns)
            )

            # If columns are mutually exclusive and dates overlap
            if not overlapping_columns and any(self._data.index.isin(new_data.index)):
                self._data = pd.concat([self._data, new_data], axis=1)
            else:
                self._data = pd.concat([self._data, new_data])
        else:
            # If frequencies don't match, append to _dataframes without overwriting main dataframe
            self._dataframes.append(new_data)

    def get_column_data(self, column_names, freq=None):
        """Retrieve data for specific columns.

        Args:
            column_names (list or str): The name(s) of the column(s) to
                retrieve.
            freq (str, optional): The frequency of the data to
                retrieve. If not provided and a column exists in multiple
                dataframes, an error is raised.

        Returns:
            pd.DataFrame: A dataframe containing the requested column data.

        Raises:
            ValueError: If any specified column is not found or if the frequency
            is ambiguous.
        """

        # Ensure column_names is a list
        if isinstance(column_names, str):
            column_names = [column_names]

        dfs_to_concat = []
        for col in column_names:
            if col in self.data.columns:
                dfs_to_concat.append(self.data[[col]])
                continue

            # If not found in main dataframe, check in the additional dataframes
            found_dataframes = [df for df in self._dataframes if col in df.columns]

            if len(found_dataframes) == 0:
                raise ValueError(f"Column '{col}' not found in any dataframe.")

            elif len(found_dataframes) > 1 and freq is None:
                raise ValueError(
                    f"Column '{col}' exists in multiple dataframes. Please specify a frequency."
                )

            for df in found_dataframes:
                if pd.infer_freq(df.index) == freq or (
                    freq is None and pd.infer_freq(df.index) is not None
                ):
                    dfs_to_concat.append(df[[col]])
                    break
            else:
                raise ValueError(
                    f"Column '{col}' not found for the specified frequency."
                )

        result_df = pd.concat(dfs_to_concat, axis=1)
        return result_df

    def get_all_column_names(self):
        """Returns all unique column names across the repository."""

        # Start with columns from the main dataframe
        all_columns = set(self.data.columns)

        # Add columns from each additional dataframe in _dataframes
        for df in self._dataframes:
            all_columns.update(list(set(df.columns)))

        return sorted(list(all_columns))


class MSSQL_Repository:
    """A repository that reads data from a Microsoft SQL Server database."""

    def __init__(
        self,
        server="",
        database="",
        uid="",
        pwd="",
    ):
        self._server = server
        self._database = database
        self._UID = uid
        self._pwd = pwd
        self._engine = None

    def connect(self):
        """Connects to the SQL Server and returns a connection object.

        Returns:
            sqlalchemy.engine.Connection: A connection to the SQL Server.
        """
        if self._engine is None:
            if all(
                x is not None
                for x in [self._server, self._database, self._UID, self._pwd]
            ):
                params = urllib.parse.quote_plus(
                    r"DRIVER={ODBC Driver 17 for SQL Server}"
                    + r";SERVER={};DATABASE={};UID={};PWD={}".format(
                        self._server, self._database, self._UID, self._pwd
                    )
                )
                conn_str = "mssql+pyodbc:///?odbc_connect={}".format(params)
                self._engine = create_engine(conn_str)
            else:
                raise ValueError(
                    "MSSQLRepository: must provide server, database, uid, and pwd to connect to the SQL server"
                )

        connection = self._engine.connect()
        return connection


class Databricks_Repository:
    """A repository that reads data from the Databricks Tables via the PySpark API."""

    def __init__(self):
        """Initializes a new instance of the class.

        Args:
            _spark (PySpark Session): The session object that establishes a connection
                to databricks.
            solar_catalog (str): The name of the Databricks Catalog Explorer
                for all data connections to be used in the Solar side of the
                application. See config.py for more info.
            wind_catalog (str): The name of the Databricks Catalog Explorer
                for all data connections to be used in the Solar side of the
                application. See config.py for more info.

        Returns:
            None
        """
        self._spark = None
        self._active_catalog_name = None
        self.solar_catalog = os.environ["ALT_DATABRICKS_CATALOG_SOLAR"]
        self.wind_catalog = os.environ["ALT_DATABRICKS_CATALOG_WIND"]

    def _get_catalog_path(self, catalog_name):
        """Returns southernpower, southernpower_dv, or southernpower_ua."""
        if catalog_name.lower() == "solar":
            return self.solar_catalog
        elif catalog_name.lower() == "wind":
            return self.wind_catalog
        else:
            raise Exception("The param catalog_name must either be 'solar' or 'wind'.")

    @staticmethod
    def keep_only_clear_sky_days(metrics_df, clear_sky_df):
        """Filter out the non clear sky days from all metrics.

        Args:
            metrics_df (pd.DataFrame): The metrics data, pre
                aggregation.
            clear_sky_df (pd.DataFrame): The clear sky data.

        Output:
            metrics_df (pd.DataFrame): The modified metrics data.
        """
        for index, row in clear_sky_df.iterrows():
            date = row["date"]
            plant = row["plant"]

            df_index = metrics_df[metrics_df["date"] == date].index
            matching_columns = [
                col for col in metrics_df.columns if col.startswith(plant)
            ]
            metrics_df.loc[df_index, matching_columns] = np.nan
        return metrics_df

    @staticmethod
    def aggr_pandas_numeric_cols(df, should_aggregate):
        """Aggregate the daily metrics into a one row DataFrame.

        Args:
            df (pd.DataFrame): ...
            should_aggregate (bool): See docstring of `get_metrics_data`.

        Returns:
            aggregated_df (pd.DataFrame): ...
        """
        if should_aggregate == False:
            return df
        else:
            numeric_columns = df.select_dtypes(include=['int64', 'float64']).columns
            avg_cols = [
                colname for colname in numeric_columns if Databricks_Repository.should_aggregate_with_average(colname)
            ]
            sum_cols = [
                colname for colname in numeric_columns if not Databricks_Repository.should_aggregate_with_average(colname)
            ]
            agg_dict = {col: "sum" for col in sum_cols}
            agg_dict.update({col: "mean" for col in avg_cols})

            return df.agg(agg_dict).to_frame().T

    @staticmethod
    def should_aggregate_with_average(colname):
        """Determine whether or not we should aggregate by average.

        Args:
            str (colname): A column name from either the daytime_metrics,
                nighttime_metrics, or metrics delta table.

        Returns:
            (bool): A boolean. True means we should aggregate the values
                associated to the column `colname` with an average. In
                False, this means we should take a sum.
        """
        return extract_measurement(colname) == "BOM" or "pct_diff" in colname

    @staticmethod
    def aggr_pyspark_numeric_cols(df, should_aggregate):
        """Aggregate the daily metrics into a one row DataFrame.

        Args:
            df (pyspark.DataFrame): ...
            should_aggregate (bool): See docstring of `get_metrics_data`.

        Returns:
            aggregated_df (pd.DataFrame): ...
        """
        if should_aggregate == False:
            return df.toPandas()
        else:
            numeric_columns = [col_name for col_name, col_type in df.dtypes if col_type in ["int", "double", "float"]]

            avg_cols = [
                colname for colname in numeric_columns if Databricks_Repository.should_aggregate_with_average(colname)
            ]
            sum_cols = [
                colname for colname in numeric_columns if not Databricks_Repository.should_aggregate_with_average(colname)
            ]
            aggr_avg_rules = [pyspark_avg(col_name).alias(col_name) for col_name in avg_cols]
            aggr_sum_rules = [pyspark_sum(col_name).alias(col_name) for col_name in sum_cols]
            all_aggr_rules = aggr_avg_rules + aggr_sum_rules
            return df.agg(*all_aggr_rules).toPandas()

    @staticmethod
    def filter_by_dates(df, start_date, end_date):
        """Filter a daily dataframe between two dates, inclusively.

        Args:
            df (PySpark DataFrame): The input dataframe.
            start_date (datetime.date): The start date.
            end_date (datetime.date): The end date.

        Returns:
            df (pd.DataFrame): A modified dataframe.
        """
        return df.filter(
            (df.date >= start_date) & (df.date <= (end_date + timedelta(days=1)))
        )
    
    @staticmethod
    def _filter_valid_measurements(df, measurement_columns):
        """Filter DataFrame to keep rows with at least one valid measurement.

        Args:
            df (Union[pd.DataFrame, pyspark.sql.DataFrame]): Input DataFrame, either Pandas or PySpark
            measurement_columns (list): List of column names to check for valid values

        Returns:
            Union[pd.DataFrame, pyspark.sql.DataFrame]: Filtered DataFrame containing only rows with at least one valid measurement,
            returned in the same type as the input DataFrame
        """
        # Pandas DataFrame case
        if isinstance(df, pd.DataFrame):
            return df[df[measurement_columns].notna().any(axis=1)]

        # PySpark DataFrame case
        not_all_null_condition = col(measurement_columns[0]).isNotNull()
        for col_name in measurement_columns[1:]:
            not_all_null_condition = not_all_null_condition | col(col_name).isNotNull()
        filtered_df = df.filter(not_all_null_condition)
        return filtered_df

    def get_session(self, catalog_name=None):
        """Returns the PySpark Session Connection.

        Dynamically handles authentication via OAuth (Client ID and Secret) or
        Personal Access Token (PAT). Caches the session for reuse.
        """
        if catalog_name is None:
            catalog_name = "wind"

        new_connection_required = (
            self._spark is None or
            self._active_catalog_name != catalog_name
        )

        if new_connection_required:
            try:
                token = os.environ.get("DATABRICKS_TOKEN")  # TODO: Remove safely

                prefix = catalog_name.upper() + "_"
                if catalog_name.lower() not in ("solar", "wind"):
                    raise Exception("The 'catalog_name' param must be either 'solar' or 'wind'. Uppercase is allowed as well.")
                host = os.environ.get(f"{prefix}ALT_DATABRICKS_HOST")
                client_id = os.environ.get(f"{prefix}ALT_DATABRICKS_CLIENT_ID")
                client_secret = os.environ.get(f"{prefix}ALT_DATABRICKS_CLIENT_SECRET")
                if not host:
                    raise ValueError("Environment variable DATABRICKS_HOST is not set.")

                # Prioritize OAuth if client_id and client_secret are available
                if client_id and client_secret:
                    os.environ.pop("DATABRICKS_TOKEN", None)
                    
                    config = Config(
                        host=host,
                        client_id=client_id,
                        client_secret=client_secret,
                        serverless_compute_id="auto",
                    )
                    self._active_catalog_name = catalog_name
                elif token:
                    print("Using PAT authentication...")
                    config = Config(
                        host=host,
                        token=token,
                        serverless_compute_id="auto",
                    )
                else:
                    raise ValueError("No valid authentication method found. Provide either PAT or OAuth credentials.")

                # Create Databricks session
                self._spark = DatabricksSession.builder.sdkConfig(config).getOrCreate()

            except Exception as e:
                print(f"Failed to create Databricks session: {e}")
                raise RuntimeError("Unable to establish a Databricks connection.")
        return self._spark

    def get_table_last_updated(self, table_name):
        """Retrieves the last updated date of the specified table.

        Args:
            table_name (str): The name of the Databricks table.
        
        Returns:
            last_date (datetime): The last updated date of the table.
        """
        catalog_name = "solar"
        spark = self.get_session(catalog_name)
        result = spark.sql(f"DESCRIBE DETAIL {table_name}").select("lastModified").collect()
        last_date = result[0]["lastModified"] if result else None
        if last_date:
            last_date = last_date.strftime("%B %d, %Y")
        return last_date

    def get_plants(self, is_sorted=None) -> list:
        """Returns all unique plant names from the metrics table.

        Args:
            is_sorted (bool): Determines if the plants are
                sorted. By default, this is False.
        """
        if is_sorted is None:
            is_sorted = False

        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.metrics")

        # remove the date column since we don't need it
        df = df.drop("date")
        df = df.drop("start_time_utc")
        df = df.drop("Date")

        column_names = df.columns
        unique_prefixes = {col[:3] for col in column_names}
        plant_names = list(unique_prefixes)

        if is_sorted:
            plant_names = sorted(plant_names)
        return plant_names

    def get_plant_weatherstation_pairs(self) -> list:
        """Returns all unique plant-weatherstation names from the metrics table.

        An example looks like "ABD-WS1": Weather Station 1 for Adobe (ADB).
        """

        def _clean_colname(colname):
            plant = extract_plant(colname)
            ws = extract_weather_station(colname)
            return f"{plant}-{ws}"

        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.metrics")

        # remove the date column
        df = df.drop("date")
        df = df.drop("start_time_utc")
        df = df.drop("Date")

        names = [_clean_colname(col) for col in df.columns]
        names = list(set(names))
        names = sorted(names)
        return names

    def get_min_and_max_dates_across_tables(self, table_array, catalog_name) -> [datetime.date, datetime.date]:
        """Grab the min and max dates across an arbitrary number of tables."""
        spark = self.get_session(catalog_name)

        overall_min_date = None
        overall_max_date = None
        for table in table_array:
            date_columns = ["date", "day"]
            date_column = None
            
            for col in date_columns:
                if col not in spark.table(table).columns:
                    continue
                df = spark.table(table)
                df.select(col)
                date_column = col

            if not date_column:
                raise ValueError(f"Could not find date column in table {table}.")
            
            min_max_dates = df.agg(
                pyspark_min(date_column).alias("min_date"), 
                pyspark_max(date_column).alias("max_date")
            ).collect()[0]
            
            try:
                current_min_date = datetime.strptime(min_max_dates["min_date"], "%Y-%m-%d").date()
                current_max_date = datetime.strptime(min_max_dates["max_date"], "%Y-%m-%d").date()
            except ValueError:
                continue

            if overall_min_date is None or current_min_date < overall_min_date:
                overall_min_date = current_min_date
            if overall_max_date is None or current_max_date > overall_max_date:
                overall_max_date = current_max_date
        
        if overall_min_date is None or overall_max_date is None:
            raise ValueError("Could not extract date range from any of the specified tables")
        
        return overall_min_date, overall_max_date

    def get_date_range(self) -> [datetime.date, datetime.date]:
        """Returns the lower and upper dates for the date picker.
        
        This Function relies on pulling data from the metrics table
        as well as the inverter table, and then figuring out the min
        and the max dates across both datasets.
        
        By doing this, we can assure that the date selector allows
        the user to click on any day in this range. 
        """
        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)

        # Grab min and max dates from the metrics table
        df = spark.table(f"{catalog_path}.isight.metrics")
        min_max_dates = df.agg(
            pyspark_min("date").alias("min_date"), pyspark_max("date").alias("max_date")
        ).collect()[0]

        # Grab min and max dates from the inverter metrics table
        df_inv = spark.table(f"{catalog_path}.isight.inverter_metrics")
        inv_min_max_dates = df_inv.agg(
            pyspark_min("day").alias("min_date"), pyspark_max("day").alias("max_date")
        ).collect()[0]
        inv_min_date = datetime.strptime(inv_min_max_dates["min_date"], "%Y-%m-%d").date()
        inv_max_date = datetime.strptime(inv_min_max_dates["max_date"], "%Y-%m-%d").date()

        # Find the min and max date across both tables
        min_date = min(
            min_max_dates["min_date"], inv_min_date
        )
        max_date = max(
            min_max_dates["max_date"], inv_max_date
        )
        return min_date, max_date

    def get_metrics_data(
        self,
        start_date,
        end_date,
        plant=None,
        measurement=None,
        metric=None,
        should_aggregate=None,
        day_night_filter=None,
        only_clear_sky_days=None,
    ):
        """Returns daily-aggregated metrics across all Weather Stations.

        Args:
            start_date (datetime.datetime): The start date from which the data
                is filtered.
            end_date (datetime.datetime): The end date to which the data is
                filtered.
            plant (list, optional): The plant or plants you want to return. These
                plant names are 3-characters long. If None, all plants will be
                returned and no filtering will be done. Otherwise, this param must
                be an array.
            measurement (str): A physical quantity for which to filter the data
                by. This param can be one of "BOM" (Back of Module Temperature),
                "GHI" (Global Horizontal Irradiance) or "POA" (Plane of Array
                Irradiance).
            metric (str): The technique used to calculate the measurement
                specified with `measurement`. The possible options come from
                the keys of `DATABASE_METRIC_TRANSLATOR`.
            should_aggregate (bool): Determines if the data should be aggregated.
                If it is, a combination of summing and averaging will be applied
                based on the nature of the columns in question. To learn more,
                see the `should_aggregate_with_average` method.
            day_night_filter (str, optional): This param determines if we get all of
                our data, if we get back data from only the daytime (i.e. "Day"), or
                if we get data from only the nighttime (i.e. "Night"). If left
                blank, all data is returned.
            only_clear_sky_days (bool): If True, all the days that were not clear sky,
                across all the columns of the metrics data will be dropped from the
                final resulting number. This means the corresponding cell where on
                a given date, and on a given plant, if it was not a clear sky then
                the field in the table will be a NULL, which will not contribute to
                the final aggregation (see `aggr_func` for types of aggregations).

        Returns:
            (pd.DataFrame): A dataframe with a single row.
                The columns are of the form:
                  "{plant}-{block}-{power_conversion_station}-{weather_station}-{measurement}_{metric}"

                Where an example column looks like this:
                  `ADB-BLK01-PCS002-WS1-BOM_eucl`.
        """
        if should_aggregate is None:
            should_aggregate = False
        if only_clear_sky_days is None:
            only_clear_sky_days = False
        if plant is not None and not isinstance(plant, list):
            plant = [plant]

        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        if isinstance(day_night_filter, str) and day_night_filter.lower() == "day":
            table_path = f"{catalog_path}.isight.daytime_metrics"
        elif isinstance(day_night_filter, str) and day_night_filter.lower() == "night":
            table_path = f"{catalog_path}.isight.nighttime_metrics"
        else:
            table_path = f"{catalog_path}.isight.metrics"

        try:
            translated_metric = DATABASE_METRIC_TRANSLATOR[metric]
        except KeyError:
            translated_metric = None
        df = spark.table(table_path)

        # Filter by date range first to get rid of as much data as possible for subsequential calcs
        start_date = start_date.date()
        end_date = end_date.date()
        df = df.filter((df.date >= start_date) & (df.date <= end_date))

        # sort the date column in ascending order
        df = df.orderBy(col("date").asc())

        # filter dataset by parameters: TODO: wrap and test
        filtered_cols = df.columns
        if translated_metric:
            filtered_cols = [
                col_name
                for col_name in filtered_cols
                if col_name.endswith(translated_metric)
            ]
        if measurement:
            filtered_cols = [
                col_name for col_name in filtered_cols if measurement in col_name
            ]
        if plant is not None:
            plant_set = tuple(plant)
            filtered_cols = [
                col_name for col_name in filtered_cols if col_name.startswith(plant_set)
            ]
        filtered_cols = [col_name for col_name in filtered_cols if col_name != "date"]
        df = df.select("date", *filtered_cols)

        if len(df.toPandas().columns) == 1 and df.columns[0] == "date":
            return df.toPandas()

        # Filter by clear sky if applicable
        if only_clear_sky_days:
            clear_sky_df = self.get_clear_sky(
                start_date=start_date,
                end_date=end_date,
                as_pyspark=False,
            )

            # Note that we convert to pandas to avoid a RecursionError
            # that happens in the aggregation stage below
            df = df.toPandas()

            df = self.keep_only_clear_sky_days(
                metrics_df=df,
                clear_sky_df=clear_sky_df,
            )

        # Aggregate all numeric Columns
        if isinstance(df, pd.DataFrame):
            output_df =  self.aggr_pandas_numeric_cols(df=df, should_aggregate=should_aggregate)
        else:
            output_df = self.aggr_pyspark_numeric_cols(df=df, should_aggregate=should_aggregate)
        return output_df

    def get_recovery_data(
        self,
        start_date,
        end_date,
        plant=None,
        measurement=None,
        aggr_func=None,
        day_night_filter=None,
    ):
        """Returns the recovery data across Weather Stations.

        Args:
            start_date (datetime.datetime): The start date from which the data
                is filtered.
            end_date (datetime.datetime): The end date to which the data is
                filtered.
            plant (list, optional): The plant or plants you want to return. These
                plant names are 3-characters long. If None, all plants will be
                returned and no filtering will be done. Otherwise, this param must
                be an array.
            measurement (str): A physical quantity for which to filter the data
                by. This param can be one of "BOM" (Back of Module Temperature),
                "GHI" (Global Horizontal Irradiance) or "POA" (Plane of Array
                Irradiance).
            aggr_func (str). The aggregation function used to rollup the table before
                returning from this function. Possible arguments are "avg" or "sum".
            day_night_filter (str, optional): This param determines if we get all of
                our data, if we get back data from only the daytime (i.e. "Day"), or
                if if we get data from only the nighttime (i.e. "Night"). If left
                blank, all data is returned.

        Returns:
            (pd.DataFrame): A dataframe with a single row.
                The columns are of the form:
                  "{plant}-{block}-{power_conversion_station}-{weather_station}-{measurement}_recovery"

                Where an example column looks like this:
                  `ADB-BLK01-PCS013-WS3-POA_recovery`.
        """
        if not aggr_func:
            aggr_func = "avg"
        if plant is not None and not isinstance(plant, list):
            plant = [plant]

        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        if isinstance(day_night_filter, str) and day_night_filter.lower() == "day":
            table_path = f"{catalog_path}.isight.daytime_recovery"
        elif isinstance(day_night_filter, str) and day_night_filter.lower() == "night":
            table_path = f"{catalog_path}.isight.nighttime_recovery"
        else:
            table_path = f"{catalog_path}.isight.recovery"
        df = spark.table(table_path)

        # as a safety check, rename the date column so calculations below run
        date_colname = "date"
        invalid_date_colname_arr = ["start_time_utc", "Date"]
        for invalid_colname in invalid_date_colname_arr:
            if invalid_colname in df.columns:
                df = df.withColumnRenamed(invalid_colname, date_colname)

        # Filter by date range first to get rid of as much data as possible for subsequential calcs
        end_date = end_date + timedelta(days=1)
        df = df.filter((df.date >= start_date) & (df.date <= end_date))

        # Sort the DataFrame by the date column
        df = df.orderBy(col(date_colname).asc())

        # filter dataset by parameters
        filtered_cols = df.columns
        if measurement:
            filtered_cols = [
                col_name for col_name in filtered_cols if measurement in col_name
            ]
        if plant is not None:
            plant_set = tuple(plant)
            filtered_cols = [
                col_name for col_name in filtered_cols if col_name.startswith(plant_set)
            ]
        df = df.select(date_colname, *filtered_cols)
        if len(df.toPandas().columns) == 1 and df.columns[0].lower() == date_colname:
            return df.toPandas()

        # Aggregate the numeric columns
        numeric_columns = [
            col_name
            for col_name, col_type in df.dtypes
            if col_type in ["int", "double", "float"]
        ]
        if aggr_func == "avg":
            aggregated_df = df.agg(
                *[pyspark_avg(col_name).alias(col_name) for col_name in numeric_columns]
            )
        elif aggr_func == "sum":
            aggregated_df = df.agg(
                *[pyspark_sum(col_name).alias(col_name) for col_name in numeric_columns]
            )
        return aggregated_df.toPandas()

    def get_daily_values_for_weather_station(
        self, weather_station, start_date, end_date
    ):
        """Get the daily values for one weather station.

        The data in this method is used to build the sparklines chart that visualizes
        all the metrics for one weather station across the time span selected in the top
        panel of the application.

        Args:
            weather_station (str): The full PI Tag of the desired weather station.
                Eg. "SSO-BLK02-PCS004-WS2-GHI"
            start_date (datetime.datetime): The start date from which the data
                is filtered.
            end_date (datetime.datetime): The end date to which the data is
                filtered.

        Returns:
            (pandas.DataFrame): A dataframe that contains data from
                the isight_cur.metrics Databricks table, filtered by
                date, and filtered by columns that start with
                `weather_station`.
        """
        catalog_name = "solar"
        spark = self.get_session(catalog_name)
        catalog_path = self._get_catalog_path(catalog_name)
        df = spark.table(f"{catalog_path}.isight.metrics")

        # filter by date - convert to date so filtering works as expected
        start_date = start_date.date()
        end_date = end_date.date()
        df = df.filter((df.date >= start_date) & (df.date <= end_date))

        # Sort the DataFrame by the date column
        df = df.orderBy(col("Date").asc())

        # filter the weather stations we care about
        filtered_cols = df.columns
        filtered_cols = [
            col_name
            for col_name in filtered_cols
            if col_name.startswith(weather_station)
        ]
        df = df.select("date", *filtered_cols)
        df = df.toPandas()
        df['date'] = pd.to_datetime(df['date'])

        return df

    def filter_for_tmy_dataset(self, df, attribute, period, selection):
        """Filter the HWS Table to get TMY dataset.

        Args:
            df (pyspark.dataframe): This is the table from the `historical_weather_station`.
            attribute (str): Can either be "PAMA TMY GHI" or "SA TMY GHI".

        Returns:
            (pyspark.dataframe): A dataframe with column names 'plant' and 'Summed TMY Columns'
        """
        valid_attribute_arr = ["PAMA TMY GHI", "SA TMY GHI"]
        if attribute not in valid_attribute_arr:
            raise Exception(
                f"You must set attribute to a valid choice. Pick a value from {valid_attribute_arr}"
            )

        if period is None or selection is None:
            df_tmy_ghi = df.filter(
                (
                    (col("year") == HISTORICAL_WS_YEAR_TMY_VALUE)
                    & (col("month").isNull())
                    & (col("quarter").isNull())
                    & (col("attribute") == attribute)
                )
            )
        elif period == "Month" and selection:
            df_tmy_ghi = df.filter(
                (
                    (col("year").isNull())
                    & (col("month") == selection)
                    & (col("quarter").isNull())
                    & (col("attribute") == attribute)
                )
            )
        elif period == "Quarter" and selection:
            df_tmy_ghi = df.filter(
                (
                    (col("year").isNull())
                    & (col("month").isNull())
                    & (col("quarter") == selection)
                    & (col("attribute") == attribute)
                )
            )
        else:
            raise Exception("We should never see this message.")

        df_tmy_ghi = df_tmy_ghi.select("plant", "value")
        df_tmy_ghi = df_tmy_ghi.withColumnRenamed("value", f"Summed {attribute}")
        return df_tmy_ghi

    def get_historical_weather_station_year_range(self):
        """Get the min and max year in the historical weather station table.
        
        Args:
            None

        Returns:
            output (list of ints): A list containing the
                min and max year respectively in the year
                column. These values are used to populate
                the "Year" dropdown that appears next to
                the Historical Weather Station table in
                the UI.

                Note that the year column also contains a
                reserved character that happens to be a number.
                This reserved number is used for filtering the
                data and presenting different views in the UI.

                In our query, we make sure to ignore this when
                looking for the min and max year, as it could
                be a small number (eg. 1) which is obviously
                not correct.
        """
        catalog_name = "solar"
        spark = self.get_session(catalog_name)
        catalog_path = self._get_catalog_path(catalog_name)
        df = spark.sql(
            f"""
            SELECT MIN(year) AS min_year, MAX(year) AS max_year
            FROM {catalog_path}.isight.historical_weather_station
            WHERE year IS NOT NULL
            AND CAST(year AS INT) != {HISTORICAL_WS_YEAR_TMY_VALUE}
            """
        )
        year_range = df.collect()[0]
        output = [year_range["min_year"], year_range["max_year"]]
        output = [int(y) for y in output]
        return output

    def get_historical_weather_station_table(self, year, period, selection):
        """Get the historical weather station values.

        These data comes from the `isight_cur.historical_weather_station`
        table from Databricks.

        Example #1: Historical Table for 2022
        ```
        df = conn.get_historical_weather_station_table(
            year=2022,
            period=None,
            selection=None,
        )
        ```

        Example #2: Historical Table for March, 2022
        ```
        df = conn.get_historical_weather_station_table(
            year=2022,
            period="March",
            selection=3,
        )
        ```

        Example #3: Historical Table for Q4, 2022
        ```
        df = conn.get_historical_weather_station_table(
            year=2022,
            period="Quarter",
            selection=4,
        )
        ```

        Args:
            year (int): A number that comes from the 'Year' dropdown next to the
                Historical Weather Station table.
            period (str): One of "Month" or "Quarter". This number comes from
                the 'Period' dropdown next to the Historical Weather Station
                table.
            selection (int): A number that comes from the 'Selection' dropdown.
                Depending on the `period` that is provided, this hones down
                the actual temporal interval you are interested in.
                - If `period` is "Month":
                    `selection` must between an int between 1-12, inclusive.
                    (1 means January, 2 means February, etc.)
                - If `period` is "Quarter":
                    - `selection` must be an int between 1-4, inclusive.
                    (1 means Quarter 1, 2 means Quarter 2, etc)

        Returns:
            df (pandas.DataFrame): A table containing historical values across sites
                spanning across a portion of time.
        """
        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.historical_weather_station")

        # alphabetize the plant column more smoother JOINs later
        df = df.orderBy(col("plant").asc())

        # filter to the GHI values based on the selection
        temp_df = df
        temp_df = temp_df.filter(temp_df.year == year)
        if period is None or selection is None:
            temp_ghi_df = temp_df.filter(
                (
                    (col("year").isNotNull())
                    & (col("month").isNull())
                    & (col("quarter").isNull())
                )
            )
        elif period == "Month" and selection:
            temp_df = temp_df.filter(temp_df.month == selection)
            temp_ghi_df = temp_df.filter(
                (
                    (col("year").isNotNull())
                    & (col("month").isNotNull())
                    & (col("quarter").isNull())
                )
            )
        elif period == "Quarter" and selection:
            temp_df = temp_df.filter(temp_df.quarter == selection)
            temp_ghi_df = temp_df.filter(
                (
                    (col("year").isNotNull())
                    & (col("month").isNull())
                    & (col("quarter").isNotNull())
                )
            )
        else:
            raise Exception("We should never see this message.")

        # Rollup the PAMA TMY values
        temp_pama_ghi_df = self.filter_for_tmy_dataset(
            df=df,
            attribute="PAMA TMY GHI",
            period=period,
            selection=selection,
        )

        # Rollup the SA TMY values
        temp_sa_ghi_df = self.filter_for_tmy_dataset(
            df=df,
            attribute="SA TMY GHI",
            period=period,
            selection=selection,
        )

        # Merge PAMA TMY values and SA TMY values
        temp_merged_df = temp_ghi_df.join(temp_pama_ghi_df, on="plant", how="inner")
        temp_merged_df = temp_merged_df.join(temp_sa_ghi_df, on="plant", how="inner")

        # Calculate 'Variance to Mean' column in place
        temp_w_variance_df = temp_merged_df.withColumn(
            "Variance to Mean",
            try_divide(
                (col("value") - col("Summed PAMA TMY GHI")),
                col("Summed PAMA TMY GHI")
            )
        )

        # Trim the dataframe to the columns we want to show in the UI
        temp_reduced_df = temp_w_variance_df.select(
            "plant",
            "value",
            "Summed PAMA TMY GHI",
            "Summed SA TMY GHI",
            "Variance to Mean",
            "poe",
        )

        # (rename column names so compatible with old code that Adam wrote)
        temp_reduced_df = temp_reduced_df.withColumnRenamed(
            "value", "GHI (solar anywhere)"
        )
        temp_reduced_df = temp_reduced_df.withColumnRenamed(
            "Summed SA TMY GHI", "SA TMY GHI"
        )
        temp_reduced_df = temp_reduced_df.withColumnRenamed(
            "Summed PAMA TMY GHI", "PAMA TMY GHI"
        )

        # format probability of exceedance column
        temp_reduced_df = temp_reduced_df.withColumn(
            "Probability of Exceedance",

            expr("concat('P', lpad(cast(int(poe * 100) as string), 2, '0'))")

        )

        temp_reduced_df = temp_reduced_df.drop("poe")

        # round the values in some columns
        for column_name in HISTORICAL_WS_ROUNDING_COLUMN_LOOKUP.keys():
            scale = HISTORICAL_WS_SCALE_COLUMN_LOOKUP[column_name]
            rounding = HISTORICAL_WS_ROUNDING_COLUMN_LOOKUP[column_name]
            temp_reduced_df = temp_reduced_df.withColumn(
                column_name, pyspark_round(col(column_name) * scale, rounding)
            )

        # rename the columns so non-industry people can understand
        for old_name, new_name in HISTORICAL_WS_RENAMED_COLUMN_LOOKUP.items():
            temp_reduced_df = temp_reduced_df.withColumnRenamed(old_name, new_name)

        output_df = temp_reduced_df
        return output_df.toPandas()

    def get_budget_deviation(
        self,
        start_date,
        end_date,
        measurement,
        kpi,
    ):
        """Get the Budget Deviation of all weather stations for a measurement.

        These numbers serve to indicate the adjustment necessary to
        measurement values taken on our weather stations to recalibrate
        our expectations.

        This adjustment is important because the business creates budgets
        based on these measurements. If they are off, then the allocated
        budget is also off. This method serves to fill the gap.

        These numbers are visible in the tooltips of the tornado
        charts that sit at the top of the Weather Station Health page of
        the app. They are found in the "MWh" section.
            (NB. under the hood, we are indeed using energy to
            gauge deivation in measurement error.)

        Args:
            start_date (datetime.datetime): The start date from
                which the data is filtered.
            end_date (datetime.datetime): The end date to which
                the data is filtered.
            measurement (str): One of "GHI, "POA" or "BOM".
            kpi (str): Either "energy" or "revenue". This determines
                the type of deviation we are capturing.

        Returns:
            (pandas.DataFrame): A 1-column pandas DataFrame, with index.

                index        deviation
                ADB-002-WS1       57.0
                ADB-006-WS2       81.0
                ADB-013-WS3       86.0
                APX-001-WS1      162.0
                APX-007-WS3        0.0
                ...                ...
                SPM-00V-WS4        0.0
                TRQ-041-WS1     1084.0
                TRQ-012-WS2     1755.0
                TRQ-083-WS3      552.0
                TRQ-106-WS4    -4837.0

                Where:
                    index (str): The pruned metric attributes
                        for a specific weather station sensor.
                    deviation (float): The deviation between
                        the actual and expected budget calcs.
                        Note that deviation actually.
        """
        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.budget_deviation")

        # Ensure the datetime column name is correct
        if "start_time_utc" in df.columns:
            df = df.withColumnRenamed("start_time_utc", "date")

        fmt_start_date = start_date.strftime("%Y-%m-%d")
        fmt_end_date = end_date.strftime("%Y-%m-%d")
        result_df = df.filter(
            (col("type") == measurement)
            & (col("date").between(fmt_start_date, fmt_end_date))
        )

        # aggregate the appropriate deviation column
        if kpi == "energy":
            deviation_column = "budget_deviation"
        elif kpi == "revenue":
            deviation_column = "lost_revenue"
        else:
            raise Exception("Invalid value. The `kpi` param must be either 'energy' or 'revenue'.")
        if measurement in ["GHI"]:
            deviation_column = "".join(["pama_", deviation_column])
        result_df = result_df.groupBy("plant", "type", "pcs", "weather_station").agg(
            pyspark_round(
                pyspark_sum(deviation_column), TOOLTIP_LOST_ENERGY_DECIMAL_ROUNDING
            ).alias("deviation")
        )

        result_df = result_df.withColumn(
            "pcs_code",
            regexp_extract(
                result_df["pcs"],
                PI_TAG_REGEX_PATTERN_LOOKUP["power_conversion_station"],
                1,
            ),
        )

        # create an "index" column intended to match the with tornado yaxis labels
        result_df = result_df.withColumn(
            "index",
            concat_ws("-", col("plant"), col("pcs_code"), col("weather_station")),
        )
        result_df = result_df.orderBy("plant", "weather_station")
        result_df = result_df.select(["index", "deviation"])

        result_df_pandas = result_df.toPandas()
        result_df_pandas.set_index("index", inplace=True)
        return result_df_pandas

    def get_clear_sky(self, start_date, end_date, as_pyspark=None):
        """Get the Clear Sky table across all plants.

        Args:
            start_date (datetime.datetime): The start date from
                which the data is filtered.
            end_date (datetime.datetime): The end date to which
                the data is filtered.
            as_pyspark (bool): If True, will return the output
                as a PySpark DataFrame. If False, a Pandas Dataframe.

        Returns:
            result_df (pd.DataFrame) A DataFrame that looks like this:
                date (str): A day.
                plant (str): The 3 letter plant name.
                is_clear_sky_day (bool): This column is always 1

        """
        if as_pyspark is None:
            as_pyspark = False

        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.clear_sky_days")

        # Ensure the datetime column name is correct
        wrong_date_col = "date_clear_sky"
        if wrong_date_col in df.columns:
            df = df.withColumnRenamed(wrong_date_col, "date")

        start_date = start_date.date()
        end_date = end_date.date()
        # df = self.filter_by_dates(df, start_date, end_date)
        df = df.filter( (df.date >= start_date) & (df.date <= end_date) )
        df = df.orderBy(col("date").asc())

        df = df.withColumnRenamed("plant_abbrev_clear_sky", "plant")
        df = df.select(["date", "plant", "is_clear_sky_day"])
        df = df.filter(df["is_clear_sky_day"] == 1)

        if as_pyspark:
            return df
        return df.toPandas()

    def get_all_clear_sky_ratios(self, start_date, end_date, as_pyspark=None):
        """Returns the proportions of clear sky days for the desired dates.

        Args:
            start_date (datetime.datetime): The start date from
                which the data is filtered.
            end_date (datetime.datetime): The end date to which
                the data is filtered.
            as_pyspark (bool): If True, will return the output
                as a PySpark DataFrame. If False, a Pandas Dataframe.

        Returns:
            result_df (pd.DataFrame) A Dataframe with the following columns:
                plant (str): The 3 letter plant name abbreviation.
                clear_sky_day_count (int)
                total_days_count (int)
                ratio (float): 'clear_sky_day_count' divided by 'total_days_count'.
        """
        if as_pyspark is None:
            as_pyspark = False

        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.clear_sky_days")

        # Rename our columns so easy to work with
        wrong_date_col = "date_clear_sky"
        if wrong_date_col in df.columns:
            df = df.withColumnRenamed(wrong_date_col, "date")
        df = df.withColumnRenamed("plant_abbrev_clear_sky", "plant")

        df = self.filter_by_dates(df, start_date, end_date)
        # df = df.filter( (df.date >= start_date) & (df.date <= (end_date + timedelta(days=1))) )
        df = df.orderBy(col("date").asc())
        df = df.select(["date", "plant", "is_clear_sky_day"])
        df = df.filter(df["is_clear_sky_day"] == 1)

        df_grouped = df.groupBy("plant").agg(
            count("is_clear_sky_day").alias("clear_sky_day_count")
        )
        total_days_count = (end_date - start_date).days + 1
        df_grouped = df_grouped.withColumn("total_days_count", lit(total_days_count))

        # For completness, append rows with all plants not present
        all_plants = self.get_plants()
        all_plants_df = spark.createDataFrame(
            [(plant,) for plant in all_plants], ["plant"]
        )
        result_df = all_plants_df.join(df_grouped, on="plant", how="left")
        result_df = result_df.fillna(
            {"clear_sky_day_count": 0, "total_days_count": total_days_count}
        )

        # Add the ratio column, for display in the chart tooltips
        result_df = result_df.withColumn(
            "ratio", col("clear_sky_day_count") / col("total_days_count")
        )
        result_df = result_df.orderBy(col("plant").asc())
        return result_df.toPandas()

    def get_weather_station_time_series(
        self,
        plant,
        measurement,
        start_date,
        end_date,
    ):
        """Returns 10-minute data for all weather stations in a plant.

        Args:
            plant (str): The 3 character plant abbreviation.
            measurement (str): One of "GHI", "POA", and "BOM".
            start_date (datetime.date): The start date from which
                the data is filtered.
            end_date (datetime.date): The end date from which
                the data is filtered.

        Returns:
            (pd.DataFrame): The dataframe that contains the
                the sorted time series data of all weather
                stations in the desired plant.
        """
        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.weather_station_time_series")

        start_date = start_date.date()
        end_date = end_date.date()

        # we push our end date forward a day to see all of the end date's data
        end_date = end_date + timedelta(days=1) - timedelta(minutes=10)
        dff = df.filter(df.measurement_type == measurement)
        dff = dff.filter(dff.plant_abbrev == plant)

        dff = dff.filter(
            (dff.start_time_utc >= start_date) & (dff.start_time_utc <= end_date)
        )
        dff = dff.orderBy(col("start_time_utc").asc())

        dff = dff.filter(dff["element_name"].contains(plant))

        dff = dff.select("start_time_utc", "element_name", "measurement_type", "value")
        dff = dff.withColumnRenamed("start_time_utc", "time")

        return dff.toPandas()

    def get_self_perform_plants(self):
        """Get the plants that are self-performing.

        Returns:
            plants_arr (list): A list of the plant
                names that are self-performing.
        """
        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        try:
            df = spark.sql(f"SELECT * FROM {catalog_path}.isight.self_perform")
            df = df.filter(df["OandMVendor"] == "SPC").select("Plant")
        except Exception as e:
            print(f"Not able to retreive self perform data {e}")
            return []
        

        # Slice off any characters that got attache during the data run stage
        df = df.withColumn("Plant", df["Plant"].substr(1, 3))

        plants_arr = [row["Plant"] for row in df.collect()]
        return plants_arr

    def get_inverter_metrics(
        self,
        start_date,
        end_date,
        plant=None,
    ):
        """Get the relative deviation for the inverter metrics.

        Args:
            start_date (datetime.datetime): The start date from
                which the data is filtered.
            end_date (datetime.datetime): The end date to which
                the data is filtered.
            plant (list, optional): The plant or plants you want to return. These
                plant names are 3-characters long. If None, all plants will be
                returned and no filtering will be done. Otherwise, this param must
                be an array.

        Returns:
            dff (pd.DataFrame) A Dataframe where each row
                corresponds to an inverter in the first column,
                and the aggregated metric value between
                `start_date` and `end_date` for the remaining
                columns.
        """
        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.inverter_metrics")

        # Rename our columns so easy to work with
        if "day" in df.columns:
            df = df.withColumnRenamed("day", "date")

        start_date = start_date.date()
        end_date = end_date.date()
        df = df.filter( (df.date >= start_date) & (df.date <= end_date) )

        # filter by the plants to see
        if plant is not None and not isinstance(plant, list):
            plant = [plant]
        if plant is not None:
            df = df.filter(df.plant_abbrev.isin(plant))

        # turn vals into percentage so front-end rounding to 1 keeps them intact
        df = df.withColumn("recovery", col("recovery") * 100)

        dff = df.groupBy("element_name").agg(
            pyspark_sum("lost_energy").alias("aggr_lost_energy"),
            pyspark_sum("relative_deviation").alias("aggr_relative_deviation"),
            pyspark_sum("lost_revenue").alias("aggr_lost_revenue"),
            pyspark_avg("recovery").alias("aggr_recovery"),
        )

        dff = dff.select(
            "element_name",
            "aggr_lost_energy",
            "aggr_relative_deviation",
            "aggr_lost_revenue",
            "aggr_recovery",
        )

        return dff.toPandas()

    def get_inverter_active_power(
        self,
        inverter,
        start_date,
        end_date,
        as_pyspark=False,
    ):
        """Get an inverter's 10-minute denormalized active power data.

        Args:
            inverter (str): The name of an inverter.
            start_date (datetime.datetime): The start date from
                which the data is filtered.
            end_date (datetime.datetime): The end date to which
                the data is filtered.
            as_pyspark (bool): Determines if the output dataframe is
                a PySpark DataFrame (True), or a Pandas DataFrame
                (False).

        Returns:
            df_active_power (dataframe): Either a PySpark or Pandas
                DataFrame.
        """
        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.clean_data")

        end_date = end_date + timedelta(days=1) - timedelta(minutes=10)
        df = df.filter( (df.start_time_utc >= start_date) & (df.start_time_utc <= end_date) )
        df = df.orderBy(col("start_time_utc").asc())

        column = "ActivePower+Value"
        df_active_power = df.filter(
            (df["attribute_name"] == column) & (df["element_name"] == inverter)
        )

        df_active_power = df_active_power.select(
            "start_time_utc", "attribute_value",
        ).withColumnRenamed("attribute_value", 'ActivePower')
        return df_active_power if as_pyspark else df_active_power.toPandas()

    def get_plant_irradiance_poa_average(
        self,
        plant,
        start_date,
        end_date,
        as_pyspark=False,
    ):
        """Get an inverter's 10-minute denormalized active power data.

        Args:
            plant (str): A 3-letter plant abbreviation (eg. "ADB").
            start_date (datetime.datetime): The start date from
                which the data is filtered.
            end_date (datetime.datetime): The end date to which
                the data is filtered.
            as_pyspark (bool): Determines if the output dataframe is
                a PySpark DataFrame (True), or a Pandas DataFrame
                (False).

        Returns:
            df_poa_avg (dataframe): Either a PySpark or Pandas
                DataFrame.
        """
        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.clean_data")

        end_date = end_date + timedelta(days=1) - timedelta(minutes=10)
        df = df.filter( (df.start_time_utc >= start_date) & (df.start_time_utc <= end_date) )
        df = df.orderBy(col("start_time_utc").asc())

        df_poa_avg = df.filter((df["element_name"] == "Weather Stations") & (df["plant_abbrev"] == plant))

        df_poa_avg = df_poa_avg.select(
            "start_time_utc", "attribute_value"
        ).withColumnRenamed("attribute_value", "IrradiancePOAAverage")
        return df_poa_avg if as_pyspark else df_poa_avg.toPandas()

    def get_inverter_active_power_denormalized(
        self,
        inverter,
        start_date,
        end_date,
        as_pyspark=False,
    ):
        """Get an inverter's 10-minute denormalized active power data.

        Args:
            inverter (str): The name of an inverter.
            start_date (datetime.datetime): The start date from
                which the data is filtered.
            end_date (datetime.datetime): The end date to which
                the data is filtered.
            as_pyspark (bool): Determines if the output dataframe is
                a PySpark DataFrame (True), or a Pandas DataFrame
                (False).

        Returns:
            df_active_power (dataframe): Either a PySpark or Pandas
                DataFrame.
        """
        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.clean_data")

        end_date = end_date + timedelta(days=1) - timedelta(minutes=10)
        df = df.filter( (df.start_time_utc >= start_date) & (df.start_time_utc <= end_date) )
        df = df.orderBy(col("start_time_utc").asc())

        column = "ActivePowerNormalized"
        df_active_power = df.filter(
            (df["attribute_name"] == column) & (df["element_name"] == inverter)
        )

        df_active_power = df_active_power.select(
            "start_time_utc", "attribute_value",
        ).withColumnRenamed("attribute_value", "ActivePowerNormalized")
        return df_active_power if as_pyspark else df_active_power.toPandas()

    def get_inverter_active_power_expected(
        self,
        inverter,
        start_date,
        end_date,
        as_pyspark=False,
    ):
        """Get an inverter's 10-minute expected active power data.

        Args:
            inverter (str): The name of an inverter.
            start_date (datetime.datetime): The start date from
                which the data is filtered.
            end_date (datetime.datetime): The end date to which
                the data is filtered.
            as_pyspark (bool): Determines if the output dataframe is
                a PySpark DataFrame (True), or a Pandas DataFrame
                (False).

        Returns:
            df_active_power (dataframe): Either a PySpark or Pandas
                DataFrame.
        """
        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.clean_data")

        end_date = end_date + timedelta(days=1) - timedelta(minutes=10)
        df = df.filter( (df.start_time_utc >= start_date) & (df.start_time_utc <= end_date) )
        df = df.orderBy(col("start_time_utc").asc())

        column = "ActivePowerExpected"
        df_active_power = df.filter(
            (df["attribute_name"] == column) & (df["element_name"] == inverter)
        )

        df_active_power = df_active_power.select(
            "start_time_utc", "attribute_value",
        ).withColumnRenamed("attribute_value", "ActivePowerExpected")
        return df_active_power if as_pyspark else df_active_power.toPandas()

    def get_plant_active_power_normalized(
        self,
        plant,
        start_date,
        end_date,
        as_pyspark=False,
    ):
        """Get a Plant's Active Power Normalized for a given time frame.
        
        Args:
            plant (str): The 3-letter plant abbreviation.
            start_date (datetime.datetime): The start date from which the data
                is filtered.
            end_date (datetime.datetime): The end date to which the data is
                filtered.
            as_pyspark (bool): Determines if the output dataframe is
                a PySpark DataFrame (True), or a Pandas DataFrame
                (False).

        Returns:
            df_ap_norm (dataframe): Either a PySpark or Pandas
                DataFrame.
        """
        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.clean_data")

        end_date = end_date + timedelta(days=1) - timedelta(minutes=10)
        df = df.filter( (df.start_time_utc >= start_date) & (df.start_time_utc <= end_date) )
        df = df.orderBy(col("start_time_utc").asc())

        column = "InverterActivePowerNormalizedAverage"
        df_ap_norm = df.filter(
            (df["attribute_name"] == column) & (df["plant_abbrev"] == plant)
        )

        df_ap_norm = df_ap_norm.select(
            "start_time_utc", "plant_abbrev", "attribute_value",
        ).withColumnRenamed("attribute_value", "InverterActivePowerNormalizedAverage")
        return df_ap_norm if as_pyspark else df_ap_norm.toPandas()

    def get_inverter_performance_power_online_filter(
        self,
        inverter,
        plant,
        start_date,
        end_date,
    ):
        """Get data for the to the subcharts of the Inverter Performance Subcharts.

        This data is passed through a gradient, range and online filter.

        Args:
            inverter (str): The name of an inverter.
            plant (str): The plant that the supplied
                inverter belongs to.
            start_date (datetime.datetime): The start date from which the data
                is filtered.
            end_date (datetime.datetime): The end date to which the data is
                filtered.

        Returns:
            df_combined (pd.DataFrame): A dataframe that holds the 10-minute
                data for the active power denormalized and expected for a
                given inverter, the irradiance POA average that
                corresponds to the plant of the inverter, and the Plant's
                Active Power Normalized as well.
        """
        df_ap = self.get_inverter_active_power(inverter, start_date, end_date, as_pyspark=True)
        df_poa = self.get_plant_irradiance_poa_average(plant, start_date, end_date, as_pyspark=True)
        df_ap_denom = self.get_inverter_active_power_denormalized(inverter, start_date, end_date, as_pyspark=True)
        df_ap_exp = self.get_inverter_active_power_expected(inverter, start_date, end_date, as_pyspark=True)
        df_plant_ap = self.get_plant_active_power_normalized(plant, start_date, end_date, as_pyspark=True)

        
        df_ap = df_ap.filter("ActivePower > -1000")
        df_ap_denom = df_ap_denom.filter("ActivePowerNormalized > -1000")
        df_combined = df_poa.join(
            df_ap_denom,
            on="start_time_utc",
            how="inner"
        ).join(
            df_ap_exp,
            on="start_time_utc",
            how="inner",
        ).join(
            df_ap,
            on="start_time_utc",
            how="inner",
        ).join(
            df_plant_ap,
            on="start_time_utc",
            how="inner",
        )

        # drop the points that didn't pass our cleaning stage
        df = df_combined.toPandas()
        df.replace([-9999, 9999], np.nan, inplace=True)

        # Make sure that we only keep rows that have at least one valid measurement
        measurement_columns = [
            "IrradiancePOAAverage",
            "ActivePowerNormalized",
            "ActivePowerExpected",
            "ActivePower",
            "InverterActivePowerNormalizedAverage",
        ]
        df = self._filter_valid_measurements(df, measurement_columns)

        return df
    
    def get_inverter_performance_power_no_online_filter(
        self,
        inverter,
        plant,
        start_date,
        end_date,
    ):
        """Get data that corresponds to the subcharts of the Inverter Treemap.

        This data comes from the inverter_time_series_data table: this data has
        been cleaned with gradient and range filtering, but not online filtering.

        It is meant for display in the 10-minute time series inverter sub-chart. 

        Args:
            inverter (str): The name of an inverter.
            plant (str): The plant that the supplied
                inverter belongs to.
            start_date (datetime.datetime): The start date from which the data
                is filtered.
            end_date (datetime.datetime): The end date to which the data is
                filtered.

        Returns:
            df_pandas (pd.DataFrame): A dataframe that holds the 10-minute
                data for the active power denormalized and expected for a
                given inverter, the irradiance POA average that
                corresponds to the plant of the inverter, and the Plant's
                Active Power Normalized as well.
        """
        catalog_name = "solar"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)

        df = spark.table(f"{catalog_path}.isight.inverter_time_series_data")

        # Filter the frame by start and end dates
        start_date = start_date.date()
        end_date = end_date.date()
        end_date = end_date + timedelta(days=1) - timedelta(minutes=10)
        df = df.filter( (df.start_time_utc >= start_date) & (df.start_time_utc <= end_date) )
        df = df.filter(f"element_name = '{inverter}' or attribute_name in('InverterActivePowerNormalizedAverage', 'IrradiancePOAAverage')")

        
        # Pivot and transform to a suitable format
        pivoted_df = (df
            .filter(col("plant_abbrev") == plant)
            .groupBy("start_time_utc", "plant_abbrev")
            .pivot("attribute_name", [
                "IrradiancePOAAverage",
                "ActivePowerNormalized",
                "ActivePowerExpected",
                "ActivePower+Value",
                "InverterActivePowerNormalizedAverage",
            ])
            .agg(first("attribute_value"))
            .select(
                col("start_time_utc"),
                col("IrradiancePOAAverage"),
                col("ActivePowerNormalized"),
                col("ActivePowerExpected"),
                col("ActivePower+Value").alias("ActivePower"),
                col("plant_abbrev"),
                col("InverterActivePowerNormalizedAverage")
            )
            .orderBy("start_time_utc")
        )

        # Filter Active Power and Active Power Denormalized points
        df = df.filter("ActivePower+Value >= 0")
        df = df.filter("ActivePowerNormalized >= 0")
        
        # Transform to pandas for easier following transformations
        df_pandas = pivoted_df.toPandas()

        # Drop the -9999 and 9999s from all columns
        df_pandas.replace([-9999, 9999], np.nan, inplace=True)

        # Define columns to check for NaN values
        measurement_columns = [
            "IrradiancePOAAverage",
            "ActivePowerNormalized",
            "ActivePowerExpected",
            "ActivePower",
            "InverterActivePowerNormalizedAverage"
        ]

        # Filter out rows where all measurements are NaN
        df_pandas = self._filter_valid_measurements(df_pandas, measurement_columns)

        return df_pandas

    def get_wind_date_range(self) -> [datetime.date, datetime.date]:
        """Returns a date range to set bounds in the Wind app's calendar picker."""
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        table_array = [
            f"{catalog_path}.isight.wind_reliability_metrics",
            f"{catalog_path}.isight.wind_performance_metrics",
        ]
        return self.get_min_and_max_dates_across_tables(
            table_array=table_array,
            catalog_name=catalog_name,
        )

    def get_wind_plants(self, is_sorted=None):
        """Get a Complete list of Wind Plant Name Abbreviations.

        Args:
            is_sorted (bool): Determines if the plants are
                sorted. By default, this is False.

        Returns:
            plant_names (list): An array of plant names.
        """
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.parameters")

        project_subsets = df.filter(df.key == "PLANT_ABBREV").select("value").first()[0]
        plant_names = list(json.loads(project_subsets).values())

        if is_sorted:
            plant_names = sorted(plant_names)

        return plant_names

    def get_wind_unique_turbine_isight_attributes(self):
        """Get a list of all possible Wind iSight Attributes."""
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.parameters")
        key_to_name_values = (
            df.filter(df.key == "KEY_TO_NAME")
            .select(
                from_json(col("value"), MapType(StringType(), StringType())).alias("parsed_map")
            )
            .select(map_values(col("parsed_map")).alias("values"))
            .select(collect_list("values"))
            .first()[0]
        )
        isight_attribute_array = key_to_name_values[0]
        isight_attribute_array = sorted(isight_attribute_array)
        return isight_attribute_array

    def get_wind_component_temperature_data(
        self,
        start_date,
        end_date,
        plant=None,
        component=None,
    ):
        """Load the data for the Component Temperature chart with date filtering.

        Args:
            start_date (datetime|str): The start date to filter data (inclusive).
            end_date (datetime|str): The end date to filter data (inclusive).
            plant (str, optional): The name of the plant to filter by.
            component (str, optional): The name of the component to filter by.

        Returns:
            (pandas.DataFrame): Dataframe with filtered data between start_date and end_date.
        """
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.wind_reliability_metrics")

        df = df.withColumn("day", to_date(col("day")))
        df = df.filter((col("day") >= start_date) & (col("day") <= end_date))

        # remove all isight attributes that are not temperatures
        df = df.filter(lower(col("isight_attribute_name")).contains("temp"))

        # filter by plant if provided
        if plant not in (None, "All"):
            df = df.filter(df.plant_abbrev.isin([plant]))

        # filter by plant if provided
        if component not in (None, "All"):
            df = df.filter(df.isight_attribute_name.isin([component]))

        df = df.select(
            col("day"),
            col("element_name"),
            col("isight_attribute_name"),
            col("daily_relative_deviation"),
            col("daily_mean"),
            col("plant_abbrev")
        )

        df_temp_means_by_component = df.groupBy("element_name", "isight_attribute_name") \
            .agg(pyspark_avg("daily_mean").alias("component_avg_temp"))

        df_severity_by_component = df.groupBy("element_name", "isight_attribute_name") \
            .agg(pyspark_sum("daily_relative_deviation").alias("component_severity"))
        
        df_park_avg_temp_by_component = df.groupBy("plant_abbrev", "isight_attribute_name") \
            .agg(pyspark_avg("daily_mean").alias("park_avg_temp"))

        df_combined = df_temp_means_by_component.join(
            df_severity_by_component, 
            on=["element_name", "isight_attribute_name"], 
            how="outer"
        )
        # Extract plant_abbrev from the original dataframe for the combined dataframe
        df_plant_mapping = df.select("element_name", "plant_abbrev").distinct()
        df_combined = df_combined.join(
            df_plant_mapping,
            on="element_name",
            how="left"
        )
        df_final = df_combined.join(
            df_park_avg_temp_by_component,
            on=["plant_abbrev", "isight_attribute_name"], 
            how="outer"
        )

        # Make sure that NaNs are filled with 0 to indicate they are wrong
        null_placeholder = -99
        df_final = df_final.na.fill(null_placeholder, ["component_severity"]) \
                          .na.fill(null_placeholder, ["component_avg_temp"]) \
                          .na.fill(null_placeholder, ["park_avg_temp"])

        # Remove Negative Severity Values
        df_final = df_final[df_final["component_severity"] >= 0]

        return df_final.toPandas()

    def get_wind_component_temperature_data_by_component(
        self,
        start_date,
        end_date,
        element_name,
    ):
        """Load the temperature data for a specific turbine's components with date filtering.

        Args:
            start_date (datetime|str): The start date to filter data (inclusive).
            end_date (datetime|str): The end date to filter data (inclusive).
            element_name (str): The name of the turbine to filter by.

        Returns:
            (pandas.DataFrame): A MultiIndex DataFrame with:
                - Index: Dates
                - Columns: MultiIndex of (Component names, Metric)
                - Values: Temperature values and relative deviations
        """
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.wind_reliability_metrics")

        df = df.withColumn("day", to_date(col("day")))
        df = df.filter((col("day") >= start_date) & (col("day") <= end_date))

        # remove all isight attributes that are not temperatures
        df = df.filter(lower(col("isight_attribute_name")).contains("temp"))

        # filter by element_name
        df = df.filter(df.element_name.isin([element_name]))

        df = df.select(
            col("day"),
            col("isight_attribute_name"),
            col("daily_mean"),
            col("daily_relative_deviation")
        )

        # Convert to pandas
        df_pandas = df.toPandas()
        
        # Create separate DataFrames for each metric
        df_temp = df_pandas.pivot(
            index='day',
            columns='isight_attribute_name',
            values='daily_mean'
        )
        
        df_dev = df_pandas.pivot(
            index='day',
            columns='isight_attribute_name',
            values='daily_relative_deviation'
        )
        
        # Create MultiIndex columns
        temp_columns = pd.MultiIndex.from_product([df_temp.columns, ['temperature']])
        dev_columns = pd.MultiIndex.from_product([df_dev.columns, ['deviation']])
        
        # Set the new column names
        df_temp.columns = temp_columns
        df_dev.columns = dev_columns
        
        # Combine the DataFrames
        df_combined = pd.concat([df_temp, df_dev], axis=1)
        
        # Sort the columns for better organization
        df_combined = df_combined.sort_index(axis=1)
        
        return df_combined

    def get_wind_component_temperature_data_by_turbine(
        self,
        start_date,
        end_date,
        component_type,
    ):
        """Load the temperature data for a specific components' turbines with date filtering.

        Args:
            start_date (datetime|str): The start date to filter data (inclusive).
            end_date (datetime|str): The end date to filter data (inclusive).
            component_type (str): The name of the component to filter by.

        Returns:
            (pandas.DataFrame): A MultiIndex DataFrame with:
                - Index: Dates
                - Columns: MultiIndex of (Component names, Metric)
                - Values: Temperature values and relative deviations
        """
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.wind_reliability_metrics")

        df = df.withColumn("day", to_date(col("day")))
        df = df.filter((col("day") >= start_date) & (col("day") <= end_date))
        df = df.filter(df.isight_attribute_name.isin([component_type]))

        df = df.select(
            col("day"),
            col("element_name"),
            col("daily_mean"),
            col("daily_relative_deviation")
        )

        # Convert to pandas
        df_pandas = df.toPandas()

        # Create separate DataFrames for each metric
        df_temp = df_pandas.pivot(
            index='day',
            columns='element_name',
            values='daily_mean'
        )

        df_dev = df_pandas.pivot(
            index='day',
            columns='element_name',
            values='daily_relative_deviation'
        )

        # Create MultiIndex columns
        temp_columns = pd.MultiIndex.from_product([df_temp.columns, ['temperature']])
        dev_columns = pd.MultiIndex.from_product([df_dev.columns, ['deviation']])

        # Set the new column names
        df_temp.columns = temp_columns
        df_dev.columns = dev_columns

        # Combine the DataFrames
        df_combined = pd.concat([df_temp, df_dev], axis=1)

        # Sort the columns for better organization
        df_combined = df_combined.sort_index(axis=1)

        return df_combined

    def get_wind_power_perforamnce_treemap_data(
        self,
        start_date,
        end_date,
        plant=None,
        acknowledged_pp_turbines=None,
        under_over_perform=None,
        sort_by=None,
        is_filtered=None,
    ):
        """Generate the data for the Power Performance Chart.
        
        Args:
            start_date (date): The start date for filtering
                performance metrics.
            end_date (date): The end date for filtering
                performance metrics.
            plant (str, optional): Plant abbreviation to
                filter by. Defaults to None.
            acknowledged_pp_turbines (list, optional): List
                of turbines to exclude.
            under_over_perform (str): Either "underperforming"
                or "overperforming".
            is_filtered (bool): Determines if the data is filtered
                based on the `sort_by`.
            sort_by (str): One of the values in PERFORMANCE_METRICS.
        
        Returns:
            df_final (pandas.DataFrame): Filtered Wind Performance metrics
        """
        if is_filtered is None:
            is_filtered = False
        if acknowledged_pp_turbines is None:
            acknowledged_pp_turbines = []
        if under_over_perform is None:
            under_over_perform = "underperforming"

        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.wind_performance_metrics")

        df = df.withColumn("day", to_date(col("day")))
        df = df.filter((col("day") >= start_date) & (col("day") <= end_date))

        # filter by plant if provided
        if plant not in (None, "All"):
            df = df.filter(df.plant_abbrev.isin([plant]))
        
        # filter out acknowledged turbines
        if len(acknowledged_pp_turbines) > 0:
            df = df.filter(~df.element_name.isin(acknowledged_pp_turbines))

        df = df.na.fill(0)  # TODO: Should we keep this?
        for metric_col in ("lost_revenue", "lost_energy", "daily_relative_deviation"):
            df = df.withColumn(metric_col, col(metric_col).cast(DoubleType()))

        df = df.select(
            col("element_name").alias("Turbine"),
            col("day"),
            col("lost_revenue"),
            col("lost_energy"),
            col("daily_relative_deviation"),
        )

        df_pandas = df.toPandas()
        df_pandas = df_pandas.groupby(["Turbine"]).agg({
            "lost_revenue": "sum",
            "lost_energy": "sum",
            "daily_relative_deviation": "sum"
        }).reset_index()

        # Filter the values based on under/overperforming, and the sorting
        if is_filtered:
            if sort_by is None:
                raise Exception(
                    "If you set `is_filtered` to True, then "
                    "you must pass in a value for `sort_by.`"
                )
            column_map = {
                "-LOST-REVENUE": "lost_revenue",
                "-LOST-ENERGY": "lost_energy",
                "-SEVERITY": "daily_relative_deviation"
            }
            filter_col = column_map[sort_by]
            if "lost" in filter_col:
                if under_over_perform == "underperforming":
                    df_pandas = df_pandas[df_pandas[filter_col] >= 0]
                    ascending = False
                else:
                    df_pandas = df_pandas[df_pandas[filter_col] < 0]
                    ascending = True
            else:
                if under_over_perform == "underperforming":
                    df_pandas = df_pandas[df_pandas[filter_col] < 0]
                    ascending = True
                else:
                    df_pandas = df_pandas[df_pandas[filter_col] >= 0]
                    ascending = False

            # sort the values so the 'worst' ones are on top
            df_pandas.sort_values(by=filter_col, ascending=ascending).head(25)
        return df_pandas

    def get_wind_all_unique_turbines(self):
        """Return all available Wind Turbine names.

        Returns:
            values (list): All the unique values of the
                "element_name" column.
        """
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.wind_performance_metrics")

        temp_df = df.select(col("element_name").alias("Turbine")).distinct()
        sorted_temp_df = temp_df.orderBy("Turbine")
        values = [row.Turbine for row in
                    sorted_temp_df.select("Turbine")
                    .filter(col("Turbine").isNotNull())
                    .collect()]
        return values

    def get_wind_power_curves_data(
        self,
        start_date,
        end_date,
        turbine,
    ):
        """Generate the data for the Wind Power Curve.

        Args:
            start_date (date): The start date for filtering
                performance metrics.
            end_date (date): The end date for filtering
                performance metrics.
            turbine (str): The turbine name of interest.
                Example: "BR2-K008".
        Returns:
            df_pandas (pandas.DataFrame): The resulting dataframe.
        """
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.wind_power_curves")

        date_col = "date"
        df = df.withColumn(date_col, to_date(col(date_col)))
        df = df.filter((col(date_col) >= start_date) & (col(date_col) <= end_date))

        df = df.filter(df.element_name.isin([turbine]))

        df = df.groupBy("plant_abbrev", "element_name", "WS_BIN").agg(
            (F.sum(F.col("avg_clean_active_power") * F.col("bin_count")) / F.sum(F.col("bin_count"))).alias(f"turbine_active_power"),
            F.sum("bin_count").alias("total_turbine_bin_count"),
            (F.sum(F.col("park_avg_active_power") * F.col("park_bin_count")) / F.sum(F.col("park_bin_count"))).alias("park_avg_active_power"),
            F.sum("park_bin_count").alias("park_avg_bin_count"),
            F.first("warranted_power").alias("warranted_power")
        )
        return df.toPandas()

    def gen_wind_yaw_error_data_by_turbine(self, start_date, end_date):
        """Fetch the Yaw Error and Efficiency data.
        
        This method fetches data from two tables to form the
        dataset necessary for creating the Yaw Chart in the UI.

        Args:
            start_date (datetime.datetime): This filters the data to only
                include dates on or after this date. This is inclusive.
            end_date (datetime.datetime): This filters the data to only
                include dates on or before this date. This is inclusive.
        
        Returns:
            df_result (pd.DataFrame): A dataframe with the following
                schema:
                    - index: The Project-Turbine names (eg. BR2-K020)
                    - "aggr_yaw_error" (column): An statistical descriptive
                        for the Yaw Error across all the dates selected.
                    - "aggr_efficiency" (column): The mean of the daily
                        efficiency values across the selected dates,
                        per turbine.
        """
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.wind_daily_yaw_error")
        
        df = df.filter((df.date >= start_date) & (df.date <= end_date))
        
        pivoted_df = df.groupBy("date") \
            .pivot("element_name") \
            .agg(F.first("yaw_error"))
        
        pivoted_df = pivoted_df.orderBy("date")
        
        pandas_df = pivoted_df.toPandas()
        pandas_df.set_index('date', inplace=True)

        mean_by_turbine = pandas_df.mean(skipna=True)
        mean_by_turbine = mean_by_turbine.to_frame()

        # pull in the efficiency
        df = spark.table(f"{catalog_path}.isight.wind_performance_metrics")
        df = df.select(
            col("element_name"),
            col("day").alias("date"),
            col("mean_efficiency"),
        )
        df = df.filter((df.date >= start_date) & (df.date <= end_date))
        pivoted_df = df.groupBy("date") \
            .pivot("element_name") \
            .agg(pyspark_avg("mean_efficiency"))
        pivoted_df = pivoted_df.orderBy("date")

        df_pandas_eff = pivoted_df.toPandas()
        df_pandas_eff.set_index('date', inplace=True)
        df_pandas_eff_by_turbine = df_pandas_eff.mean()

        df_pandas_eff_by_turbine = df_pandas_eff_by_turbine.to_frame()
        
        # Rename the columns
        mean_by_turbine = mean_by_turbine.rename(columns={0: "aggr_yaw_error"})
        df_pandas_eff_by_turbine = df_pandas_eff_by_turbine.rename(columns={0: "aggr_efficiency"})

        # Join the dataframes on their index
        df_result = mean_by_turbine.join(df_pandas_eff_by_turbine, how="outer")
        df_result = df_result.fillna(0)
        return df_result

    def get_wind_turbine_fault_codes(self):
        """Get all unique turbine fault code pairs.

        Returns:
            turbine_fault_codes (list): ...
        """
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.wind_daily_turbine_fault")
        df = df.withColumn("TurbineFaultCode", concat(col("Turbine"), lit(TURBINE_FAULT_DELIM), col("FaultCode")))

        temp_df = df.select("Turbine", "FaultCode", "TurbineFaultCode").distinct()
        sorted_temp_df = temp_df.orderBy("Turbine", col("FaultCode").cast("int"))
        turbine_fault_codes = [row.TurbineFaultCode for row in 
                            sorted_temp_df.select("TurbineFaultCode")
                            .filter(col("TurbineFaultCode").isNotNull())
                            .collect()]
        return turbine_fault_codes

    def get_wind_fault_code_data(
        self,
        start_date,
        end_date,
        ack_turbine_fault_pairs=None,
        ack_fault_descr_pairs=None,
        filter_fault_descr_pairs=None,
    ):
        """Get fault code data for wind turbines.

        Retrieves fault code data from the wind_daily_turbine_fault
        table for the specified date range.

        Args:
            start_date (date): The start date to filter data from.
            end_date (date): The end date to filter data to.
            ack_turbine_fault_pairs (list): A list of tuples containing
                turbine and fault code pairs to acknowledge. They might
                look "BR2-K001 | 10".
            ack_fault_descr_pairs (list): A list of strings containing
                fault description pairs to acknowledge. They might
                look "5 - REPAIR".
            filter_fault_descr_pairs (list): The fault descriptions
                to keep. See `ack_fault_descr_pairs` for the format.

        Returns:
            df_pandas (pandas.DataFrame): A dataframe containing fault code data
                for wind turbines between the specified dates.
        """
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.wind_daily_turbine_fault")

        df = df.filter((df.Date >= start_date) & (df.Date <= end_date))

        # filter out fault descriptions
        if filter_fault_descr_pairs is None:
            filter_fault_descr_pairs = []
        if len(filter_fault_descr_pairs) > 0:
            descriptions_to_filter = [pair.split(DESCRIPTION_CODE_DELIM)[1] for pair in filter_fault_descr_pairs]
            df = df.filter(df.Description.isin(descriptions_to_filter))

        # filter out acknowledged turbine-fault pairs
        if ack_turbine_fault_pairs is None:
            ack_turbine_fault_pairs = []
        if len(ack_turbine_fault_pairs) > 0:
            df = df.withColumn("TurbineFaultCode", concat(col("Turbine"), lit(TURBINE_FAULT_DELIM), col("FaultCode")))
            df = df.filter(~df.TurbineFaultCode.isin(ack_turbine_fault_pairs))

        # filter out acknowledged fault description pairs
        if ack_fault_descr_pairs is None:
            ack_fault_descr_pairs = []
        if len(ack_fault_descr_pairs) > 0:
            descriptions_to_filter = [pair.split(DESCRIPTION_CODE_DELIM)[1] for pair in ack_fault_descr_pairs]
            df = df.filter(~df.Description.isin(descriptions_to_filter))

        df_pandas = df.toPandas()
        return df_pandas

    def get_wind_fault_code_description_options(self):
        """Get Fault Code Descriptions options used for Acknowledge Dropdowns.
        
        The option labels are of the form '{code} | {description}'. Eg. '5 | REPAIR'.

        Returns:
            options (list): An array of labels ready for a Plotly dcc.Dropdown's
                options parameter.
        """
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.fault_description_mapping")

        df = df.withColumn("CodeDescription", concat(col("Code"), lit(DESCRIPTION_CODE_DELIM), col("Description")))
        temp_df = df.select("Code", "Description", "CodeDescription").distinct()
        sorted_temp_df = temp_df.orderBy(col("Code").cast("int"), "Description")
        options = [row.CodeDescription for row in
                            sorted_temp_df.select("CodeDescription")
                            .filter(col("CodeDescription").isNotNull())
                            .collect()]
        return options

    def get_wind_fault_downtime_lost_energy(
        self,
        start_date,
        end_date,
        plant,
        ack_turbine_fault_pairs=None,
        ack_fault_descr_pairs=None,
        filter_fault_descr_pairs=None,
    ):
        """Get the Fault Metrics for the Pulse and Pareto Charts.

        Args:
            start_date (date): The start date to filter data from.
            end_date (date): The end date to filter data to.
            plant (str): The 3-letter plant abbreviation.
            ack_turbine_fault_pairs (list): A list of tuples containing
                turbine and fault code pairs to acknowledge. They might
                look "ODK-K001 | 5" or "BR2-K001 | 10".
            ack_fault_descr_pairs (list): A list of strings containing
                fault description pairs to acknowledge. They might
                look "5 - REPAIR".
            filter_fault_descr_pairs (list): The fault descriptions
                to keep. See `ack_fault_descr_pairs` for the format.

        Returns:
            df_pandas (pandas.DataFrame): A dataframe containing the
                data pertinent to the Pulse and Pareto Chart.
        """
        catalog_name = "wind"
        catalog_path = self._get_catalog_path(catalog_name)
        spark = self.get_session(catalog_name)
        df = spark.table(f"{catalog_path}.isight.wind_downtime_lost_energy")

        df = df.filter((df.AdjustedStartDateTime >= start_date) & (df.AdjustedEndDateTime <= end_date))
        df = df.filter((df.StartDateTime >= start_date) & (df.EndDateTime <= end_date))

        if plant not in ("all", "All", None):
            df = df.filter(df.plant_abbrev == plant)

        df = df.select(
            col("plant_abbrev"),
            col("element_name").alias("Turbine"),
            col("FaultCode"),
            col("AdjustedStartDateTime"),
            col("AdjustedEndDateTime"),
            col("StartDateTime"),
            col("EndDateTime"),
            col("AdjustedDuration"),
            col("LostRevenue"),
            col("LostEnergy"),
            col("Description"),
        )

        # filter out fault descriptions
        if filter_fault_descr_pairs is None:
            filter_fault_descr_pairs = []
        if len(filter_fault_descr_pairs) > 0:
            descriptions_to_filter = [pair.split(DESCRIPTION_CODE_DELIM)[1] for pair in filter_fault_descr_pairs]
            df = df.filter(df.Description.isin(descriptions_to_filter))

        # filter out acknowledged turbine-fault pairs
        if ack_turbine_fault_pairs is None:
            ack_turbine_fault_pairs = []
        if len(ack_turbine_fault_pairs) > 0:
            df = df.withColumn("TurbineFaultCode", concat(col("Turbine"), lit(TURBINE_FAULT_DELIM), col("FaultCode")))
            df = df.filter(~df.TurbineFaultCode.isin(ack_turbine_fault_pairs))

        # filter out acknowledged fault description pairs
        if ack_fault_descr_pairs is None:
            ack_fault_descr_pairs = []
        if len(ack_fault_descr_pairs) > 0:
            descriptions_to_filter = [pair.split(DESCRIPTION_CODE_DELIM)[1] for pair in ack_fault_descr_pairs]
            df = df.filter(~df.Description.isin(descriptions_to_filter))

        df_pandas = df.toPandas()

        for colname in ["AdjustedStartDateTime", "AdjustedEndDateTime"]:
            df_pandas[colname] = pd.to_datetime(df_pandas[colname])

        return df_pandas
