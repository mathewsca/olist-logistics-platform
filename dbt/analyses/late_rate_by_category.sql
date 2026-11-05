-- Late rate per product category (category of the most expensive item), for categories with volume.
select
    coalesce(main_product_category, 'unknown') as product_category,
    count(*) as deliveries,
    round(avg(is_late::int) * 100, 1) as late_pct,
    round(avg(freight_value), 2) as avg_freight_value,
    round(avg(distance_km), 0) as avg_distance_km
from {{ ref('fct_deliveries') }}
group by 1
having count(*) >= 1000
order by late_pct desc
