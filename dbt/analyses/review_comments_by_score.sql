-- What written reviews talk about: share that mentions delivery, per score group.
select
    case
        when deliveries.review_score <= 2 then '1. 1-2'
        when deliveries.review_score = 3 then '2. 3'
        else '3. 4-5'
    end as score_group,
    count(*) as comments,
    round(avg(orders.review_mentions_delivery::int) * 100, 1) as mentions_delivery_pct,
    round(avg(deliveries.is_late::int) * 100, 1) as late_pct
from {{ ref('fct_deliveries') }} as deliveries
inner join {{ ref('fct_orders') }} as orders
    on deliveries.order_id = orders.order_id
where orders.review_mentions_delivery is not null
group by 1
order by 1
