select order_id, purchased_at, estimated_delivery_date
from {{ ref('stg_olist__orders') }}
where estimated_delivery_date < purchased_at::date
