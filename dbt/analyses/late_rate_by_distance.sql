-- Late rate per seller -> customer distance band (km); bands match DISTANCE_BANDS in olist_platform.analytics.
select
    case
        when distance_km is null then '7. unknown'
        when distance_km < 100 then '1. < 100'
        when distance_km < 300 then '2. 100-300'
        when distance_km < 600 then '3. 300-600'
        when distance_km < 1000 then '4. 600-1000'
        when distance_km < 2000 then '5. 1000-2000'
        else '6. >= 2000'
    end as distance_band,
    count(*) as deliveries,
    round(avg(is_late::int) * 100, 1) as late_pct,
    round(avg(estimated_delivery_days), 1) as avg_promised_days,
    round(avg(delivery_days), 1) as avg_delivery_days
from {{ ref('fct_deliveries') }}
group by 1
order by 1
