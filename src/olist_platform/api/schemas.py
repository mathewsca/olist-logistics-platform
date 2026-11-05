"""Request and response contracts of the inference API."""

import re
from datetime import date, datetime
from typing import Annotated, Literal

import pandas as pd
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

# The marts store purchase timestamps as Olist exported them: São Paulo local time, no offset.
SOURCE_TIMEZONE = "America/Sao_Paulo"
MAX_ITEMS_PER_ORDER = 100
MAX_BATCH_SIZE = 1000

BrazilianState = Literal[
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]  # fmt: skip


def _zip_prefix(value: str) -> str:
    digits = re.sub(r"[\s.-]", "", value)
    if not re.fullmatch(r"\d{5}(\d{3})?", digits):
        raise ValueError("expected a CEP (8 digits) or its 5-digit prefix")
    return digits[:5]


ZipCode = Annotated[
    str,
    AfterValidator(_zip_prefix),
    Field(
        description="CEP (`01310-100`, `01310100`) or its 5-digit prefix; only the prefix is used"
    ),
]


class OrderItem(BaseModel):
    """One product line of the order."""

    # Infinity/NaN are valid JSON for Python but would reach the model as non-finite features.
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    seller_id: str = Field(min_length=1, max_length=64)
    seller_zip_code: ZipCode
    seller_state: BrazilianState
    price: float = Field(gt=0, le=1_000_000, description="Unit price in BRL")
    freight_value: float = Field(
        ge=0, le=100_000, description="Freight charged for each unit, in BRL"
    )
    quantity: int = Field(default=1, ge=1, le=MAX_ITEMS_PER_ORDER)
    product_category: str | None = Field(
        default=None, description="English category name, as in the Olist translation table"
    )
    product_weight_g: float | None = Field(default=None, ge=0, le=1_000_000)
    product_length_cm: float | None = Field(default=None, ge=0, le=10_000)
    product_height_cm: float | None = Field(default=None, ge=0, le=10_000)
    product_width_cm: float | None = Field(default=None, ge=0, le=10_000)


# After the seller-history snapshot (2018-10), as a real new order would be.
ORDER_EXAMPLE = {
    "purchased_at": "2018-11-06T14:30:00",
    "estimated_delivery_date": "2018-11-27",
    "customer_zip_code": "22041-001",
    "customer_state": "RJ",
    "items": [
        {
            "seller_id": "6560211a19b47992c3666cc44a7e94c0",
            "seller_zip_code": "05849",
            "seller_state": "SP",
            "price": 89.9,
            "freight_value": 18.5,
            "quantity": 1,
            "product_category": "bed_bath_table",
            "product_weight_g": 1200,
            "product_length_cm": 40,
            "product_height_cm": 10,
            "product_width_cm": 30,
        }
    ],
}


class OrderRequest(BaseModel):
    """An order as known at checkout, before payment approval."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [ORDER_EXAMPLE]})

    purchased_at: datetime = Field(
        description="Purchase time; without an offset it is read as São Paulo local time"
    )
    estimated_delivery_date: date = Field(description="Delivery date promised to the customer")
    customer_zip_code: ZipCode
    customer_state: BrazilianState
    items: list[OrderItem] = Field(min_length=1, max_length=MAX_ITEMS_PER_ORDER)

    @model_validator(mode="after")
    def _check_order(self) -> "OrderRequest":
        if self.estimated_delivery_date < self.local_purchase_time().date():
            raise ValueError("estimated_delivery_date is before the purchase date")
        if sum(item.quantity for item in self.items) > MAX_ITEMS_PER_ORDER:
            raise ValueError(f"an order holds at most {MAX_ITEMS_PER_ORDER} units")
        origins = {}
        for item in self.items:
            origin = (item.seller_zip_code, item.seller_state)
            if origins.setdefault(item.seller_id, origin) != origin:
                raise ValueError(f"seller {item.seller_id} has two different addresses")
        return self

    def local_purchase_time(self) -> pd.Timestamp:
        """Naive São Paulo time, the convention of the training data."""
        timestamp = pd.Timestamp(self.purchased_at)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert(SOURCE_TIMEZONE).tz_localize(None)
        return timestamp


class BatchRequest(BaseModel):
    """Several orders scored in one call."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"examples": [{"orders": [ORDER_EXAMPLE]}]}
    )

    orders: list[OrderRequest] = Field(min_length=1, max_length=MAX_BATCH_SIZE)


class Prediction(BaseModel):
    """Delay risk and expected delivery time of one order."""

    late_risk_score: float = Field(
        ge=0,
        le=1,
        description=(
            "Ranking score of the late-delivery model. Higher means riskier; it is NOT a "
            "calibrated probability (the champion was trained with balanced class weights)."
        ),
    )
    is_late_predicted: bool = Field(description="late_risk_score >= the champion's threshold")
    late_threshold: float
    predicted_delivery_days: float = Field(ge=0, description="Days from purchase to delivery")
    predicted_delivery_date: date
    promised_delivery_days: int = Field(description="Calendar days from purchase to the promise")
    warnings: list[str] = Field(
        default_factory=list,
        description="Inputs the model had to fill in (unknown seller, zip without coordinates)",
    )


class BatchResponse(BaseModel):
    """Predictions in the order of the request."""

    predictions: list[Prediction]


class ModelVersion(BaseModel):
    """A registered champion."""

    name: str
    version: str
    algorithm: str | None = None
    run_id: str | None = None


class ModelInfo(BaseModel):
    """Which models and lookup tables are being served."""

    classifier: ModelVersion
    regressor: ModelVersion
    late_threshold: float
    served_from: Literal["mlflow", "export"]
    seller_history_as_of: str | None = None
    exported_at: str | None = None
    features: list[str]


class Health(BaseModel):
    """Liveness and readiness."""

    status: Literal["ok", "unavailable"]
    model_loaded: bool
