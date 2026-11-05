select
    order_id::text as order_id,
    payment_sequential::integer as payment_sequential,
    payment_type::text as payment_type,
    payment_installments::integer as payment_installments,
    payment_value::numeric(12, 2) as payment_value,
    _loaded_at
from {{ source('olist', 'order_payments') }}
