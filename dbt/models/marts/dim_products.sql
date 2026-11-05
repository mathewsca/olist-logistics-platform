select
    product_id,
    product_category_name,
    product_category,
    product_name_length,
    product_description_length,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm,
    product_length_cm * product_height_cm * product_width_cm as product_volume_cm3
from {{ ref('int_products__categorized') }}
