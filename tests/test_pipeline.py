"""

Tests for equipment measurement validation.

"""

import json
import sqlite3
import pandas as pd
import pytest
import json
from src import pipeline
from src.pipeline import (
    extract_data,
    standardize_schema,
    standardize_types,
    validate_data,
)


def test_expected_dataset_results():
    """
    Verify rejection counts for the synthetic dataset.
    """
    csv_df, json_df = extract_data()
    combined = standardize_schema(csv_df, json_df)
    transformed = standardize_types(combined)

    accepted, rejected = validate_data(transformed)

    assert len(accepted) == 96
    assert len(rejected) == 4

    expected_reasons = {
        "missing_value": 1,
        "invalid_timestamp": 1,
        "invalid_numeric": 1,
        "duplicate_measurement_id": 1,
    }

    assert rejected["rejection_reason"].value_counts().to_dict() == expected_reasons


def test_first_valid_occurrence_wins():
    """
    Accept a valid record following an invalid record with the same ID.
    """
    records = [
        {
            "measurement_id": "M101",
            "equipment_id": "EQ-01",
            "timestamp": "invalid-timestamp",
            "temperature_c": "22.0",
            "vibration_mm_s": "0.8",
        },
        {
            "measurement_id": "M101",
            "equipment_id": "EQ-01",
            "timestamp": "2026-10-08T08:00:00Z",
            "temperature_c": "23.0",
            "vibration_mm_s": "0.9",
        },
        {
            "measurement_id": "M101",
            "equipment_id": "EQ-01",
            "timestamp": "2026-10-08T08:05:00Z",
            "temperature_c": "24.0",
            "vibration_mm_s": "1.0",
        },
    ]

    transformed = standardize_types(pd.DataFrame(records))
    accepted, rejected = validate_data(transformed)

    assert len(accepted) == 1
    assert accepted.iloc[0]["temperature_c"] == 23.0

    assert rejected["rejection_reason"].tolist() == [
        "invalid_timestamp",
        "duplicate_measurement_id",
    ]


@pytest.mark.parametrize(
    "invalid_value",
    ["inf", "-inf", "1e400", "NaN"],
)
def test_non_finite_values_are_rejected(invalid_value):
    """
    Reject non-finite temperature measurements.
    """
    record = {
        "measurement_id": "M200",
        "equipment_id": "EQ-01",
        "timestamp": "2026-10-08T08:00:00Z",
        "temperature_c": invalid_value,
        "vibration_mm_s": "0.8",
    }

    transformed = standardize_types(pd.DataFrame([record]))
    accepted, rejected = validate_data(transformed)

    assert len(accepted) == 0
    assert rejected.iloc[0]["rejection_reason"] == "invalid_numeric"




    
@pytest.mark.parametrize("boolean_value", [True, False])
def test_boolean_measurements_are_rejected(boolean_value):
    """
    Reject boolean values used as numeric measurements.
    """
    record = {
        "measurement_id": "M300",
        "equipment_id": "EQ-01",
        "timestamp": "2026-10-08T08:00:00Z",
        "temperature_c": boolean_value,
        "vibration_mm_s": "0.8",
    }

    transformed = standardize_types(pd.DataFrame([record]))
    accepted, rejected = validate_data(transformed)

    assert len(accepted) == 0
    assert rejected.iloc[0]["rejection_reason"] == "invalid_numeric"




@pytest.mark.parametrize("boolean_value", [True, False])
def test_json_boolean_is_rejected(tmp_path, monkeypatch, boolean_value):
    """
    Reject boolean measurements loaded from a JSON file.
    """
    csv_path = tmp_path / "measurements.csv"
    json_path = tmp_path / "measurements.json"

    csv_path.write_text(
        "measurement_id,equipment_id,timestamp,temperature_c,vibration_mm_s\n"
        "M001,EQ-01,2026-10-08T08:00:00Z,22.5,0.8\n",
        encoding="utf-8"
    )

    json_records = [
        {
            "measurementId": "M002",
            "machineId": "EQ-02",
            "recordedAt": "2026-10-08T10:05:00+02:00",
            "tempC": boolean_value,
            "vibrationMmS": 0.9
        }
    ]

    json_path.write_text(
        json.dumps(json_records),
        encoding="utf-8"
    )

    monkeypatch.setattr(pipeline, "RAW_DATA_DIR", tmp_path)

    csv_df, json_df = pipeline.extract_data()
    combined = pipeline.standardize_schema(csv_df, json_df)
    transformed = pipeline.standardize_types(combined)
    accepted, rejected = pipeline.validate_data(transformed)

    assert len(accepted) == 1
    assert accepted.iloc[0]["measurement_id"] == "M001"

    assert len(rejected) == 1
    assert rejected.iloc[0]["measurement_id"] == "M002"
    assert rejected.iloc[0]["rejection_reason"] == "invalid_numeric"




def test_sqlite_load_is_idempotent(tmp_path, monkeypatch):
    """
    Verify that repeated loads do not duplicate stored measurements.
    """
    csv_df, json_df = pipeline.extract_data()
    combined_df = pipeline.standardize_schema(csv_df, json_df)
    transformed_df = pipeline.standardize_types(combined_df)
    accepted_df, _ = pipeline.validate_data(transformed_df)

    monkeypatch.setattr(pipeline, "PROJECT_ROOT", tmp_path)

    first_load = pipeline.load_data(accepted_df)
    second_load = pipeline.load_data(accepted_df)

    db_path = (
        tmp_path / "data" / "processed" / "equipment_measurements.db"
    )

    with sqlite3.connect(db_path) as connection:
        stored_count = connection.execute(
            "SELECT COUNT(*) FROM measurements"
        ).fetchone()[0]

        unique_count = connection.execute(
            "SELECT COUNT(DISTINCT measurement_id) FROM measurements"
        ).fetchone()[0]

    assert first_load == 96
    assert second_load == 96
    assert stored_count == 96
    assert unique_count == 96




def test_quality_report(tmp_path, monkeypatch):
    """
    Verify report statistics and saved JSON content.
    """
    csv_df, json_df = pipeline.extract_data()
    combined_df = pipeline.standardize_schema(csv_df, json_df)
    transformed_df = pipeline.standardize_types(combined_df)

    accepted_df, rejected_df = pipeline.validate_data(transformed_df)

    report = pipeline.build_quality_report(
        accepted_df, rejected_df
    )

    expected_report = {
        "total_input_records": 100,
        "accepted_records": 96,
        "rejected_records": 4,
        "rejection_counts": {
            "missing_value": 1,
            "invalid_timestamp": 1,
            "invalid_numeric": 1,
            "duplicate_measurement_id": 1
        }
    }

    assert report == expected_report

    monkeypatch.setattr(pipeline, "PROJECT_ROOT", tmp_path)

    report_path = pipeline.save_quality_report(report)

    assert report_path.exists()

    with report_path.open("r", encoding="utf-8") as file:
        saved_report = json.load(file)

    assert saved_report == expected_report
