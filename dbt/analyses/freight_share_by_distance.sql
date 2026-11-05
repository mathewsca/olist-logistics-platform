-- Freight as a share of the items' value per distance band; bands match DISTANCE_BANDS.
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
    round(avg(freight_value), 2) as avg_freight_value,
    round(
        (percentile_cont(0.5) within group (order by freight_value / items_value * 100))::numeric, 1
    ) as median_freight_share_pct
from {{ ref('fct_deliveries') }}
where items_value > 0
group by 1
order by 1
