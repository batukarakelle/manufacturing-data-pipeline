"""

Generate reproducible synthetic manufacturing equipment datasets.

"""

import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


RANDOM_SEED = 14
TOTAL_RECORDS = 100
CSV_RECORDS = 70


def generate_measurements() -> list[dict]:
    """
    Generate reproducible equipment measurements.

    Returns:
        A list of synthetic measurement records.
    """
    rng = random.Random(RANDOM_SEED)

    equipment_ids = ["EQ-01", "EQ-02", "EQ-03"]
    start_time = datetime(2026, 10, 8, 8, 0, tzinfo=timezone.utc)

    measurements = []

    for i in range(TOTAL_RECORDS):
        measurement = {
            "measurement_id": f"M{i+1:03d}",
            "equipment_id": rng.choice(equipment_ids),
            "timestamp": (
                start_time + timedelta(minutes=i * 5)
            ).isoformat(),
            "temperature_c": round(rng.uniform(20.0, 25.0), 2),
            "vibration_mm_s": round(rng.uniform(0.5, 1.5), 2)
        }

        measurements.append(measurement)

    return measurements


def inject_anomalies(measurements: list[dict]) -> None:
    """
    Inject controlled data-quality issues into measurement records.

    Modifies the input records in place.

    Args:
        measurements: Generated measurement records.
    """
    measurements[4]["equipment_id"] = None
    measurements[14]["timestamp"] = "invalid-timestamp"
    measurements[24]["temperature_c"] = "not_a_number"
    measurements[79]["measurement_id"] = measurements[1]["measurement_id"]


def export_csv(measurements: list[dict], output_dir: Path) -> None:
    """
    Export the first 70 measurements using the CSV source schema.

    Args:
        measurements: Generated measurement records.
        output_dir: Directory where the CSV file is saved.
    """
    csv_path = output_dir / "measurements.csv"

    fieldnames = [
        "measurement_id",
        "equipment_id",
        "timestamp",
        "temperature_c",
        "vibration_mm_s"
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(measurements[:CSV_RECORDS])

    print(f"Saved {CSV_RECORDS} measurements to CSV.")


def export_json(measurements: list[dict], output_dir: Path) -> None:
    """
    Export remaining measurements with an alternative JSON schema.

    Convert UTC timestamps to a +02:00 offset.

    Args:
        measurements: Generated measurement records.
        output_dir: Directory where the JSON file is saved.
    """
    json_path = output_dir / "measurements.json"
    json_measurements = []

    for measurement in measurements[CSV_RECORDS:]:
        json_timestamp = datetime.fromisoformat(
            measurement["timestamp"]
        ).astimezone(
            timezone(timedelta(hours=2))
        ).isoformat()

        json_record = {
            "measurementId": measurement["measurement_id"],
            "machineId": measurement["equipment_id"],
            "recordedAt": json_timestamp,
            "tempC": measurement["temperature_c"],
            "vibrationMmS": measurement["vibration_mm_s"]
        }

        json_measurements.append(json_record)

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(json_measurements, file, indent=2)

    print(f"Saved {len(json_measurements)} measurements to JSON.")


def main() -> None:
    """
    Generate synthetic datasets with controlled validation errors.
    """
    
    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "data" / "raw"

    output_dir.mkdir(parents=True, exist_ok=True)

    measurements = generate_measurements()
    inject_anomalies(measurements)

    print(f"Generated {len(measurements)} measurements.")

    export_csv(measurements, output_dir)
    export_json(measurements, output_dir)


if __name__ == "__main__":
    main()
