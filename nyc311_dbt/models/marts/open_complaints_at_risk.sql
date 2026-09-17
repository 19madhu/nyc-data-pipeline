with open_complaints as (

    select
        unique_key,
        created_date,
        complaint_type,
        borough,
        status,
        timestamp_diff(current_timestamp(), created_date, hour) as hours_open

    from {{ ref('stg_complaints') }}
    where closed_date is null

),

benchmarks as (

    select
        complaint_type,
        round(percentile_cont(resolution_hours, 0.9) over (partition by complaint_type), 1) as p90_benchmark_hours

    from {{ ref('complaint_resolution_analysis') }}
    qualify row_number() over (partition by complaint_type order by unique_key) = 1

)

select
    o.unique_key,
    o.created_date,
    o.complaint_type,
    o.borough,
    o.status,
    o.hours_open,
    b.p90_benchmark_hours,
    o.hours_open > b.p90_benchmark_hours as currently_at_risk

from open_complaints o
left join benchmarks b
    on o.complaint_type = b.complaint_type