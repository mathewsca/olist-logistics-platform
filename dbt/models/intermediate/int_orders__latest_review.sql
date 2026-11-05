-- Some orders were reviewed more than once; the last answer is the customer's final opinion.
with ranked_reviews as (
    select
        *,
        count(*) over (partition by order_id) as review_count,
        row_number() over (
            partition by order_id
            order by review_answered_at desc nulls last, review_created_date desc, review_id
        ) as recency_rank
    from {{ ref('stg_olist__order_reviews') }}
)

select
    order_id,
    review_score,
    review_comment_message is not null as has_review_comment,
    -- Word stems need no accents ("entrega", "atrasou", "não chegou", "correios"); null when
    -- there is no comment, so the share is taken over written reviews only.
    review_comment_message
    ~* 'entreg|prazo|atras|cheg|receb|correio|transportador|rastre|demor' as review_mentions_delivery,
    review_count
from ranked_reviews
where recency_rank = 1
