
import random
from datetime import datetime, timedelta, timezone
import csv
from pathlib import Path
import json

# Configuration
rng = random.Random(14)

equipment_ids = ["EQ-01", "EQ-02", "EQ-03"]
start_time = datetime(2026, 10, 8, 8, 0, tzinfo=timezone.utc)

measurements = []

# Generate 10 synthetic measurements
for i in range(100):
    measurement_id = f"M{i+1:03d}"

    equipment_id = rng.choice(equipment_ids)

    timestamp = (
        start_time + timedelta(minutes=i * 5)
    ).isoformat()

    temperature = round(rng.uniform(20.0, 25.0), 2)
    vibration = round(rng.uniform(0.5, 1.5), 2)

    measurement = {
        "measurement_id": measurement_id,
        "equipment_id": equipment_id,
        "timestamp": timestamp,
        "temperature_c": temperature,
        "vibration_mm_s": vibration
    }

    measurements.append(measurement)

    
# Inject controlled data-quality anomalies

# Missing equipment ID (CSV)
measurements[4]["equipment_id"] = None

# Invalid timestamp (CSV)
measurements[14]["timestamp"] = "invalid-timestamp"

# Invalid numeric value (CSV)
measurements[24]["temperature_c"] = "not_a_number"

# Duplicate measurement ID across CSV and JSON
measurements[79]["measurement_id"] = measurements[1]["measurement_id"]


# Display generated records
print(f"Generated {len(measurements)} measurements.")


# Define output path
project_root = Path(__file__).resolve().parents[1]
csv_path = project_root / "data" / "raw" / "measurements.csv"

# Create output directory if it does not exist
csv_path.parent.mkdir(parents=True, exist_ok=True)

# Define CSV columns
fieldnames = [
    "measurement_id",
    "equipment_id",
    "timestamp",
    "temperature_c",
    "vibration_mm_s"
]

# Export the first 70 measurements
with csv_path.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)

    writer.writeheader()
    writer.writerows(measurements[:70])

print("Saved 70 measurements to CSV.")


# Define JSON output path
json_path = project_root / "data" / "raw" / "measurements.json"

# Convert remaining measurements to JSON source schema
json_measurements = []

for measurement in measurements[70:]:
    # Represent the same timestamp using a +02:00 offset
    json_timestamp = datetime.fromisoformat(
        measurement["timestamp"]
    ).astimezone(timezone(timedelta(hours=2))).isoformat()

    json_record = {
        "measurementId": measurement["measurement_id"],
        "machineId": measurement["equipment_id"],
        "recordedAt": json_timestamp,
        "tempC": measurement["temperature_c"],
        "vibrationMmS": measurement["vibration_mm_s"]
    }

    json_measurements.append(json_record)

# Export JSON measurements
with json_path.open("w", encoding="utf-8") as file:
    json.dump(json_measurements, file, indent=2)

print("Saved 30 measurements to JSON.")

