"""Specification of the nine Olist source files and their raw tables."""

from dataclasses import dataclass

KAGGLE_DATASET = "olistbr/brazilian-ecommerce"
RAW_SCHEMA = "raw"


@dataclass(frozen=True)
class Source:
    """One CSV file of the dataset and the raw table it lands in."""

    file_name: str
    table: str
    columns: tuple[str, ...]


SOURCES: tuple[Source, ...] = (
    Source(
        "olist_customers_dataset.csv",
        "customers",
        (
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ),
    ),
    Source(
        "olist_geolocation_dataset.csv",
        "geolocation",
        (
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "geolocation_city",
            "geolocation_state",
        ),
    ),
    Source(
        "olist_order_items_dataset.csv",
        "order_items",
        (
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ),
    ),
    Source(
        "olist_order_payments_dataset.csv",
        "order_payments",
        (
            "order_id",
            "payment_sequential",
            "payment_type",
            "payment_installments",
            "payment_value",
        ),
    ),
    Source(
        "olist_order_reviews_dataset.csv",
        "order_reviews",
        (
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ),
    ),
    Source(
        "olist_orders_dataset.csv",
        "orders",
        (
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ),
    ),
    Source(
        "olist_products_dataset.csv",
        "products",
        (
            "product_id",
            "product_category_name",
            # Misspelled ("lenght") in the source; kept as-is in raw and renamed in staging.
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ),
    ),
    Source(
        "olist_sellers_dataset.csv",
        "sellers",
        ("seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"),
    ),
    Source(
        "product_category_name_translation.csv",
        "product_category_name_translation",
        ("product_category_name", "product_category_name_english"),
    ),
)


def get_source(table: str) -> Source:
    """Return the source whose raw table is ``table``."""
    for source in SOURCES:
        if source.table == table:
            return source
    raise KeyError(f"Unknown raw table: {table}")
