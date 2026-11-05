-- Late rate per freight value band (BRL); bands match FREIGHT_BANDS in olist_platform.analytics.
select
    case
        when freight_value < 10 then '1. < 10'
        when freight_value < 15 then '2. 10-15'
        when freight_value < 20 then '3. 15-20'
        when freight_value < 30 then '4. 20-30'
        when freight_value < 50 then '5. 30-50'
        else '6. >= 50'
    end as freight_band,
    count(*) as deliveries,
    round(avg(is_late::int) * 100, 1) as late_pct,
    round(avg(distance_km), 0) as avg_distance_km
from {{ ref('fct_deliveries') }}
group by 1
order by 1
