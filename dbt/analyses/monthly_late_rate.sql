-- SLA by purchase month: share of deliveries that missed the promised date and how late they were.
select
    to_char(purchase_date, 'YYYY-MM') as year_month,
    count(*) as deliveries,
    round(avg(is_late::int) * 100, 1) as late_pct,
    round(avg(delay_days) filter (where is_late), 1) as avg_days_late_when_late,
    round(percentile_cont(0.5) within group (order by delivery_days)::numeric, 1) as median_delivery_days
from {{ ref('fct_deliveries') }}
group by 1
order by 1
