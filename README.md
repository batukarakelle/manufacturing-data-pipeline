# Manufacturing Equipment Data Pipeline

A small, tested batch ETL pipeline in Python. It reads synthetic equipment measurements from two sources with different schemas (CSV and JSON), standardizes them, validates every record against explicit data-quality rules, loads the valid records into SQLite and writes a JSON data-quality report.

The focus is reliable, transparent data processing rather than system complexity: every rejected record gets exactly one documented reason, and the rules are covered by automated tests.

**Stack:** Python, pandas, SQLite, pytest

## Pipeline overview

```text
measurements.csv  ──┐
                    ├──> extract ──> standardize ──> validate ──┬──> SQLite (accepted records)
measurements.json ──┘                                           └──> quality_report.json
```

| Step | Function (`src/pipeline.py`) | What it does |
|---|---|---|
| Extract | `extract_data()` | Reads the CSV (every column as text, so nothing is converted silently) and the JSON file. |
| Standardize schema | `standardize_schema()` | Renames the JSON fields to the CSV names and combines both sources, CSV first. |
| Standardize types | `standardize_types()` | Converts measurements to numbers and timestamps to UTC. Bad values are flagged, not dropped, so validation can report why a record failed. |
| Validate | `validate_data()` | Splits records into accepted and rejected, with one `rejection_reason` per rejected record. |
| Load | `load_data()` | Replaces the contents of the `measurements` table with the accepted records. |
| Report | `build_quality_report()`, `save_quality_report()` | Counts accepted and rejected records per reason and saves the summary as JSON. |

### Source schemas

| CSV column | JSON field | Standardized column |
|---|---|---|
| `measurement_id` | `measurementId` | `measurement_id` |
| `equipment_id` | `machineId` | `equipment_id` |
| `timestamp` | `recordedAt` | `timestamp_utc` |
| `temperature_c` | `tempC` | `temperature_c` |
| `vibration_mm_s` | `vibrationMmS` | `vibration_mm_s` |

## Data-quality rules

Rules are checked in this order. The first rule a record breaks becomes its rejection reason.

| Priority | Reason | A record is rejected when |
|---|---|---|
| 1 | `missing_value` | A required field is missing or blank (whitespace only counts as blank). |
| 2 | `invalid_timestamp` | The timestamp cannot be parsed, or has no explicit timezone (`Z` or `+HH:MM`). |
| 3 | `invalid_numeric` | Temperature or vibration is not a finite number, e.g. `not_a_number`, `inf`, `NaN` or a boolean. |
| 4 | `duplicate_measurement_id` | A valid record with the same ID was already accepted. |

Valid timestamps are converted to UTC. For example, `2026-10-08T15:50:00+02:00` from the JSON source is stored as `2026-10-08T13:50:00+00:00`.


## Getting started

Requires Python 3.11 or newer.

Clone the repository:

```bash
git clone https://github.com/batukarakelle/manufacturing-data-pipeline.git
cd manufacturing-data-pipeline
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the virtual environment:

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
source .venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```


### Run the pipeline

From the project root:

```bash
python src/pipeline.py
```

The run prints each stage to the console and writes two files to `data/processed/`. Both are recreated on every run and are not tracked by Git:

- `equipment_measurements.db`: SQLite database with the `measurements` table
- `quality_report.json`: the data-quality report


### Run the tests

From the project root:

```bash
python -m pytest -v
```

The project includes pytest configuration in `pyproject.toml`,
allowing tests to run with either `pytest` or `python -m pytest`.


## Results on the synthetic dataset

The dataset has 100 records (70 CSV, 30 JSON) from three pieces of equipment, with four deliberately injected problems. `quality_report.json` after a run:

```json
{
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
```

| Record | Problem | Reason |
|---|---|---|
| `M005` (CSV) | Empty `equipment_id` | `missing_value` |
| `M015` (CSV) | Timestamp `invalid-timestamp` | `invalid_timestamp` |
| `M025` (CSV) | Temperature `not_a_number` | `invalid_numeric` |
| `M002` (JSON) | Reuses an ID already accepted from the CSV | `duplicate_measurement_id` |

## Output schema

Table `measurements` in `equipment_measurements.db`:

| Column | Type | Constraint | Example |
|---|---|---|---|
| `measurement_id` | TEXT | Primary key | `M001` |
| `equipment_id` | TEXT | Not null | `EQ-01` |
| `timestamp_utc` | TEXT | Not null | `2026-10-08T08:00:00+00:00` |
| `temperature_c` | REAL | Not null | `23.08` |
| `vibration_mm_s` | REAL | Not null | `1.26` |

Each run deletes the existing rows and inserts the new batch in a single transaction, so running the pipeline twice never creates duplicates.

## Tests

`tests/test_pipeline.py` has 12 tests (counting each parametrized case) that check:

- the accepted and rejected counts and reasons for the synthetic dataset
- that the first *valid* occurrence of an ID wins, so an invalid first copy does not block a valid later one
- rejection of non-finite values (`inf`, `-inf`, `1e400`, `NaN`)
- rejection of boolean measurements, both directly and when read from a JSON file
- idempotent loading: two loads still leave 96 unique rows
- the content of the saved quality report

## Project structure

```text
manufacturing-data-pipeline/
├── data/
│   ├── raw/
│   │   ├── measurements.csv       # synthetic CSV input data
│   │   └── measurements.json      # synthetic JSON input data
│   └── processed/                 # generated database and report (not tracked)
├── scripts/
│   └── generate_data.py           # reproducible synthetic data generator
├── src/
│   └── pipeline.py                # ETL pipeline
├── tests/
│   └── test_pipeline.py           # pytest tests
├── .gitignore
├── PROJECT_SPEC.md                # requirements and design decisions
├── pyproject.toml                 # pytest configuration
├── README.md                      # project documentation
└── requirements.txt               # Python dependencies
```

## Design decisions

- **Flag first, decide later.** Type conversion records *why* a value is bad instead of discarding it, so validation can assign one clear reason to every rejected record.
- **No guessing timezones.** A timestamp without a timezone is rejected, because assuming one could silently shift a measurement by hours.
- **First valid occurrence wins.** Duplicates are detected only among records that passed every other check, in a fixed order (CSV before JSON), so results are deterministic.
- **Full refresh load.** Each run replaces the table, which keeps runs repeatable and the database free of duplicates.
- **Read CSV values as text.** IDs and malformed values stay exactly as they appeared in the source until validation inspects them.

## Limitations and next steps

- The data is synthetic and does not represent real equipment behaviour.
- Rejected records are counted in the report and printed to the console, but not stored. Writing them to a separate table would make them auditable.
- Each run processes the full batch; there is no incremental loading.
