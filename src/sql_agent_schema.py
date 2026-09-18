COMPLAINT_ANALYSIS_SCHEMA = """
Table: `maddie19.nyc311_dbt.complaint_resolution_analysis`

Columns:
- unique_key (STRING): unique complaint ID
- created_date (TIMESTAMP): when the complaint was filed
- closed_date (TIMESTAMP): when the complaint was resolved
- complaint_type (STRING): category of complaint, e.g. 'Noise - Residential', 'Illegal Parking'
- borough (STRING): one of 'BROOKLYN', 'QUEENS', 'MANHATTAN', 'BRONX', 'STATEN ISLAND'
- status (STRING): current status, e.g. 'Closed'
- resolution_hours (FLOAT): hours between created_date and closed_date
- p90_benchmark_hours (FLOAT): the 90th percentile resolution time for that complaint_type
- is_sla_breach (BOOLEAN): true if resolution_hours exceeded the 90th percentile benchmark

This table contains complaints that have a closed_date populated (so resolution_hours is always available), but a small number may still show a status other than 'Closed' (e.g. 'Open', 'In Progress', 'Assigned') due to source data inconsistencies in NYC's 311 system.
"""