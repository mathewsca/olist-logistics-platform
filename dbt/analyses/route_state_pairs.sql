-- Busiest seller state -> customer state routes; small routes are left out because their rates are noise.
select
    origin_state,
    destination_state,
    count(*) as deliveries,
    round(avg(is_late::int) * 100, 1) as late_pct,
    round(avg(distance_km), 0) as avg_distance_km,
    round(avg(estimated_delivery_days), 1) as avg_promised_days,
    round(avg(delivery_days), 1) as avg_delivery_days
from {{ ref('fct_deliveries') }}
group by 1, 2
having count(*) >= 300
order by deliveries desc
limit 20
