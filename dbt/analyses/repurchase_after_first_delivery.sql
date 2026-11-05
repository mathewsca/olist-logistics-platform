-- Does a late first delivery reduce repurchase? Customers (customer_unique_id) are grouped by whether
-- their first delivered order was late; repurchase = another order within 180 days of the first purchase.
-- Only first purchases made at least 180 days before the last delivered purchase get a full window
-- (the few orders after it, from Sep-Oct 2018, are leftovers, see docs/dados.md).
with orders as (
    select customer_unique_id, order_id, purchased_at
    from {{ ref('fct_orders') }}
    where order_status not in ('canceled', 'unavailable')
),

first_deliveries as (
    select distinct on (orders.customer_unique_id)
        orders.customer_unique_id,
        deliveries.purchased_at,
        deliveries.is_late
    from {{ ref('fct_deliveries') }} as deliveries
    inner join {{ ref('fct_orders') }} as orders
        on deliveries.order_id = orders.order_id
    -- order_id breaks ties between orders placed at the same second (same rule as the dashboard).
    order by orders.customer_unique_id, deliveries.purchased_at, deliveries.order_id
),

eligible as (
    select first_deliveries.*
    from first_deliveries
    where purchased_at <= (select max(purchased_at) from {{ ref('fct_deliveries') }}) - interval '180 days'
),

returning_customers as (
    select distinct eligible.customer_unique_id
    from eligible
    inner join orders
        on orders.customer_unique_id = eligible.customer_unique_id
        and orders.purchased_at > eligible.purchased_at
        and orders.purchased_at <= eligible.purchased_at + interval '180 days'
)

select
    case when eligible.is_late then 'late' else 'on time' end as first_delivery,
    count(*) as customers,
    round(avg((returning_customers.customer_unique_id is not null)::int) * 100, 2) as repurchase_180d_pct
from eligible
left join returning_customers
    on eligible.customer_unique_id = returning_customers.customer_unique_id
group by 1
order by 1
