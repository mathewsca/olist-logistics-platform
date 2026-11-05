select
    order_id::text as order_id,
    order_item_id::integer as order_item_id,
    product_id::text as product_id,
    seller_id::text as seller_id,
    shipping_limit_date::timestamp as shipping_limit_at,
    price::numeric(12, 2) as price,
    freight_value::numeric(12, 2) as freight_value,
    _loaded_at
from {{ source('olist', 'order_items') }}
