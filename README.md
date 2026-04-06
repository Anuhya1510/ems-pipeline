# EMS ETL Pipeline 

# Project Overview
This repository contains a production-ready, idempotent ETL pipeline designed to ingest raw Emergency Medical Services (EMS) data and transform it into a Kimball-style Star Schema. 

The pipeline acts as a Data Quality Firewall, enforcing strict NEMSIS standards and business logic before data reaches the analytical layer. In the current test cycle, the system identified and quarantined 23 invalid records to ensure the integrity of the Fact table.

# Architecture & Flow
The pipeline follows a modular Extract-Transform-Load (ETL) architecture:
1. Extract: Ingests raw NEMSIS-compliant CSV data using Pandas with automated schema inference.
2. Transform: Executes a multi-stage validation gate to categorize and filter records.
3. Load (Staging): Bulk-loads valid records into a volatile “STG_EMS_INCIDENTS” table using SQLAlchemy.
4. Load (Warehouse): Performs atomic T-SQL “MERGE” operations to sync dimensions and the Fact table.

![EMS ETL Star Schema](docs/erd_diagram.png)


# Model Grain & Definitions
The warehouse utilizes a Kimball Star Schema designed for high-performance BI analytics.

# Fact Table
Fact_EMS_Incidents: The grain is one record per EMS Incident IncidentID. 
    Measures: “ToSceneMins” (Response Time).
    Keys: Foreign keys to “Dim_Location” and “Dim_Provider”.

# Dimensions
Dim_Location: SCD Type 1 dimension. Attributes: “CountyName”, “DestinationType”.
Dim_Provider: SCD Type 1 dimension. Attributes: “Structure”, “ServiceType”, “ServiceLevel”.

# Data Quality Rules
The pipeline categorizes the 23 rejections into four specific business-driven buckets:

| Category | Rejection Logic | Records Rejected |
| Missing Critical Fields | Nulls in “_id”, “INCIDENT_DT”, or “INCIDENT_COUNTY”. | 11 |
| Invalid Timestamp Sequence | Chronological violations (e.g., Arrived < Dispatched). | 5 |
| Duration Outlier/Negative | Response times < 0 mins or > 1440 mins (24h). | 7 |
| Duplicate Records | Duplicate “_id” values found in source. | 0 |


# Logging & Error Handling
Auditability: Quarantined records are moved to “ERR_Quarantine”. We use a JSON Serialization pattern to preserve the full raw record alongside a “QuarantineReason” for medical auditors.
Logging: A dedicated Python “logging” module tracks the ETL lifecycle, row counts, and execution time for performance monitoring.

# Incremental Strategy
The pipeline is designed for Daily Incremental Loads:
1.  Idempotency: The use of T-SQL “MERGE” ensures that if a file is re-processed, records are updated rather than duplicated.
2.  High-Water Mark: The system is built to support a “LastModifiedDate” filter, where the Python “Extract” layer only pulls records newer than the maximum “LoadTimestamp” currently in the Fact table.

# Assumptions & Decisions
NEMSIS Nulls: Values like "Not Recorded" or "Not Applicable" are coerced to true SQL “NULLs”. This ensures that averages are not skewed by placeholder text.
Surrogate Keys: “IDENTITY” columns are used for dimensions to decouple the warehouse from source system changes and allow for future SCD Type 2 implementation.
Negative Durations: These are treated as "Entry Errors" and quarantined rather than being "fixed", as altering medical timestamps without an audit trail is a compliance risk.

# How to Run End-to-End
1.  Initialize DB: Run “sql/ddl.sql” in SQL Server to create the schema.
2.  Configuration: Set your connection string in “config/config.yaml”.
3.  Data: Place the EMS CSV in the “data/” folder.
4.  Execute: Run “python main.py”.

