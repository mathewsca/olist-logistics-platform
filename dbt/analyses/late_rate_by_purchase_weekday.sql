-- Demand and lateness by weekday of the purchase; seller handling shows where the days are lost.
select
    extract(isodow from purchased_at)::int || '. ' || case extract(isodow from purchased_at)::int
        when 1 then 'Monday' when 2 then 'Tuesday' when 3 then 'Wednesday' when 4 then 'Thursday'
        when 5 then 'Friday' when 6 then 'Saturday' else 'Sunday'
    end as purchase_weekday,
    count(*) as deliveries,
    round(avg(is_late::int) * 100, 1) as late_pct,
    round(avg(seller_handling_days), 2) as avg_seller_handling_days,
    round(avg(delivery_days), 2) as avg_delivery_days
from {{ ref('fct_deliveries') }}
group by 1
order by 1
