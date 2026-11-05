select
    product_category_name::text as product_category_name,
    product_category_name_english::text as product_category_name_english,
    _loaded_at
from {{ source('olist', 'product_category_name_translation') }}
