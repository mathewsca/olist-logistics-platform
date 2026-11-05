-- An order can ship from several sellers but has a single delivery date, so routes use one
-- origin per order: the seller of the most expensive item (ties broken by item number).
with ranked_items as (
    select
        *,
        row_number() over (
            partition by order_id order by price desc, order_item_id
        ) as price_rank
    from {{ ref('int_order_items__enriched') }}
)

select
    order_id,
    count(*) as item_count,
    count(distinct product_id) as product_count,
    count(distinct seller_id) as seller_count,
    sum(price) as items_value,
    sum(freight_value) as freight_value,
    max(case when price_rank = 1 then seller_id end) as main_seller_id,
    max(case when price_rank = 1 then product_category end) as main_product_category
from ranked_items
group by order_id
