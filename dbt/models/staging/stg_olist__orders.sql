-- Timestamps come without time zone; they are kept as local Brazilian time (timestamp, not timestamptz).
select
    order_id::text as order_id,
    customer_id::text as customer_id,
    order_status::text as order_status,
    order_purchase_timestamp::timestamp as purchased_at,
    order_approved_at::timestamp as approved_at,
    order_delivered_carrier_date::timestamp as delivered_to_carrier_at,
    order_delivered_customer_date::timestamp as delivered_to_customer_at,
    -- Always at midnight in the source: the promise is a calendar date.
    order_estimated_delivery_date::date as estimated_delivery_date,
    _loaded_at
from {{ source('olist', 'orders') }}
