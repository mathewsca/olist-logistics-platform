select
    product_id::text as product_id,
    {{ blank_to_null('product_category_name') }} as product_category_name,
    product_name_lenght::integer as product_name_length,
    product_description_lenght::integer as product_description_length,
    product_photos_qty::integer as product_photos_qty,
    product_weight_g::integer as product_weight_g,
    product_length_cm::integer as product_length_cm,
    product_height_cm::integer as product_height_cm,
    product_width_cm::integer as product_width_cm,
    _loaded_at
from {{ source('olist', 'products') }}
