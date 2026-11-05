select
    seller_id,
    seller_zip_code_prefix,
    seller_city,
    seller_state,
    {{ brazil_region('seller_state') }} as seller_region
from {{ ref('stg_olist__sellers') }}
