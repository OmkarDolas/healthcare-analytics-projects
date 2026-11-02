"""Risk models: penalized logistic regression, gradient-boosted trees (XGBoost), and a PyTorch MLP.

Race and ethnicity are deliberately excluded as predictors; they are used only to audit
subgroup performance (see docs/model_card.md).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC = [
    "age", "sbp", "dbp", "bmi", "total_chol", "hdl", "ldl", "triglycerides", "hba1c", "glucose",
    "egfr", "creatinine", "heart_rate", "sbp_slope_per_year", "bmi_slope_per_year",
    "hba1c_slope_per_year", "n_bp_readings", "visits_prior_year", "acute_visits_3y",
]
BINARY = [
    "hx_hypertension", "hx_diabetes_t2", "hx_prediabetes", "hx_hyperlipidemia", "hx_ckd",
    "hx_obesity", "hx_afib", "rx_statin", "rx_antihypertensive", "rx_glucose_lowering",
]
CATEGORICAL = ["sex", "smoking"]
FEATURES = NUMERIC + BINARY + CATEGORICAL
LABEL = "cvd_5y"


def make_preprocessor() -> ColumnTransformer:
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
    ])
    return ColumnTransformer([
        ("num", numeric, NUMERIC),
        ("bin", "passthrough", BINARY),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
    ])


class LogisticModel:
    name = "logistic_regression"

    def __init__(self, C: float = 0.5, seed: int = 0):
        self.pipe = Pipeline([("prep", make_preprocessor()),
                              ("clf", LogisticRegression(C=C, max_iter=2000, random_state=seed))])

    def fit(self, X: pd.DataFrame, y: np.ndarray, X_val=None, y_val=None):
        self.pipe.fit(X[FEATURES], y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.pipe.predict_proba(X[FEATURES])[:, 1]


class XGBModel:
    name = "xgboost"

    def __init__(self, seed: int = 0):
        from xgboost import XGBClassifier
        self.prep = make_preprocessor()
        self.clf = XGBClassifier(
            n_estimators=600, learning_rate=0.03, max_depth=3, min_child_weight=5,
            subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0, eval_metric="logloss",
            early_stopping_rounds=50, random_state=seed, n_jobs=2)

    def fit(self, X, y, X_val, y_val):
        Xt = self.prep.fit_transform(X[FEATURES])
        Xv = self.prep.transform(X_val[FEATURES])
        self.clf.fit(Xt, y, eval_set=[(Xv, y_val)], verbose=False)
        return self

    def predict_proba(self, X):
        return self.clf.predict_proba(self.prep.transform(X[FEATURES]))[:, 1]


class TorchMLPModel:
    """Two-layer MLP in PyTorch with dropout, weight decay and early stopping on validation loss."""
    name = "pytorch_mlp"

    def __init__(self, hidden: int = 32, dropout: float = 0.3, lr: float = 1e-3,
                 weight_decay: float = 1e-3, max_epochs: int = 300, patience: int = 25, seed: int = 0):
        self.hparams = dict(hidden=hidden, dropout=dropout, lr=lr, weight_decay=weight_decay,
                            max_epochs=max_epochs, patience=patience)
        self.seed = seed
        self.prep = make_preprocessor()

    def fit(self, X, y, X_val, y_val):
        import torch
        from torch import nn

        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        Xt = torch.tensor(self.prep.fit_transform(X[FEATURES]), dtype=torch.float32)
        Xv = torch.tensor(self.prep.transform(X_val[FEATURES]), dtype=torch.float32)
        yt = torch.tensor(np.asarray(y), dtype=torch.float32)
        yv = torch.tensor(np.asarray(y_val), dtype=torch.float32)
        h = self.hparams
        self.net = nn.Sequential(
            nn.Linear(Xt.shape[1], h["hidden"]), nn.ReLU(), nn.Dropout(h["dropout"]),
            nn.Linear(h["hidden"], h["hidden"]), nn.ReLU(), nn.Dropout(h["dropout"]),
            nn.Linear(h["hidden"], 1))
        opt = torch.optim.AdamW(self.net.parameters(), lr=h["lr"], weight_decay=h["weight_decay"])
        loss_fn = nn.BCEWithLogitsLoss()
        best, best_state, wait = np.inf, None, 0
        loader = torch.utils.data.DataLoader(torch.utils.data.TensorDataset(Xt, yt),
                                             batch_size=128, shuffle=True,
                                             generator=torch.Generator().manual_seed(self.seed))
        for _ in range(h["max_epochs"]):
            self.net.train()
            for xb, yb in loader:
                opt.zero_grad()
                loss_fn(self.net(xb).squeeze(1), yb).backward()
                opt.step()
            self.net.eval()
            with torch.no_grad():
                val = loss_fn(self.net(Xv).squeeze(1), yv).item()
            if val < best - 1e-5:
                best, wait = val, 0
                best_state = {k: v.clone() for k, v in self.net.state_dict().items()}
            else:
                wait += 1
                if wait >= h["patience"]:
                    break
        self.net.load_state_dict(best_state)
        return self

    def predict_proba(self, X):
        import torch
        self.net.eval()
        with torch.no_grad():
            z = self.net(torch.tensor(self.prep.transform(X[FEATURES]), dtype=torch.float32))
        return torch.sigmoid(z).squeeze(1).numpy()


def available_models(seed: int = 0) -> list:
    models = [LogisticModel(seed=seed), XGBModel(seed=seed)]
    try:
        import torch  # noqa: F401
        models.append(TorchMLPModel(seed=seed))
    except Exception as err:  # ImportError, or a broken CUDA install that fails at import time
        print(f"PyTorch unavailable ({type(err).__name__}); skipping the MLP model.")
    return models
