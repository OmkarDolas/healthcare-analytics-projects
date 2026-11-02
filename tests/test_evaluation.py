import numpy as np
import pandas as pd

from src import evaluation as ev


def _simulate(n=20000, seed=0, scale=1.0, shift=0.0):
    rng = np.random.default_rng(seed)
    lp = rng.normal(-2, 1, n)
    y = rng.binomial(1, 1 / (1 + np.exp(-lp)))
    p = 1 / (1 + np.exp(-(shift + scale * lp)))
    return y.astype(float), p


def test_perfectly_calibrated_model_has_intercept_0_slope_1():
    y, p = _simulate()
    intercept, slope = ev.calibration_intercept_slope(y, p)
    assert abs(intercept) < 0.06
    assert abs(slope - 1) < 0.06
    assert ev.expected_calibration_error(y, p) < 0.01


def test_overconfident_model_has_slope_below_1():
    y, p = _simulate(scale=2.0)
    _, slope = ev.calibration_intercept_slope(y, p)
    assert 0.4 < slope < 0.6


def test_overpredicting_model_has_negative_intercept_and_oe_below_1():
    y, p = _simulate(shift=1.0)
    m = ev.point_metrics(y, p)
    assert m["calibration_intercept"] < -0.8
    assert m["observed_expected_ratio"] < 1


def test_logistic_recalibration_repairs_miscalibration():
    y, p = _simulate(n=120000, scale=2.0, shift=0.7, seed=1)
    half = len(y) // 2
    recal = ev.logistic_recalibration(y[:half], p[:half])
    before = ev.point_metrics(y[half:], p[half:])
    after = ev.point_metrics(y[half:], recal(p[half:]))
    assert abs(after["calibration_slope"] - 1) < 0.1
    assert after["ece"] < before["ece"]
    # recalibration is monotone, so discrimination is unchanged
    assert abs(after["auroc"] - before["auroc"]) < 1e-9


def test_net_benefit_treat_none_is_zero_and_treat_all_matches_formula():
    y = np.array([1, 0, 0, 0])
    nb = ev.net_benefit(y, np.full(4, 0.5), np.array([0.2]))
    assert nb.net_benefit_treat_none.iloc[0] == 0
    assert np.isclose(nb.net_benefit_treat_all.iloc[0], 0.25 - 0.75 * 0.25)


def test_bootstrap_ci_brackets_point_estimate():
    y, p = _simulate(n=3000)
    groups = np.repeat(np.arange(1500), 2)
    m = ev.bootstrap_metrics(y, p, groups, n_boot=100)
    assert m["auroc_lo"] <= m["auroc"] <= m["auroc_hi"]


def test_subgroup_table_flags_small_groups():
    y, p = _simulate(n=1000)
    df = pd.DataFrame({"y": y, "grp": ["big"] * 980 + ["small"] * 20})
    tab = ev.subgroup_table(df, p, "y", ["grp"])
    assert not tab.set_index("group").loc["small", "reliable"]


def test_smd_detects_shift():
    a = pd.DataFrame({"x": np.random.default_rng(0).normal(0, 1, 500)})
    b = pd.DataFrame({"x": np.random.default_rng(1).normal(0.5, 1, 500)})
    smd = ev.standardized_mean_differences(a, b, ["x"])
    assert 0.35 < smd.smd.iloc[0] < 0.65
