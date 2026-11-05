select
    items.order_id,
    items.order_item_id,
    items.product_id,
    items.seller_id,
    items.shipping_limit_at,
    items.price,
    items.freight_value,
    products.product_category,
    sellers.seller_zip_code_prefix,
    sellers.seller_state
from {{ ref('stg_olist__order_items') }} as items
inner join {{ ref('int_products__categorized') }} as products
    on items.product_id = products.product_id
inner join {{ ref('stg_olist__sellers') }} as sellers
    on items.seller_id = sellers.seller_id
