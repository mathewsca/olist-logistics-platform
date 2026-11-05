select
    review_id::text as review_id,
    order_id::text as order_id,
    review_score::smallint as review_score,
    {{ blank_to_null('review_comment_title') }} as review_comment_title,
    {{ blank_to_null('review_comment_message') }} as review_comment_message,
    -- The source sends the creation date at midnight: it is a date, not an instant.
    review_creation_date::date as review_created_date,
    review_answer_timestamp::timestamp as review_answered_at,
    _loaded_at
from {{ source('olist', 'order_reviews') }}
