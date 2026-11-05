select
    seller_id::text as seller_id,
    seller_zip_code_prefix::text as seller_zip_code_prefix,
    lower(trim(seller_city)) as seller_city,
    upper(trim(seller_state)) as seller_state,
    _loaded_at
from {{ source('olist', 'sellers') }}
