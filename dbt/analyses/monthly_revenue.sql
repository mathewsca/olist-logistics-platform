-- Delivered revenue (items + freight) per purchase month and how much of it came late.
select
    to_char(purchased_at, 'YYYY-MM') as year_month,
    count(*) as deliveries,
    round(sum(items_value + freight_value), 0) as revenue_brl,
    round(avg(items_value + freight_value), 2) as avg_ticket_brl,
    round(sum(freight_value) / sum(items_value + freight_value) * 100, 1) as freight_share_pct,
    round(
        sum(case when is_late then items_value + freight_value else 0 end)
        / sum(items_value + freight_value) * 100,
        1
    ) as late_revenue_pct
from {{ ref('fct_deliveries') }}
group by 1
order by 1
