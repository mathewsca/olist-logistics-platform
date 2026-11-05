-- Installment interest and vouchers make some payments differ from items + freight.
{{ config(severity='warn') }}

select order_id, items_value, freight_value, payment_value
from {{ ref('fct_orders') }}
where item_count > 0
  and payment_value is not null
  and abs(items_value + freight_value - payment_value) > 1
