with days as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('" ~ var('calendar_start') ~ "' as date)",
        end_date="cast('" ~ var('calendar_end') ~ "' as date)"
    ) }}
)

select
    date_day::date as date_day,
    extract(year from date_day)::integer as year,
    extract(quarter from date_day)::integer as quarter,
    extract(month from date_day)::integer as month,
    to_char(date_day, 'YYYY-MM') as year_month,
    date_trunc('month', date_day)::date as month_start,
    date_trunc('week', date_day)::date as week_start,
    extract(isodow from date_day)::integer as iso_day_of_week,
    extract(isodow from date_day) in (6, 7) as is_weekend
from days
