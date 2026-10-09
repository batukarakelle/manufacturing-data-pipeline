"""
Extract and standardize manufacturing equipment measurements.
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


def extract_data():
    """Read raw equipment measurements from CSV and JSON files."""
    csv_path = RAW_DATA_DIR / "measurements.csv"
    json_path = RAW_DATA_DIR / "measurements.json"

    csv_df = pd.read_csv(csv_path)
    json_df = pd.read_json(json_path)

    return csv_df, json_df


def standardize_schema(csv_df, json_df):

    """
    Rename source columns and combine both datasets.

    Args:
        csv_df: Raw CSV measurements.
        json_df: Raw JSON measurements.

    Returns:
        A combined DataFrame with standardized column names.
    """

    json_column_mapping = {
        "measurementId": "measurement_id",
        "machineId": "equipment_id",
        "recordedAt": "timestamp",
        "tempC": "temperature_c",
        "vibrationMmS": "vibration_mm_s"
    }

    standard_columns = [
        "measurement_id",
        "equipment_id",
        "timestamp",
        "temperature_c",
        "vibration_mm_s"
    ]

    csv_standard = csv_df[standard_columns].copy()

    json_standard = json_df.rename(
        columns=json_column_mapping
    )[standard_columns].copy()

    combined_df = pd.concat(
        [csv_standard, json_standard],
        ignore_index=True
    )

    return combined_df



def standardize_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert measurements to numeric values and timestamps to UTC.

    Preserve indicators of malformed values for later validation.

    Args:
        df: Combined DataFrame with standardized column names.

    Returns:
        DataFrame with converted values and invalid-input flags.
    """
    result = df.copy()

    numeric_columns = ["temperature_c", "vibration_mm_s"]

    
    for column in numeric_columns:
        original = result[column]
        converted = pd.to_numeric(original, errors="coerce")

        non_finite = converted.isin([
            float("inf"),
            float("-inf")
        ])

        result[f"invalid_{column}"] = (
            original.notna()
            & (converted.isna() | non_finite)
        )

        result[column] = converted.mask(non_finite)

    raw_timestamp = result["timestamp"].astype("string")

    has_timezone = raw_timestamp.str.contains(
        r"(?:Z|[+-]\d{2}:\d{2})$",
        case=False,
        na=False,
    )

    parsed_timestamp = pd.to_datetime(
        raw_timestamp.where(has_timezone),
        errors="coerce",
        utc=True,
        format="mixed",
    )

    result["invalid_timestamp"] = (
        raw_timestamp.notna() & parsed_timestamp.isna()
    )

    result["timestamp_utc"] = parsed_timestamp

    return result.drop(columns=["timestamp"])



def main():
    """Run extraction and schema standardization."""
    csv_df, json_df = extract_data()

    print(f"CSV records: {len(csv_df)}")
    print(f"JSON records: {len(json_df)}")
    print(f"Total records: {len(csv_df) + len(json_df)}")

    print("\nCSV columns:")
    print(csv_df.columns.tolist())

    print("\nJSON columns:")
    print(json_df.columns.tolist())

    combined_df = standardize_schema(csv_df, json_df)

    print("\nAfter schema standardization:")
    print(f"Combined records: {len(combined_df)}")
    print(f"Columns: {combined_df.columns.tolist()}")

    print("\nFirst 5 records:")
    print(combined_df.head())

    transformed_df = standardize_types(combined_df)

    print("\nAfter type standardization:")
    print(transformed_df.dtypes)

    print("\nSelected transformation checks:")
    selected_ids = ["M015", "M025", "M071"]

    selected_columns = [
        "measurement_id",
        "timestamp_utc",
        "temperature_c",
        "invalid_timestamp",
        "invalid_temperature_c",
    ]

    print(
        transformed_df.loc[
            transformed_df["measurement_id"].isin(selected_ids),
            selected_columns,
        ].to_string(index=False)
    )

if __name__ == "__main__":
    main()

