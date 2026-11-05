-- Known source anomaly: canceled orders with a delivery date stay out of fct_deliveries.
{{ config(severity='warn') }}

select order_id, order_status, delivered_to_customer_at
from {{ ref('stg_olist__orders') }}
where order_status <> 'delivered'
  and delivered_to_customer_at is not null
