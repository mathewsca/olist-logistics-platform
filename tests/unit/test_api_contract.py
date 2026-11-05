"""HTTP contract of the inference API: status codes, schema and invalid inputs."""

import copy
import json

import pytest
from fastapi.testclient import TestClient

from olist_platform.api.app import create_app
from olist_platform.api.schemas import MAX_BATCH_SIZE, ORDER_EXAMPLE
from olist_platform.features import FEATURE_COLUMNS
from tests.api_data import THRESHOLD, fitted_bundle

PREDICTION_FIELDS = {
    "late_risk_score",
    "is_late_predicted",
    "late_threshold",
    "predicted_delivery_days",
    "predicted_delivery_date",
    "promised_delivery_days",
    "warnings",
}


@pytest.fixture(scope="module")
def client():
    bundle = fitted_bundle()
    with TestClient(create_app(lambda: bundle)) as test_client:
        yield test_client


def order(**overrides):
    body = copy.deepcopy(ORDER_EXAMPLE)
    item_overrides = overrides.pop("item", {})
    body["items"][0].update(item_overrides)
    body.update(overrides)
    return body


def test_health_reports_a_loaded_model(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_loaded": True}


def test_without_a_model_health_and_predict_answer_503():
    def failing_loader():
        raise FileNotFoundError("no bundle")

    with TestClient(create_app(failing_loader)) as unloaded:
        assert unloaded.get("/health").status_code == 503
        assert unloaded.get("/model-info").status_code == 503
        assert unloaded.post("/predict", json=order()).status_code == 503


def test_model_info_describes_the_champions(client):
    body = client.get("/model-info").json()
    assert body["classifier"]["name"] == "olist-late-delivery"
    assert body["regressor"]["version"] == "1"
    assert body["late_threshold"] == THRESHOLD
    assert body["served_from"] == "export"
    assert body["features"] == list(FEATURE_COLUMNS)


def test_predict_returns_the_documented_schema(client):
    response = client.post("/predict", json=order())
    assert response.status_code == 200
    body = response.json()
    assert set(body) == PREDICTION_FIELDS
    assert 0 <= body["late_risk_score"] <= 1
    assert body["is_late_predicted"] == (body["late_risk_score"] >= THRESHOLD)
    assert body["promised_delivery_days"] == 21
    assert body["warnings"] == []


def test_batch_keeps_the_request_order(client):
    orders = [order(), order(customer_state="BA", customer_zip_code="40020")]
    batch = client.post("/predict/batch", json={"orders": orders}).json()["predictions"]
    singles = [client.post("/predict", json=o).json() for o in orders]
    # Batched matrix products may differ from single-row ones in the last floating-point digit.
    for batched, single in zip(batch, singles, strict=True):
        assert batched["late_risk_score"] == pytest.approx(single.pop("late_risk_score"))
        assert {k: v for k, v in batched.items() if k != "late_risk_score"} == single


@pytest.mark.parametrize("zip_code", ["22041-001", "22041001", "22041", " 22041-001 "])
def test_cep_formats_resolve_to_the_same_prefix(client, zip_code):
    expected = client.post("/predict", json=order()).json()
    assert client.post("/predict", json=order(customer_zip_code=zip_code)).json() == expected


def test_purchase_time_with_offset_is_converted_to_sao_paulo(client):
    local = client.post("/predict", json=order(purchased_at="2018-06-12T14:30:00")).json()
    utc = client.post("/predict", json=order(purchased_at="2018-06-12T17:30:00Z")).json()
    assert utc == local


def test_quantity_equals_repeated_items(client):
    doubled = order(item={"quantity": 2})
    repeated = order()
    repeated["items"] = repeated["items"] * 2
    assert (
        client.post("/predict", json=doubled).json()
        == client.post("/predict", json=repeated).json()
    )


def test_unknown_seller_and_zip_are_scored_with_warnings(client):
    body = client.post(
        "/predict", json=order(item={"seller_id": "brand-new", "seller_zip_code": "69900"})
    ).json()
    assert any("seller without delivery history" in w for w in body["warnings"])
    assert any("origin zip prefix" in w for w in body["warnings"])


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(order(customer_state="XX"), id="unknown-state"),
        pytest.param(order(customer_zip_code="2204"), id="short-zip"),
        pytest.param(order(customer_zip_code="ABCDE"), id="non-digit-zip"),
        pytest.param(order(items=[]), id="no-items"),
        pytest.param(order(item={"price": 0}), id="zero-price"),
        pytest.param(order(item={"freight_value": -1}), id="negative-freight"),
        pytest.param(order(item={"quantity": 0}), id="zero-quantity"),
        pytest.param(order(item={"product_weight_g": -5}), id="negative-weight"),
        pytest.param(order(estimated_delivery_date="2018-06-01"), id="promise-before-purchase"),
        pytest.param(order(purchased_at="yesterday"), id="bad-timestamp"),
        pytest.param(order(approved_at="2018-06-13T10:00:00"), id="post-purchase-field"),
        pytest.param({k: v for k, v in order().items() if k != "items"}, id="missing-items"),
    ],
)
def test_invalid_orders_are_rejected_with_422(client, body):
    assert client.post("/predict", json=body).status_code == 422


def test_non_finite_numbers_are_rejected(client):
    body = json.dumps(order()).replace("89.9", "Infinity")
    response = client.post("/predict", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_purchase_before_the_snapshot_is_flagged(client):
    body = client.post(
        "/predict",
        json=order(purchased_at="2018-06-12T14:30:00", estimated_delivery_date="2018-07-03"),
    ).json()
    assert any("seller-history snapshot" in w for w in body["warnings"])


def test_one_seller_with_two_addresses_is_rejected(client):
    body = order()
    body["items"].append({**body["items"][0], "seller_zip_code": "01001"})
    assert client.post("/predict", json=body).status_code == 422


def test_batch_size_is_limited(client):
    assert client.post("/predict/batch", json={"orders": []}).status_code == 422
    too_many = {"orders": [order()] * (MAX_BATCH_SIZE + 1)}
    assert client.post("/predict/batch", json=too_many).status_code == 422


def test_openapi_carries_the_request_example(client):
    schema = client.get("/openapi.json").json()
    assert schema["components"]["schemas"]["OrderRequest"]["examples"] == [ORDER_EXAMPLE]
