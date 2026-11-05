select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state,
    {{ brazil_region('customer_state') }} as customer_region
from {{ ref('stg_olist__customers') }}
