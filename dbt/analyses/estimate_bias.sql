-- Is the Olist promise conservative or optimistic? Slack = promised days minus actual days, per customer state.
-- The first row (all states) is the overall picture.
with deliveries as (
    select
        destination_state,
        estimated_delivery_days,
        delivery_days,
        estimated_delivery_days - delivery_days as slack_days,
        is_late
    from {{ ref('fct_deliveries') }}
),

by_state as (
    select
        destination_state,
        count(*) as deliveries,
        round(avg(estimated_delivery_days), 1) as avg_promised_days,
        round(avg(delivery_days), 1) as avg_delivery_days,
        round(percentile_cont(0.5) within group (order by slack_days)::numeric, 1) as median_slack_days,
        round(avg((slack_days >= 7)::int) * 100, 1) as early_7_plus_pct,
        round(avg(is_late::int) * 100, 1) as late_pct
    from deliveries
    group by grouping sets ((destination_state), ())
)

select
    coalesce(destination_state, 'all') as destination_state,
    deliveries,
    avg_promised_days,
    avg_delivery_days,
    median_slack_days,
    early_7_plus_pct,
    late_pct
from by_state
order by destination_state is not null, median_slack_days desc
