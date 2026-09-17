with resolved_complaints as (

    select
        unique_key,
        created_date,
        closed_date,
        complaint_type,
        borough,
        status,
        timestamp_diff(closed_date, created_date, hour) as resolution_hours

    from {{ ref('stg_complaints') }}
    where closed_date is not null
      and closed_date >= created_date  -- guards against bad data (closed before created)

),

with_percentile as (

    select
        *,
        percentile_cont(resolution_hours, 0.9) over (
            partition by complaint_type
        ) as p90_resolution_hours_for_type

    from resolved_complaints

)

select
    unique_key,
    created_date,
    closed_date,
    complaint_type,
    borough,
    status,
    resolution_hours,
    round(p90_resolution_hours_for_type, 1) as p90_benchmark_hours,
    resolution_hours > p90_resolution_hours_for_type as is_sla_breach

from with_percentile