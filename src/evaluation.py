"""Model evaluation beyond AUROC: discrimination, calibration, clinical utility, subgroups, shift.

All functions take numpy arrays of binary labels ``y`` and predicted risks ``p``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

EPS = 1e-6


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def _fit_logistic(x: np.ndarray, y: np.ndarray, offset: np.ndarray | None = None,
                  n_iter: int = 50) -> np.ndarray:
    """Unpenalized logistic regression by Newton-Raphson. ``x`` must include an intercept column."""
    offset = np.zeros(len(y)) if offset is None else offset
    beta = np.zeros(x.shape[1])
    for _ in range(n_iter):
        mu = _sigmoid(x @ beta + offset)
        w = mu * (1 - mu)
        grad = x.T @ (y - mu)
        hess = x.T @ (x * w[:, None]) + 1e-9 * np.eye(x.shape[1])
        step = np.linalg.solve(hess, grad)
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return beta


def calibration_intercept_slope(y: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    """Calibration-in-the-large (intercept with logit(p) as offset) and calibration slope.

    Ideal values: intercept 0, slope 1. Slope < 1 means predictions are too extreme (overfitting).
    """
    lp = _logit(p)
    ones = np.ones((len(y), 1))
    intercept = _fit_logistic(ones, y, offset=lp)[0]
    slope = _fit_logistic(np.column_stack([ones, lp]), y)[1]
    return float(intercept), float(slope)


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    """ECE with equal-frequency (quantile) bins."""
    order = np.argsort(p)
    bins = np.array_split(order, n_bins)
    return float(sum(len(b) / len(p) * abs(y[b].mean() - p[b].mean()) for b in bins if len(b)))


def reliability_curve(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    order = np.argsort(p)
    rows = []
    for b in np.array_split(order, n_bins):
        if len(b):
            rows.append({"mean_predicted": p[b].mean(), "observed_rate": y[b].mean(), "n": len(b)})
    return pd.DataFrame(rows)


def net_benefit(y: np.ndarray, p: np.ndarray, thresholds: np.ndarray) -> pd.DataFrame:
    """Decision curve analysis: net benefit of treating patients above each risk threshold."""
    n = len(y)
    prevalence = y.mean()
    rows = []
    for t in thresholds:
        treat = p >= t
        tp = np.sum(treat & (y == 1))
        fp = np.sum(treat & (y == 0))
        rows.append({
            "threshold": t,
            "net_benefit_model": tp / n - fp / n * t / (1 - t),
            "net_benefit_treat_all": prevalence - (1 - prevalence) * t / (1 - t),
            "net_benefit_treat_none": 0.0,
        })
    return pd.DataFrame(rows)


def point_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    out = {"n": len(y), "events": int(y.sum()), "event_rate": float(y.mean()),
           "mean_predicted": float(p.mean())}
    if 0 < y.sum() < len(y):
        out["auroc"] = float(roc_auc_score(y, p))
        out["auprc"] = float(average_precision_score(y, p))
        ci, cs = calibration_intercept_slope(y, p)
        out["calibration_intercept"] = ci
        out["calibration_slope"] = cs
    else:
        out.update(auroc=np.nan, auprc=np.nan, calibration_intercept=np.nan, calibration_slope=np.nan)
    brier = brier_score_loss(y, p)
    brier_ref = y.mean() * (1 - y.mean())
    out["brier"] = float(brier)
    out["scaled_brier"] = float(1 - brier / brier_ref) if brier_ref > 0 else np.nan
    out["observed_expected_ratio"] = float(y.mean() / p.mean()) if p.mean() > 0 else np.nan
    out["ece"] = expected_calibration_error(y, p)
    return out


def bootstrap_metrics(y: np.ndarray, p: np.ndarray, groups: np.ndarray, n_boot: int = 500,
                      seed: int = 0, metrics: tuple[str, ...] = ("auroc", "auprc", "brier",
                      "calibration_intercept", "calibration_slope", "observed_expected_ratio")
                      ) -> dict[str, float]:
    """Point estimates with 95% percentile CIs from a cluster bootstrap over persons.

    Persons can contribute several landmark rows, so resampling is done at the person level.
    """
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    groups = np.asarray(groups)
    est = point_metrics(y, p)
    uniq, inverse = np.unique(groups, return_inverse=True)
    members = [np.flatnonzero(inverse == i) for i in range(len(uniq))]
    rng = np.random.default_rng(seed)
    draws = {m: [] for m in metrics}
    for _ in range(n_boot):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([members[i] for i in pick])
        yb, pb = y[idx], p[idx]
        if yb.sum() == 0 or yb.sum() == len(yb):
            continue
        m = point_metrics(yb, pb)
        for k in metrics:
            draws[k].append(m[k])
    for k in metrics:
        arr = np.array(draws[k])
        est[f"{k}_lo"] = float(np.nanpercentile(arr, 2.5)) if len(arr) else np.nan
        est[f"{k}_hi"] = float(np.nanpercentile(arr, 97.5)) if len(arr) else np.nan
    return est


def subgroup_table(df: pd.DataFrame, p: np.ndarray, label: str, by: list[str],
                   min_events: int = 10) -> pd.DataFrame:
    """Per-subgroup discrimination and calibration. Flags subgroups too small to judge."""
    rows = []
    work = df.assign(_p=p)
    for col in by:
        for level, g in work.groupby(col, observed=True):
            m = point_metrics(g[label].to_numpy(), g["_p"].to_numpy())
            m.update(attribute=col, group=str(level),
                     reliable=bool(m["events"] >= min_events and m["n"] - m["events"] >= min_events))
            rows.append(m)
    cols = ["attribute", "group", "n", "events", "event_rate", "mean_predicted", "auroc", "auprc",
            "brier", "observed_expected_ratio", "calibration_intercept", "calibration_slope", "reliable"]
    return pd.DataFrame(rows)[cols]


# ---------------------------------------------------------------- dataset shift

def standardized_mean_differences(a: pd.DataFrame, b: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """SMD between two cohorts per feature. |SMD| > 0.1 is a common threshold for meaningful shift."""
    rows = []
    for c in columns:
        x, z = a[c].astype(float), b[c].astype(float)
        pooled = np.sqrt((x.var() + z.var()) / 2)
        smd = (z.mean() - x.mean()) / pooled if pooled > 0 else 0.0
        rows.append({"feature": c, "mean_source": x.mean(), "mean_target": z.mean(),
                     "missing_source": x.isna().mean(), "missing_target": z.isna().mean(),
                     "smd": smd})
    return pd.DataFrame(rows).sort_values("smd", key=np.abs, ascending=False)


def logistic_recalibration(y_cal: np.ndarray, p_cal: np.ndarray):
    """Fit intercept + slope recalibration on a target-site calibration sample; return a mapper."""
    lp = _logit(p_cal)
    beta = _fit_logistic(np.column_stack([np.ones(len(lp)), lp]), np.asarray(y_cal, float))

    def apply(p_new: np.ndarray) -> np.ndarray:
        return _sigmoid(beta[0] + beta[1] * _logit(np.asarray(p_new)))

    apply.coefficients = beta  # type: ignore[attr-defined]
    return apply


def intercept_recalibration(y_cal: np.ndarray, p_cal: np.ndarray):
    """Update only the intercept (re-anchor to the target site's baseline risk)."""
    lp = _logit(p_cal)
    a = _fit_logistic(np.ones((len(lp), 1)), np.asarray(y_cal, float), offset=lp)[0]

    def apply(p_new: np.ndarray) -> np.ndarray:
        return _sigmoid(a + _logit(np.asarray(p_new)))

    apply.coefficients = np.array([a, 1.0])  # type: ignore[attr-defined]
    return apply
