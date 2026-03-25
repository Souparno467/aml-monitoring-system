from __future__ import annotations

import asyncio

from app.config import settings


class MLPredictor:
    def __init__(self) -> None:
        self._loaded = False
        self._xgb = None
        self._load_error: str | None = None

    def reset(self) -> None:
        self._loaded = False
        self._xgb = None
        self._load_error = None

    def _load(self) -> None:
        if self._loaded:
            return

        self._loaded = True
        self._load_error = None

        try:
            import joblib  # type: ignore
        except Exception:
            self._load_error = "joblib_not_available"
            return

        model_dir = settings.resolve_path(settings.ML_MODEL_PATH)
        xgb_path = model_dir / "xgb_aml_v1.joblib"
        if not xgb_path.exists():
            return

        try:
            self._xgb = joblib.load(xgb_path)
        except Exception as exc:
            # Do not leak local filesystem paths in error messages.
            self._xgb = None
            self._load_error = f"model_load_failed:{exc.__class__.__name__}"

    async def predict(self, features: dict) -> float:
        self._load()
        await asyncio.sleep(0)
        if self._xgb is None:
            return 0.0
        try:
            import pandas as pd  # type: ignore
        except Exception:
            return 0.0

        feature_names = getattr(self._xgb, "feature_names_in_", None)
        if feature_names is None:
            X = pd.DataFrame([features])
        else:
            X = pd.DataFrame(
                [[features.get(n, 0) for n in feature_names]],
                columns=list(feature_names),
            )
        proba = float(self._xgb.predict_proba(X)[0][1])
        return max(0.0, min(proba, 1.0))


ml_predictor = MLPredictor()
