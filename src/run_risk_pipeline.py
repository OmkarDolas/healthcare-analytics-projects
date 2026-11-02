"""Train 5-year CVD risk models and evaluate them beyond AUROC.

Validation design
-----------------
* Development site (Massachusetts) persons are split 70/30 at the person level.
* Train:          70% persons, landmarks 2006-2014 (20% of those persons held out for early stopping
                  and model selection).
* Internal test:  30% held-out persons, landmarks 2006-2014.
* Temporal test:  30% held-out persons, landmark 2018 (later period, never seen in training).
* External test:  a separately simulated Chicago, Illinois population (dataset shift).

Usage:
    python -m src.run_risk_pipeline --dev data/analytic_dev.parquet --ext data/analytic_ext.parquet
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import log_loss, roc_auc_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from src import evaluation as ev  # noqa: E402
from src.models import BINARY, FEATURES, LABEL, NUMERIC, available_models, make_preprocessor  # noqa: E402
from src.shift_scenarios import SCENARIOS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
FIG = OUT / "figures"
SEED = 20240501
TRAIN_LANDMARKS = [2006, 2010, 2014]
TEMPORAL_LANDMARK = 2018
COLORS = {"logistic_regression": "#2563eb", "xgboost": "#d97706", "pytorch_mlp": "#059669"}


def person_split(ids: np.ndarray, frac: float, seed: int) -> tuple[set, set]:
    uniq = np.unique(ids)
    rng = np.random.default_rng(seed)
    rng.shuffle(uniq)
    cut = int(len(uniq) * frac)
    return set(uniq[:cut]), set(uniq[cut:])


def add_age_band(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(age_band=pd.cut(df["age"], [40, 55, 65, 80], right=False,
                                      labels=["40-54", "55-64", "65-79"]))


def make_splits(dev: pd.DataFrame, ext: pd.DataFrame) -> dict[str, pd.DataFrame]:
    train_ids, test_ids = person_split(dev.person_id.to_numpy(), 0.7, SEED)
    fit_ids, val_ids = person_split(np.array(sorted(train_ids)), 0.8, SEED + 1)
    early = dev.landmark_year.isin(TRAIN_LANDMARKS)
    return {
        "train": dev[early & dev.person_id.isin(fit_ids)],
        "validation": dev[early & dev.person_id.isin(val_ids)],
        "internal_test": dev[early & dev.person_id.isin(test_ids)],
        "temporal_test": dev[(dev.landmark_year == TEMPORAL_LANDMARK) & dev.person_id.isin(test_ids)],
        "external_test": ext,
    }


def domain_classifier_auc(a: pd.DataFrame, b: pd.DataFrame) -> float:
    """Cross-validated AUROC of a classifier that tries to tell cohort a from cohort b.

    0.5 means the cohorts are indistinguishable on the model's features; higher means more shift.
    """
    both = pd.concat([a.assign(_d=0), b.assign(_d=1)], ignore_index=True)
    groups = both["person_id"].astype(str) + both["_d"].astype(str)
    scores = np.zeros(len(both))
    for tr, te in GroupKFold(n_splits=5).split(both, both["_d"], groups):
        prep = make_preprocessor()
        clf = LogisticRegression(max_iter=2000)
        clf.fit(prep.fit_transform(both.iloc[tr][FEATURES]), both.iloc[tr]["_d"])
        scores[te] = clf.predict_proba(prep.transform(both.iloc[te][FEATURES]))[:, 1]
    return float(roc_auc_score(both["_d"], scores))


def plot_calibration(preds: dict, splits: dict, path: Path) -> None:
    panels = ["internal_test", "temporal_test", "external_test"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), sharex=True, sharey=True)
    lim = 0
    for ax, split in zip(axes, panels):
        y = splits[split][LABEL].to_numpy()
        for model, p_by_split in preds.items():
            rc = ev.reliability_curve(y, p_by_split[split], n_bins=8)
            lim = max(lim, rc.mean_predicted.max(), rc.observed_rate.max())
            ax.plot(rc.mean_predicted, rc.observed_rate, "o-", color=COLORS[model], label=model, ms=4)
        ax.set_title(split.replace("_", " "))
        ax.set_xlabel("Mean predicted 5-year risk")
        ax.grid(alpha=0.3)
    for ax in axes:
        ax.plot([0, lim * 1.05], [0, lim * 1.05], "--", color="grey", lw=1, label="perfect calibration")
    axes[0].set_ylabel("Observed 5-year event rate")
    axes[0].legend(fontsize=8, loc="upper left")
    fig.suptitle("Calibration (reliability) curves, octiles of predicted risk")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_subgroups(sub: pd.DataFrame, overall_auc: float, path: Path) -> None:
    sub = sub.copy()
    sub["label"] = sub["attribute"] + ": " + sub["group"] + "  (n=" + sub["n"].astype(str) + \
        ", events=" + sub["events"].astype(str) + ")"
    fig, axes = plt.subplots(1, 2, figsize=(13, 0.42 * len(sub) + 1.5), sharey=True)
    ypos = np.arange(len(sub))[::-1]
    colors = np.where(sub["reliable"], "#2563eb", "#9ca3af")
    axes[0].scatter(sub["auroc"], ypos, c=colors)
    axes[0].axvline(overall_auc, ls="--", color="grey", lw=1)
    axes[0].set_xlabel("AUROC")
    axes[0].set_yticks(ypos, sub["label"], fontsize=8)
    axes[1].scatter(sub["observed_expected_ratio"], ypos, c=colors)
    axes[1].axvline(1.0, ls="--", color="grey", lw=1)
    axes[1].set_xlabel("Observed / expected events (1.0 = calibrated)")
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.suptitle("Subgroup performance on held-out persons (grey = fewer than 10 events or non-events)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_shift(smd: pd.DataFrame, path: Path, top: int = 15) -> None:
    s = smd.head(top).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 0.35 * len(s) + 1.2))
    ax.barh(s["feature"], s["smd"], color=np.where(s["smd"].abs() > 0.1, "#dc2626", "#9ca3af"))
    ax.axvline(0.1, ls="--", color="grey", lw=1)
    ax.axvline(-0.1, ls="--", color="grey", lw=1)
    ax.set_xlabel("Standardized mean difference, external vs development (|SMD| > 0.1 = shift)")
    ax.set_title("Covariate shift: Illinois vs Massachusetts")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_recalibration(y, curves: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 4.8))
    lim = 0
    for label, p in curves.items():
        rc = ev.reliability_curve(y, p, n_bins=8)
        lim = max(lim, rc.mean_predicted.max(), rc.observed_rate.max())
        ax.plot(rc.mean_predicted, rc.observed_rate, "o-", label=label, ms=4)
    ax.plot([0, lim * 1.05], [0, lim * 1.05], "--", color="grey", lw=1)
    ax.set_xlabel("Mean predicted 5-year risk")
    ax.set_ylabel("Observed 5-year event rate")
    ax.set_title("External site: before and after recalibration")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_decision_curve(dca: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 4.5))
    for model, g in dca.groupby("model"):
        ax.plot(g.threshold, g.net_benefit_model, color=COLORS[model], label=model)
    g = dca[dca.model == dca.model.iloc[0]]
    ax.plot(g.threshold, g.net_benefit_treat_all, color="black", ls=":", label="treat all")
    ax.axhline(0, color="grey", lw=1, label="treat none")
    ymax = dca.net_benefit_model.max()
    ax.set_ylim(-0.01, ymax * 1.3 if ymax > 0 else 0.05)
    ax.set_xlabel("Risk threshold for intervention")
    ax.set_ylabel("Net benefit")
    ax.set_title("Decision curve, internal test")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_stress(stress: pd.DataFrame, path: Path) -> None:
    scen = list(dict.fromkeys(stress.scenario))
    fig, axes = plt.subplots(1, 3, figsize=(15, 3.6), sharey=True)
    ypos = np.arange(len(scen))[::-1]
    for ax, (metric, ref, label) in zip(axes, [("auroc", None, "AUROC"),
                                              ("observed_expected_ratio", 1.0, "Observed / expected events"),
                                              ("calibration_slope", 1.0, "Calibration slope")]):
        for variant, marker, color in [("as deployed", "o", "#dc2626"), ("after recalibration", "s", "#2563eb")]:
            v = stress[stress.variant == variant].set_index("scenario").loc[scen, metric]
            ax.scatter(v, ypos, marker=marker, color=color, label=variant, s=40)
        if ref is not None:
            ax.axvline(ref, ls="--", color="grey", lw=1)
        ax.set_xlabel(label)
        ax.grid(alpha=0.3)
    axes[0].set_yticks(ypos, scen, fontsize=8)
    axes[2].legend(fontsize=8, loc="lower right")
    fig.suptitle("Controlled dataset-shift stress tests on the external cohort")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run(dev_path: str, ext_path: str, n_boot: int = 500) -> dict:
    OUT.mkdir(exist_ok=True)
    FIG.mkdir(exist_ok=True)
    dev = add_age_band(pd.read_parquet(dev_path))
    ext = add_age_band(pd.read_parquet(ext_path))
    splits = make_splits(dev, ext)

    cohort = pd.DataFrame([{"split": k, "rows": len(v), "persons": v.person_id.nunique(),
                            "events": int(v[LABEL].sum()), "event_rate": v[LABEL].mean(),
                            "landmarks": ",".join(map(str, sorted(v.landmark_year.unique())))}
                           for k, v in splits.items()])
    cohort.to_csv(OUT / "cohort_summary.csv", index=False)
    print(cohort.to_string(index=False))

    # ---- fit models, select primary model on validation log loss
    preds, val_loss, fitted = {}, {}, {}
    for model in available_models(seed=SEED):
        tr, va = splits["train"], splits["validation"]
        model.fit(tr, tr[LABEL].to_numpy(), va, va[LABEL].to_numpy())
        fitted[model.name] = model
        preds[model.name] = {k: model.predict_proba(v) for k, v in splits.items()}
        val_loss[model.name] = log_loss(va[LABEL], preds[model.name]["validation"])
    primary = min(val_loss, key=val_loss.get)
    print("validation log loss:", {k: round(v, 4) for k, v in val_loss.items()}, "-> primary:", primary)

    # ---- overall metrics with person-level bootstrap CIs
    rows = []
    for model, by_split in preds.items():
        for split in ["internal_test", "temporal_test", "external_test"]:
            d = splits[split]
            m = ev.bootstrap_metrics(d[LABEL].to_numpy(), by_split[split], d.person_id.to_numpy(),
                                     n_boot=n_boot, seed=SEED)
            rows.append({"model": model, "split": split, **m})
    overall = pd.DataFrame(rows)
    overall.to_csv(OUT / "metrics_overall.csv", index=False)

    # ---- subgroup performance on all held-out persons (internal + temporal)
    held = pd.concat([splits["internal_test"], splits["temporal_test"]])
    p_held = np.concatenate([preds[primary]["internal_test"], preds[primary]["temporal_test"]])
    sub = ev.subgroup_table(held, p_held, LABEL, ["sex", "age_band", "race", "ethnicity"])
    sub.insert(0, "model", primary)
    sub.to_csv(OUT / "subgroup_performance.csv", index=False)

    # ---- dataset shift: covariates, label, domain classifier, and a temporal comparison
    num_cols = NUMERIC + BINARY + [LABEL]
    smd = ev.standardized_mean_differences(dev, ext, num_cols)
    smd.to_csv(OUT / "dataset_shift_smd.csv", index=False)
    dev_early = dev[dev.landmark_year.isin(TRAIN_LANDMARKS)]
    dev_late = dev[dev.landmark_year == TEMPORAL_LANDMARK]
    smd_time = ev.standardized_mean_differences(dev_early, dev_late, num_cols)
    smd_time.to_csv(OUT / "temporal_shift_smd.csv", index=False)
    shift_summary = pd.DataFrame([
        {"comparison": "external (IL) vs development (MA)",
         "domain_classifier_auroc": domain_classifier_auc(dev, ext),
         "features_abs_smd_gt_0.1": int((smd["smd"].abs() > 0.1).sum()),
         "event_rate_source": dev[LABEL].mean(), "event_rate_target": ext[LABEL].mean()},
        {"comparison": "2018 vs 2006-2014 (development site)",
         "domain_classifier_auroc": domain_classifier_auc(dev_early, dev_late),
         "features_abs_smd_gt_0.1": int((smd_time["smd"].abs() > 0.1).sum()),
         "event_rate_source": dev_early[LABEL].mean(), "event_rate_target": dev_late[LABEL].mean()},
    ])
    shift_summary.to_csv(OUT / "shift_summary.csv", index=False)

    # ---- external recalibration: fit on half of external persons, evaluate on the other half
    ext_d = splits["external_test"]
    cal_ids, eval_ids = person_split(ext_d.person_id.to_numpy(), 0.5, SEED + 2)
    cal_mask = ext_d.person_id.isin(cal_ids).to_numpy()
    p_ext = preds[primary]["external_test"]
    y_ext = ext_d[LABEL].to_numpy()
    recal_int = ev.intercept_recalibration(y_ext[cal_mask], p_ext[cal_mask])
    recal_log = ev.logistic_recalibration(y_ext[cal_mask], p_ext[cal_mask])
    y_eval, p_eval = y_ext[~cal_mask], p_ext[~cal_mask]
    variants = {"original": p_eval, "intercept update": recal_int(p_eval),
                "logistic recalibration": recal_log(p_eval)}
    recal = pd.DataFrame([{"model": primary, "variant": k, **ev.point_metrics(y_eval, v)}
                          for k, v in variants.items()])
    recal.to_csv(OUT / "recalibration_external.csv", index=False)

    # ---- controlled shift stress tests on the external cohort, with recalibration as the repair
    stress_rows = []
    for name, fn in SCENARIOS.items():
        shifted = fn(ext_d, SEED + 3)
        p_s = fitted[primary].predict_proba(shifted)
        y_s = shifted[LABEL].to_numpy()
        cal, evl = person_split(shifted.person_id.to_numpy(), 0.5, SEED + 4)
        cmask = shifted.person_id.isin(cal).to_numpy()
        repaired = ev.logistic_recalibration(y_s[cmask], p_s[cmask])(p_s[~cmask])
        dom = domain_classifier_auc(dev, shifted) if name.startswith(("case", "measure")) else np.nan
        for variant, pv in [("as deployed", p_s[~cmask]), ("after recalibration", repaired)]:
            stress_rows.append({"scenario": name, "variant": variant, "domain_classifier_auroc": dom,
                                **ev.point_metrics(y_s[~cmask], pv)})
    stress = pd.DataFrame(stress_rows)
    stress.to_csv(OUT / "shift_stress_tests.csv", index=False)

    # ---- decision curve on internal test
    thresholds = np.round(np.arange(0.02, 0.41, 0.01), 2)
    dca = pd.concat([ev.net_benefit(splits["internal_test"][LABEL].to_numpy(), p["internal_test"],
                                    thresholds).assign(model=m) for m, p in preds.items()])
    dca.to_csv(OUT / "decision_curve.csv", index=False)

    # ---- logistic regression coefficients (interpretability)
    if "logistic_regression" in fitted:
        lr = fitted["logistic_regression"].pipe
        names = lr.named_steps["prep"].get_feature_names_out()
        coefs = pd.DataFrame({"feature": names, "coefficient": lr.named_steps["clf"].coef_[0]})
        coefs.assign(odds_ratio_per_unit=np.exp(coefs.coefficient)) \
             .sort_values("coefficient", key=np.abs, ascending=False) \
             .to_csv(OUT / "logistic_coefficients.csv", index=False)

    # ---- figures
    plot_calibration(preds, splits, FIG / "calibration_curves.png")
    auc_int = overall.query("model == @primary and split == 'internal_test'")["auroc"].iloc[0]
    plot_subgroups(sub, auc_int, FIG / "subgroup_performance.png")
    plot_shift(smd[smd.feature != LABEL], FIG / "dataset_shift_smd.png")
    plot_recalibration(y_eval, variants, FIG / "external_recalibration.png")
    plot_decision_curve(dca, FIG / "decision_curve.png")
    plot_stress(stress, FIG / "shift_stress_tests.png")

    results = {"primary_model": primary, "validation_log_loss": val_loss,
               "cohort": cohort.to_dict("records"), "overall": overall.to_dict("records"),
               "shift": shift_summary.to_dict("records"), "recalibration": recal.to_dict("records"),
               "stress_tests": stress.to_dict("records")}
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=float))
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dev", default=str(ROOT / "data" / "analytic_dev.parquet"))
    ap.add_argument("--ext", default=str(ROOT / "data" / "analytic_ext.parquet"))
    ap.add_argument("--n-boot", type=int, default=500)
    args = ap.parse_args()
    res = run(args.dev, args.ext, args.n_boot)
    cols = ["model", "split", "n", "events", "auroc", "auroc_lo", "auroc_hi", "brier",
            "calibration_intercept", "calibration_slope", "observed_expected_ratio", "ece"]
    print(pd.DataFrame(res["overall"])[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
