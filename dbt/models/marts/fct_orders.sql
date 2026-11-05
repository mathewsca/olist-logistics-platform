select
    orders.order_id,
    orders.customer_id,
    customers.customer_unique_id,
    orders.order_status,
    orders.order_status = 'delivered' as is_delivered,
    orders.purchased_at,
    orders.purchased_at::date as purchase_date,
    orders.approved_at,
    orders.delivered_to_carrier_at,
    orders.delivered_to_customer_at,
    orders.estimated_delivery_date,
    coalesce(items.item_count, 0) as item_count,
    coalesce(items.seller_count, 0) as seller_count,
    items.main_seller_id,
    items.main_product_category,
    items.items_value,
    items.freight_value,
    payments.payment_value,
    payments.payment_count,
    payments.main_payment_type,
    payments.max_installments,
    reviews.review_score,
    coalesce(reviews.review_count, 0) as review_count,
    reviews.has_review_comment,
    reviews.review_mentions_delivery
from {{ ref('stg_olist__orders') }} as orders
inner join {{ ref('stg_olist__customers') }} as customers
    on orders.customer_id = customers.customer_id
left join {{ ref('int_orders__items_summary') }} as items
    on orders.order_id = items.order_id
left join {{ ref('int_orders__payments_summary') }} as payments
    on orders.order_id = payments.order_id
left join {{ ref('int_orders__latest_review') }} as reviews
    on orders.order_id = reviews.order_id
