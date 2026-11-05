select
    geolocation_zip_code_prefix::text as zip_code_prefix,
    geolocation_lat::double precision as latitude,
    geolocation_lng::double precision as longitude,
    lower(trim(geolocation_city)) as city,
    upper(trim(geolocation_state)) as state,
    _loaded_at
from {{ source('olist', 'geolocation') }}
