select
    products.*,
    -- Two categories have no translation in the source; the Portuguese name is better than a gap.
    coalesce(
        translations.product_category_name_english, products.product_category_name
    ) as product_category
from {{ ref('stg_olist__products') }} as products
left join {{ ref('stg_olist__product_category_translation') }} as translations
    on products.product_category_name = translations.product_category_name
