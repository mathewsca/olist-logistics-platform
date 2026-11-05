select order_id, purchased_at, delivered_to_customer_at
from {{ ref('stg_olist__orders') }}
where delivered_to_customer_at < purchased_at
