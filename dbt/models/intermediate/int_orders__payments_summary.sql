with ranked_payments as (
    select
        *,
        row_number() over (
            partition by order_id order by payment_value desc, payment_sequential
        ) as value_rank
    from {{ ref('stg_olist__order_payments') }}
)

select
    order_id,
    count(*) as payment_count,
    sum(payment_value) as payment_value,
    max(payment_installments) as max_installments,
    max(case when value_rank = 1 then payment_type end) as main_payment_type
from ranked_payments
group by order_id
