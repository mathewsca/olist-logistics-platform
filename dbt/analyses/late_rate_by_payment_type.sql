-- Payment approval is the first leg of the delivery: a boleto is approved only when it is paid.
select
    coalesce(orders.main_payment_type, 'unknown') as payment_type,
    count(*) as deliveries,
    round(
        (percentile_cont(0.5) within group (
            order by extract(epoch from deliveries.approved_at - deliveries.purchased_at) / 3600
        ))::numeric,
        1
    ) as median_approval_hours,
    round(avg(deliveries.delivery_days), 2) as avg_delivery_days,
    round(avg(deliveries.is_late::int) * 100, 1) as late_pct
from {{ ref('fct_deliveries') }} as deliveries
inner join {{ ref('fct_orders') }} as orders
    on deliveries.order_id = orders.order_id
group by 1
order by count(*) desc, 1
