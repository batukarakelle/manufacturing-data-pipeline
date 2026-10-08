# Manufacturing Equipment Data Pipeline — Project Specification

## 1. Project Overview

This project implements a small Python-based ETL (Extract, Transform, Load) pipeline for processing synthetic manufacturing equipment measurements.

The pipeline demonstrates how equipment data from different sources can be standardized, validated, and stored in a structured database.

The project is developed as a portfolio project to demonstrate foundational data engineering skills relevant to manufacturing and cleanroom environments.

## 2. Project Objectives

The pipeline should:

1. Read synthetic equipment measurements from CSV and JSON files.
2. Standardize inconsistent column names, data types, and timestamp formats.
3. Identify missing, malformed, and duplicate records.
4. Store valid measurements in a SQLite database.
5. Generate a basic data-quality report.
6. Include automated tests and clear documentation.

## 3. Technology Stack

- **Python:** Core programming language
- **pandas:** Data ingestion and transformation
- **SQLite:** Relational data storage
- **pytest:** Automated testing
- **Git and GitHub:** Version control
- **VS Code:** Local development environment

## 4. Input Data

The pipeline processes two synthetic data sources.

### Source A — CSV

File: `data/raw/measurements.csv`

Expected fields:

| Field | Description |
|---|---|
| measurement_id | Unique measurement identifier |
| equipment_id | Equipment identifier |
| timestamp | Measurement timestamp |
| temperature_c | Temperature in Celsius |
| vibration_mm_s | Vibration velocity in mm/s |

### Source B — JSON

File: `data/raw/measurements.json`

The JSON file contains a list of measurement objects with a different naming convention.

| Field | Maps to |
|---|---|
| measurementId | measurement_id |
| machineId | equipment_id |
| recordedAt | timestamp_utc |
| tempC | temperature_c |
| vibrationMmS | vibration_mm_s |

Both sources represent the same type of equipment measurements but use different schemas.

The synthetic datasets will intentionally contain a small number of missing, malformed, and duplicate records.

## 5. Standardized Data Schema

After transformation, all valid records must follow a common schema.

| Field | Data Type | Description |
|---|---|---|
| measurement_id | TEXT | Unique measurement identifier |
| equipment_id | TEXT | Equipment identifier |
| timestamp_utc | TEXT | UTC timestamp in ISO 8601 format |
| temperature_c | REAL | Temperature measurement |
| vibration_mm_s | REAL | Vibration measurement |

All timestamps must be converted to UTC.

Input timestamps must contain explicit timezone information to avoid ambiguity.

## 6. Data Validation Rules

The pipeline must apply the following rules:

**Rule 1 — Missing values**

Reject records containing missing or empty required fields.

**Rule 2 — Invalid timestamps**

Reject records with timestamps that cannot be parsed or converted to UTC.

**Rule 3 — Invalid numeric values**

Reject records where temperature or vibration measurements cannot be converted to valid, finite numeric values.

**Rule 4 — Duplicate measurements**

Identify duplicate records using `measurement_id`.

Only the first valid occurrence of a measurement ID is accepted. Subsequent occurrences are rejected.

Records are processed in a deterministic order: CSV records first, followed by JSON records.

**Rule 5 — Valid records**

Records that pass all validation checks are eligible for storage in SQLite.

Each rejected record should have a primary rejection reason for reporting purposes.

## 7. ETL Pipeline Workflow

### Extract

Read the CSV and JSON datasets into pandas DataFrames.

### Transform

- Rename source columns to the standardized schema.
- Convert numeric fields to appropriate data types.
- Parse timestamps and convert them to UTC.
- Combine the standardized datasets.

### Validate

- Check required fields.
- Identify malformed values.
- Check timestamps.
- Detect duplicate measurement IDs.
- Separate valid and rejected records.

### Load

- Create a SQLite database.
- Create a measurements table.
- Insert valid records into the table.
- Use `measurement_id` as the primary key.

The MVP will process the complete synthetic dataset in a repeatable batch run, replacing previously generated outputs rather than accumulating duplicate records across runs.

## 8. Data Quality Report

The pipeline should generate a simple JSON report containing:

- Total input records
- Total accepted records
- Total rejected records
- Number of records rejected due to missing values
- Number of records rejected due to invalid timestamps
- Number of records rejected due to invalid numeric values
- Number of duplicate records rejected

The report should be saved to:

`data/processed/quality_report.json`

The SQLite database should be saved to:

`data/processed/equipment_measurements.db`

## 9. Proposed Project Structure

- `data/raw/` — Original synthetic CSV and JSON files
- `data/processed/` — Generated SQLite database and quality report
- `src/pipeline.py` — ETL implementation
- `tests/` — Automated pytest tests
- `PROJECT_SPEC.md` — Project requirements and technical decisions
- `README.md` — Project overview, setup and usage instructions
- `requirements.txt` — Python dependencies
- `.gitignore` — Files excluded from version control

The raw synthetic datasets will be version-controlled. Generated database files, reports, and local virtual environments will be excluded from Git.

## 10. Testing Requirements

Automated tests should verify at least:

1. Correct standardization of CSV and JSON column names.
2. Correct handling of valid timestamps.
3. Rejection of missing required values.
4. Rejection of malformed numeric values.
5. Detection of duplicate measurement IDs.

Tests should use small, controlled datasets.

## 11. MVP Acceptance Criteria

The minimum viable project is complete when:

- The pipeline runs locally using a documented command.
- CSV and JSON inputs are successfully loaded.
- Both sources are transformed into one standardized schema.
- Missing, malformed, and duplicate records are correctly rejected.
- Valid records are stored in SQLite.
- A data-quality report is generated.
- Basic automated tests pass.
- The README explains how to install dependencies and run the project.
- The project is committed and pushed to GitHub.

## 12. Out of Scope

The initial MVP will not include:

- External APIs or live equipment connections
- Machine learning or predictive maintenance
- Interactive dashboards
- Docker
- Cloud infrastructure
- Real-time or streaming processing
- Complex orchestration frameworks

These features may be considered for future development, but they are not required for the initial portfolio project.

## 13. Target Milestones

- **October 8–9:** Repository setup, specification, and synthetic datasets
- **October 9–10:** CSV/JSON ingestion, transformation, and validation
- **October 11:** SQLite storage and data-quality report
- **October 12–13:** Automated tests, README, and final verification
- **October 15:** Internship application deadline

## 14. Definition of Success

The project should demonstrate a complete, understandable, and reproducible ETL workflow.

The priority is not system complexity, but reliable data processing, transparent validation rules, automated tests, and clear documentation.

## 15. Synthetic Data Generation

The project uses a reproducible synthetic data generator
implemented in Python.

### Generation Strategy

- Generate 100 equipment measurement records.
- Export 70 records to CSV and 30 records to JSON.
- Simulate measurements from three equipment units.
- Use a fixed random seed (42) for reproducibility.
- Generate temperature and vibration measurements
  within predefined ranges.
- Introduce controlled data-quality issues, including:
  - Missing required values
  - Invalid timestamps
  - Malformed numeric values
  - Duplicate measurement IDs

### Limitations

The generated measurements are illustrative and do not
represent actual manufacturing equipment performance.

The dataset is designed to test ETL functionality and
data-quality validation rather than statistical modeling.