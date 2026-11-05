-- Review score by delay band: how much a missed promise costs in customer satisfaction.
-- delay_days <= 0 is on time (delivered on or before the promised calendar date).
select
    case
        when delay_days <= -15 then '1. 15+ days early'
        when delay_days <= -8 then '2. 8-14 days early'
        when delay_days <= -1 then '3. 1-7 days early'
        when delay_days = 0 then '4. on the promised day'
        when delay_days <= 3 then '5. 1-3 days late'
        when delay_days <= 7 then '6. 4-7 days late'
        when delay_days <= 14 then '7. 8-14 days late'
        else '8. 15+ days late'
    end as delay_band,
    count(*) as reviewed_deliveries,
    round(avg(review_score), 2) as avg_review_score,
    round(avg((review_score <= 2)::int) * 100, 1) as low_score_pct
from {{ ref('fct_deliveries') }}
where review_score is not null
group by 1
order by 1
