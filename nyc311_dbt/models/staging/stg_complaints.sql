select
    unique_key,
    created_date,
    closed_date,
    complaint_type,
    descriptor,
    agency,
    borough,
    status,
    latitude,
    longitude
from {{ source('raw_nyc311', 'complaints') }}