-- Known source anomaly; makes seller_handling_days negative for these orders.
{{ config(severity='warn') }}

select order_id, purchased_at, delivered_to_carrier_at
from {{ ref('stg_olist__orders') }}
where delivered_to_carrier_at < purchased_at
