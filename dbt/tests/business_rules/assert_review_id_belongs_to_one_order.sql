-- Known source anomaly: review_id is not a key, so reviews are picked per order_id.
{{ config(severity='warn') }}

select review_id, count(distinct order_id) as order_count
from {{ ref('stg_olist__order_reviews') }}
group by review_id
having count(distinct order_id) > 1
