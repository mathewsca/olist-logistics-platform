-- Known source anomaly: these products keep the Portuguese category name.
{{ config(severity='warn') }}

select products.product_id, products.product_category_name
from {{ ref('stg_olist__products') }} as products
left join {{ ref('stg_olist__product_category_translation') }} as translations
    on products.product_category_name = translations.product_category_name
where products.product_category_name is not null
  and translations.product_category_name is null
