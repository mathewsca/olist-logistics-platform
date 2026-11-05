-- Sellers with at least 30 deliveries, banded by their late rate: does the score follow?
with sellers as (
    select
        seller_id,
        count(*) as deliveries,
        avg(is_late::int) * 100 as late_pct,
        sum(review_score) as score_sum,
        count(review_score) as reviews
    from {{ ref('fct_deliveries') }}
    group by seller_id
    having count(*) >= 30
)

select
    case
        when late_pct < 5 then '1. < 5'
        when late_pct < 10 then '2. 5-10'
        when late_pct < 20 then '3. 10-20'
        else '4. >= 20'
    end as seller_late_band,
    count(*) as sellers,
    sum(deliveries) as deliveries,
    round(sum(score_sum)::numeric / sum(reviews), 2) as avg_review_score
from sellers
group by 1
order by 1
