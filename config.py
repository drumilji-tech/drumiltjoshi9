"""Configuration settings for different environments.

Note that we deliberaltely are prepending our environment variables with "ALT_".
This is to avoid conflicts with the Databricks environment variables.
"""

ENVIRONMENTS = {
    "prod": {
        "ENV_TITLE": "",
        "ENV_DESCRIPTION": "This is the most up-to-date version of the iSight app.",
        "ALT_DATABRICKS_CATALOG_WIND": "southernpower_dv",
        "ALT_DATABRICKS_CATALOG_SOLAR": "southernpower",
    },
    "dev": {
        "ENV_TITLE": "Development",
        "ENV_DESCRIPTION": "This is the development version of the iSight app.",
        "ALT_DATABRICKS_CATALOG_WIND": "southernpower_dv",
        "ALT_DATABRICKS_CATALOG_SOLAR": "southernpower_dv",
    }
}

ENV_CONNECTION_KEYS_MAPPING = {
    "southernpower_dv": {
        "ALT_DATABRICKS_HOST": "https://adb-5068312773981457.17.azuredatabricks.net/",
        "ALT_DATABRICKS_CLIENT_ID": "00e96b4b-b8c0-46bc-9fb5-c2fb5b673c9c",
        "ALT_DATABRICKS_CLIENT_SECRET": "dosecab3210704bab38ca806c7d302e7f230",
    },
    "southernpower_ua": {
        "ALT_DATABRICKS_HOST": "https://adb-4261052631343710.10.azuredatabricks.net/",
        "ALT_DATABRICKS_CLIENT_ID": "a81378a6-de6f-46a9-8d0d-471032cb315f",
        "ALT_DATABRICKS_CLIENT_SECRET": "doseace901b953d21eb486218c71ffd19ef1",
    },
    "southernpower": {
        "ALT_DATABRICKS_HOST": "https://adb-2611872975370758.18.azuredatabricks.net/",
        "ALT_DATABRICKS_CLIENT_ID": "97e944c3-d046-4afc-9b15-1786f6a88b3a",
        "ALT_DATABRICKS_CLIENT_SECRET": "dose09284385fdeed4b353096db65a5b865d",
    }
}

# Default environment
CURRENT_ENV = "dev"


def get_environment_config():
    """Get the configuration for the current environment."""
    output = ENVIRONMENTS[CURRENT_ENV]
    wind_catalog = output["ALT_DATABRICKS_CATALOG_WIND"]
    solar_catalog = output["ALT_DATABRICKS_CATALOG_SOLAR"]
    for key, value in ENV_CONNECTION_KEYS_MAPPING[wind_catalog].items():
        output["WIND_" + key] = value
    for key, value in ENV_CONNECTION_KEYS_MAPPING[solar_catalog].items():
        output["SOLAR_" + key] = value
    return output
