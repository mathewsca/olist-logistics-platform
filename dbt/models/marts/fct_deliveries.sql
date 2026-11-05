-- Delivered orders with a delivery date: the population for SLA analysis and the delay model.
-- Durations from timestamps are fractional days; the promise is a calendar date, so lateness
-- compares calendar dates (delivered on the promised day is on time).
with delivered_orders as (
    select *
    from {{ ref('fct_orders') }}
    where is_delivered
      and delivered_to_customer_at is not null
      and main_seller_id is not null
)

select
    orders.order_id,
    orders.customer_id,
    orders.main_seller_id as seller_id,
    orders.seller_count,
    orders.seller_count > 1 as is_multi_seller,
    orders.purchased_at,
    orders.purchase_date,
    orders.approved_at,
    orders.delivered_to_carrier_at,
    orders.delivered_to_customer_at,
    orders.delivered_to_customer_at::date as delivery_date,
    orders.estimated_delivery_date,
    round(
        (extract(epoch from orders.delivered_to_customer_at - orders.purchased_at) / 86400)::numeric, 2
    ) as delivery_days,
    orders.estimated_delivery_date - orders.purchase_date as estimated_delivery_days,
    orders.delivered_to_customer_at::date - orders.estimated_delivery_date as delay_days,
    orders.delivered_to_customer_at::date > orders.estimated_delivery_date as is_late,
    round(
        (extract(epoch from orders.delivered_to_carrier_at - orders.purchased_at) / 86400)::numeric, 2
    ) as seller_handling_days,
    round(
        (extract(epoch from orders.delivered_to_customer_at - orders.delivered_to_carrier_at) / 86400)::numeric, 2
    ) as carrier_transit_days,
    sellers.seller_zip_code_prefix as origin_zip_code_prefix,
    sellers.seller_state as origin_state,
    sellers.seller_region as origin_region,
    customers.customer_zip_code_prefix as destination_zip_code_prefix,
    customers.customer_state as destination_state,
    customers.customer_region as destination_region,
    sellers.seller_state = customers.customer_state as is_same_state,
    -- Null when either zip code prefix has no geolocation in the source.
    round(
        {{ haversine_km(
            'origin.latitude', 'origin.longitude', 'destination.latitude', 'destination.longitude'
        ) }}::numeric, 1
    ) as distance_km,
    orders.main_product_category,
    orders.item_count,
    orders.items_value,
    orders.freight_value,
    orders.review_score
from delivered_orders as orders
inner join {{ ref('dim_sellers') }} as sellers
    on orders.main_seller_id = sellers.seller_id
inner join {{ ref('dim_customers') }} as customers
    on orders.customer_id = customers.customer_id
left join {{ ref('dim_geography') }} as origin
    on sellers.seller_zip_code_prefix = origin.zip_code_prefix
left join {{ ref('dim_geography') }} as destination
    on customers.customer_zip_code_prefix = destination.zip_code_prefix
