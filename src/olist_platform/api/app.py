"""FastAPI app: ``uvicorn --factory olist_platform.api.app:create_app``."""

import logging
import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from olist_platform.api.bundle import ModelBundle, resolve_bundle
from olist_platform.api.schemas import (
    BatchRequest,
    BatchResponse,
    Health,
    ModelInfo,
    ModelVersion,
    OrderRequest,
    Prediction,
)
from olist_platform.api.service import predict
from olist_platform.features import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

DEFAULT_BUNDLE_DIR = Path("models_export")


def load_from_env() -> ModelBundle:
    """Bundle from ``API_BUNDLE_DIR``, refreshed from ``MLFLOW_TRACKING_URI`` when it answers."""
    bundle_dir = Path(os.environ.get("API_BUNDLE_DIR", DEFAULT_BUNDLE_DIR))
    return resolve_bundle(bundle_dir, os.environ.get("MLFLOW_TRACKING_URI") or None)


def create_app(load_bundle: Callable[[], ModelBundle] = load_from_env) -> FastAPI:
    """App whose model is loaded once at startup by ``load_bundle``."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # A failed load keeps the process up so /health can report it instead of a crash loop.
        try:
            app.state.bundle = load_bundle()
        except Exception:
            logger.exception("Model bundle could not be loaded")
            app.state.bundle = None
        yield

    app = FastAPI(
        title="Olist delivery API",
        version="1.0.0",
        description=(
            "Predicts, at checkout, whether an Olist order will be delivered after the promised "
            "date and how many days it will take. Inputs are what is known at purchase time."
        ),
        lifespan=lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # The default handler echoes the rejected input, which fails to serialize for Infinity/NaN
        # (a 500 instead of a 422); location and message are enough for the client.
        detail = [
            {"type": error["type"], "loc": list(error["loc"]), "msg": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    def bundle_of(request: Request) -> ModelBundle:
        bundle = request.app.state.bundle
        if bundle is None:
            raise HTTPException(status_code=503, detail="model not loaded")
        return bundle

    @app.get("/health", response_model=Health, responses={503: {"model": Health}})
    def health(request: Request):
        """Ready when both models are loaded."""
        if request.app.state.bundle is None:
            return JSONResponse(
                status_code=503,
                content=Health(status="unavailable", model_loaded=False).model_dump(),
            )
        return Health(status="ok", model_loaded=True)

    @app.get("/model-info", response_model=ModelInfo)
    def model_info(request: Request) -> ModelInfo:
        """Champion versions, threshold and the snapshot date of the seller history."""
        bundle = bundle_of(request)
        metadata = bundle.metadata
        return ModelInfo(
            classifier=ModelVersion(**_version_fields(metadata["classifier"])),
            regressor=ModelVersion(**_version_fields(metadata["regressor"])),
            late_threshold=bundle.threshold,
            served_from=metadata.get("served_from", "export"),
            seller_history_as_of=metadata.get("seller_history_as_of"),
            exported_at=metadata.get("exported_at"),
            features=list(FEATURE_COLUMNS),
        )

    @app.post("/predict", response_model=Prediction)
    def predict_one(order: OrderRequest, request: Request) -> Prediction:
        """Score one order."""
        return predict([order], bundle_of(request))[0]

    @app.post("/predict/batch", response_model=BatchResponse)
    def predict_batch(batch: BatchRequest, request: Request) -> BatchResponse:
        """Score up to 1000 orders in one call."""
        return BatchResponse(predictions=predict(batch.orders, bundle_of(request)))

    return app


def _version_fields(entry: dict) -> dict:
    return {key: entry.get(key) for key in ("name", "version", "algorithm", "run_id")}
