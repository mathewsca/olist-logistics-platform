-- The source has ~50 points per prefix and a few outside Brazil (typos in the coordinates).
-- The median of the points inside Brazil's bounding box is robust to the remaining outliers.
with points_in_brazil as (
    select *
    from {{ ref('stg_olist__geolocation') }}
    where latitude between {{ var('brazil_min_lat') }} and {{ var('brazil_max_lat') }}
      and longitude between {{ var('brazil_min_lng') }} and {{ var('brazil_max_lng') }}
)

select
    zip_code_prefix,
    percentile_cont(0.5) within group (order by latitude) as latitude,
    percentile_cont(0.5) within group (order by longitude) as longitude,
    mode() within group (order by city) as city,
    mode() within group (order by state) as state,
    count(*) as point_count
from points_in_brazil
group by zip_code_prefix
