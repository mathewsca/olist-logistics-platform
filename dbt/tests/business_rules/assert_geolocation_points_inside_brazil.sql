-- Known source anomaly: typos in the coordinates; these points are dropped before the median.
{{ config(severity='warn') }}

select zip_code_prefix, latitude, longitude
from {{ ref('stg_olist__geolocation') }}
where latitude not between {{ var('brazil_min_lat') }} and {{ var('brazil_max_lat') }}
   or longitude not between {{ var('brazil_min_lng') }} and {{ var('brazil_max_lng') }}
