-- Known source anomaly; makes carrier_transit_days negative for these orders.
{{ config(severity='warn') }}

select order_id, delivered_to_carrier_at, delivered_to_customer_at
from {{ ref('stg_olist__orders') }}
where delivered_to_customer_at < delivered_to_carrier_at
