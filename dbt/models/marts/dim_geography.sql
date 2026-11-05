select
    zip_code_prefix,
    city,
    state,
    {{ brazil_region('state') }} as region,
    latitude,
    longitude,
    point_count
from {{ ref('int_geolocation__by_zip_prefix') }}
