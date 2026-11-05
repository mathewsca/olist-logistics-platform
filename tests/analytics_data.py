"""Tiny hand-built datasets with the columns of ``olist_platform.analytics.datasets``."""

from io import StringIO

import pandas as pd

# Two late orders (o2, o5), one on the promised day (o4, unreviewed), one without distance (o5).
# Four reviews have a comment (o1, o2, o5, o6); boletos (o2, o5) take days to be approved.
DELIVERIES_CSV = """\
order_id,seller_id,customer_unique_id,purchased_at,approved_at,delivery_days,estimated_delivery_days,delay_days,is_late,seller_handling_days,origin_state,destination_state,destination_region,distance_km,main_product_category,items_value,freight_value,main_payment_type,review_score,review_mentions_delivery
o1,s1,u1,2017-01-05T10:00,2017-01-05T10:30,5.0,20,-15,False,1.0,SP,SP,Sudeste,50.0,toys,100.0,8.0,credit_card,5,False
o2,s1,u2,2017-01-20T09:00,2017-01-22T09:00,30.0,20,10,True,6.0,SP,RJ,Sudeste,400.0,toys,90.0,18.0,boleto,1,True
o3,s2,u3,2017-02-02T12:00,2017-02-02T13:00,8.0,25,-17,False,2.0,SP,RJ,Sudeste,420.0,,60.0,12.0,credit_card,4,
o4,s2,u1,2017-03-01T08:00,2017-03-01T08:15,12.0,12,0,False,3.0,SP,SP,Sudeste,60.0,auto,200.0,55.0,credit_card,,
o5,s3,u4,2017-02-10T15:00,2017-02-13T15:00,40.0,30,2,True,10.0,MG,BA,Nordeste,,auto,40.0,30.0,boleto,2,False
o6,s1,u5,2017-08-15T11:00,2017-08-15T11:10,9.0,20,-11,False,1.5,SP,SP,Sudeste,2500.0,toys,150.0,20.0,voucher,5,True
"""

# u2 buys again (shipped order); u3's second order was canceled, so it is not a repurchase.
EXTRA_ORDERS_CSV = """\
order_id,customer_unique_id,purchased_at,order_status
o7,u2,2017-03-01 10:00,shipped
o8,u3,2017-03-01 10:00,canceled
"""

STATE_CENTROIDS_CSV = """\
state,latitude,longitude
SP,-23.0,-47.0
RJ,-22.5,-43.0
MG,-19.0,-44.0
BA,-12.5,-41.0
"""


def read(csv: str) -> pd.DataFrame:
    """Parse one of the CSV blocks above."""
    header = csv.splitlines()[0].split(",")
    dates = [column for column in ("purchased_at", "approved_at") if column in header]
    return pd.read_csv(StringIO(csv), parse_dates=dates)


def deliveries_frame() -> pd.DataFrame:
    """Six deliveries over four purchase months."""
    frame = read(DELIVERIES_CSV)
    frame["review_score"] = frame["review_score"].astype("Int64")
    frame["review_mentions_delivery"] = frame["review_mentions_delivery"].astype("boolean")
    return frame


def data_quality_frame() -> pd.DataFrame:
    """Two known issues: one with violations, one whose test has not run."""
    return pd.DataFrame(
        {
            "test_name": ["assert_a", "assert_b"],
            "model": ["stg_a", "stg_b"],
            "issue": ["Problema A", "Problema B"],
            "treatment": ["Mantido", "Descartado"],
            "violations": pd.array([12, None], dtype="Int64"),
        }
    )


def orders_frame() -> pd.DataFrame:
    """Every delivered order plus the two extra orders."""
    delivered = deliveries_frame()[["order_id", "customer_unique_id", "purchased_at"]].assign(
        order_status="delivered"
    )
    return pd.concat([delivered, read(EXTRA_ORDERS_CSV)], ignore_index=True)


def centroids_frame() -> pd.DataFrame:
    """Centroids of the states used above."""
    return read(STATE_CENTROIDS_CSV)


def monitoring_runs_frame() -> pd.DataFrame:
    """Two monitored months: the second one retrained and its challenger was rejected."""
    return pd.DataFrame(
        {
            "month": pd.to_datetime(["2018-04-01", "2018-05-01"]),
            "champion_version": ["1", "1"],
            "orders": [100, 120],
            "labelled": [95, 110],
            "late_rate": [0.05, 0.08],
            "pr_auc": [0.15, 0.10],
            "lift": [3.0, 1.25],
            "validation_lift": [2.5, 2.5],
            "recall": [0.4, 0.3],
            "flagged_rate": [0.1, 0.1],
            "mae": [5.0, 6.0],
            "validation_mae": [5.0, 5.0],
            "drift_share": [0.1, 0.2],
            "drifted_features": [2, 4],
            "retrain_reasons": [None, "PR-AUC lift 1.25 vs 2.50 on validation"],
            "challenger_version": [None, "2"],
            "gate_passed": [None, False],
            "gate_detail": [None, "MAE 6.10 worse than the champion's 6.00"],
        }
    )
