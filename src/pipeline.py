"""
Extract and standardize manufacturing equipment measurements.

"""

from pathlib import Path
import pandas as pd
import sqlite3
import json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


def extract_data():
    """
    Read raw equipment measurements from CSV and JSON files.
    """
    csv_path = RAW_DATA_DIR / "measurements.csv"
    json_path = RAW_DATA_DIR / "measurements.json"

    csv_df = pd.read_csv(
        csv_path,
        dtype=str,
        keep_default_na=False
    )

    json_df = pd.read_json(
        json_path,
        dtype=False
    )

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

        missing_input = (
            original.isna()
            | original.astype("string").str.strip().eq("").fillna(False)
        )

        boolean_input = original.map(
            lambda value: pd.api.types.is_bool_dtype(type(value))
        )

        converted = pd.to_numeric(
            original.mask(missing_input | boolean_input),
            errors="coerce"
        )

        non_finite = converted.isin([
            float("inf"),
            float("-inf")
        ])

        result[f"invalid_{column}"] = (
            ~missing_input
            & (boolean_input | converted.isna() | non_finite)
        )

        result[column] = converted.mask(non_finite)


    raw_timestamp = result["timestamp"].astype("string")

    missing_timestamp_input = (
    raw_timestamp.isna()
    | raw_timestamp.str.strip().eq("").fillna(False)
)

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
    ~missing_timestamp_input & parsed_timestamp.isna()
    )

    result["timestamp_utc"] = parsed_timestamp

    return result.drop(columns=["timestamp"])



def validate_data(
    df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Validate measurements and separate accepted and rejected records.

    Apply rejection rules in priority order:
    missing values, invalid timestamps, invalid numeric values,
    and duplicate measurement IDs.

    Only the first valid occurrence of an ID is accepted.

    Args:
        df: Standardized measurements with validation flags.

    Returns:
        A tuple containing accepted and rejected DataFrames.
        Rejected records include a primary rejection reason.
    """
    result = df.reset_index(drop=True).copy()

    missing_text = pd.Series(False, index=result.index)

    for column in ["measurement_id", "equipment_id"]:
        missing_text |= (
            result[column].isna()
            | result[column].astype("string").str.strip().eq("").fillna(False)
        )

    missing_timestamp = (
        result["timestamp_utc"].isna()
        & ~result["invalid_timestamp"]
    )

    missing_numeric = (
        (
            result["temperature_c"].isna()
            & ~result["invalid_temperature_c"]
        )
        | (
            result["vibration_mm_s"].isna()
            & ~result["invalid_vibration_mm_s"]
        )
    )

    missing = missing_text | missing_timestamp | missing_numeric

    invalid_numeric = (
        result["invalid_temperature_c"]
        | result["invalid_vibration_mm_s"]
    )

    reasons = pd.Series(
        pd.NA,
        index=result.index,
        dtype="string"
    )

    reasons.loc[missing] = "missing_value"

    reasons.loc[
        reasons.isna() & result["invalid_timestamp"]
    ] = "invalid_timestamp"

    reasons.loc[
        reasons.isna() & invalid_numeric
    ] = "invalid_numeric"

    candidates = result.loc[reasons.isna()]

    duplicate_indices = candidates.index[
        candidates.duplicated(
            subset=["measurement_id"],
            keep="first"
        )
    ]

    reasons.loc[duplicate_indices] = "duplicate_measurement_id"

    result["rejection_reason"] = reasons

    accepted_df = result.loc[reasons.isna()].copy()
    rejected_df = result.loc[reasons.notna()].copy()

    return accepted_df, rejected_df





def load_data(accepted_df: pd.DataFrame) -> int:
    """
    Replace stored measurements with validated records.

    Args:
        accepted_df: Validated equipment measurements.

    Returns:
        Number of records inserted into SQLite.
    """
    output_dir = PROJECT_ROOT / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = output_dir / "equipment_measurements.db"

    records = [
        (
            row.measurement_id,
            row.equipment_id,
            row.timestamp_utc.isoformat(),
            float(row.temperature_c),
            float(row.vibration_mm_s),
        )
        for row in accepted_df.itertuples(index=False)
    ]

    connection = sqlite3.connect(db_path)

    try:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS measurements (
                    measurement_id TEXT PRIMARY KEY,
                    equipment_id TEXT NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    temperature_c REAL NOT NULL,
                    vibration_mm_s REAL NOT NULL
                )
            """)

            connection.execute("DELETE FROM measurements")

            connection.executemany(
                """
                INSERT INTO measurements (
                    measurement_id,
                    equipment_id,
                    timestamp_utc,
                    temperature_c,
                    vibration_mm_s
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                records
            )
    finally:
        connection.close()

    return len(records)




def build_quality_report(accepted_df: pd.DataFrame, rejected_df: pd.DataFrame) -> dict:
    """
    Summarize accepted records and validation rejections.

    Args:
        accepted_df: Measurements that passed validation.
        rejected_df: Measurements with rejection reasons.

    Returns:
        A dictionary containing record counts and rejection statistics.
    """
    rejection_counts = rejected_df["rejection_reason"].value_counts()

    report = {
        "total_input_records": len(accepted_df) + len(rejected_df),
        "accepted_records": len(accepted_df),
        "rejected_records": len(rejected_df),
        "rejection_counts": {
            "missing_value": int(rejection_counts.get("missing_value", 0)),
            "invalid_timestamp": int(rejection_counts.get("invalid_timestamp", 0)),
            "invalid_numeric": int(rejection_counts.get("invalid_numeric", 0)),
            "duplicate_measurement_id": int(
                rejection_counts.get("duplicate_measurement_id", 0)
            )
        }
    }

    return report



def save_quality_report(report: dict) -> Path:
    """
    Save the data-quality report as a JSON file.

    Args:
        report: Dictionary containing validation statistics.

    Returns:
        Path to the generated JSON report.
    """
    output_dir = PROJECT_ROOT / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "quality_report.json"

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)
        file.write("\n")

    return report_path




def main():
    """
    Run extraction and schema standardization.
    """
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

    accepted_df, rejected_df = validate_data(transformed_df)

    print("\nValidation results:")
    print(f"Accepted: {len(accepted_df)}")
    print(f"Rejected: {len(rejected_df)}")

    print("\nRejected records:")
    print(
        rejected_df[
            ["measurement_id", "rejection_reason"]
        ].to_string(index=False)
    )

    loaded_count = load_data(accepted_df)

    print("\nSQLite load results:")
    print(f"Inserted records: {loaded_count}")
    
    quality_report = build_quality_report(accepted_df, rejected_df)

    report_path = save_quality_report(quality_report)

    print("\nData quality report:")
    print(json.dumps(quality_report, indent=2))
    print(f"\nReport saved to: {report_path}")

if __name__ == "__main__":
    main()

