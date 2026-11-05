select
    items.order_id,
    items.order_item_id,
    items.product_id,
    items.seller_id,
    orders.customer_id,
    orders.order_status,
    orders.purchased_at,
    orders.purchased_at::date as purchase_date,
    items.shipping_limit_at,
    items.product_category,
    items.price,
    items.freight_value,
    items.price + items.freight_value as total_value
from {{ ref('int_order_items__enriched') }} as items
inner join {{ ref('stg_olist__orders') }} as orders
    on items.order_id = orders.order_id
