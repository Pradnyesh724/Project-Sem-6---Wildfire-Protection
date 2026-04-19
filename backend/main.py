import json
import pickle
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

FEATURE_COLUMNS = ["temperature", "NDVI", "humidity", "wind_speed", "slope"]

model = None


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature: float = Field(..., description="Air temperature")
    NDVI: float = Field(..., description="Normalized Difference Vegetation Index")
    humidity: float = Field(..., description="Relative humidity")
    wind_speed: float = Field(..., description="Wind speed")
    slope: float = Field(..., description="Terrain slope")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    model_path = Path(__file__).resolve().parent / "model" / "model.pkl"
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    print("Model loaded successfully.")
    yield


app = FastAPI(lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = err.get("loc") or ()
        path = [str(p) for p in loc if p not in ("body", "query", "path")]
        field = ".".join(path) if path else "request"
        details.append({"field": field, "message": err.get("msg", "Invalid value")})
    return JSONResponse(
        status_code=422,
        content={"error": "Invalid input", "details": details},
    )


@app.exception_handler(json.JSONDecodeError)
async def json_decode_exception_handler(
    request: Request, exc: json.JSONDecodeError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": "Invalid JSON",
            "details": [{"field": "body", "message": "Request body must be valid JSON"}],
        },
    )


def risk_category(score: float) -> str:
    if score < 0.3:
        return "Low"
    if score <= 0.7:
        return "Medium"
    return "High"


def predict_fire_probability(m: Any, X: pd.DataFrame) -> float:
    proba = m.predict_proba(X)
    return float(proba[0][1])


@app.get("/")
def root():
    return {"message": "Wildfire Risk API is running"}


@app.post("/predict")
def predict(body: PredictRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")

    row_values = [
        body.temperature,
        body.NDVI,
        body.humidity,
        body.wind_speed,
        body.slope,
    ]
    feature_dict = dict(zip(FEATURE_COLUMNS, row_values))
    df = pd.DataFrame([row_values], columns=FEATURE_COLUMNS)

    print(f"[predict] input features: {feature_dict}")

    risk_score = predict_fire_probability(model, df)

    print(f"[predict] predict_proba [0][1] (P positive class): {risk_score}")

    return {
        "risk_score": risk_score,
        "risk_category": risk_category(risk_score),
    }
