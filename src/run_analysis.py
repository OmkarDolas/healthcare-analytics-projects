"""End-to-end Risk Adjustment analysis: load -> validate -> SQL reporting -> statistics -> charts,
Tableau extracts, interactive dashboard and a PowerPoint summary deck."""
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import statsmodels.formula.api as smf
from plotly.subplots import make_subplots
from scipy import stats

from build_deck import build_deck

ROOT = Path(__file__).resolve().parents[1]
DATA, SQL, OUT = ROOT / "data", ROOT / "sql", ROOT / "outputs"
TABLEAU, CHARTS = OUT / "tableau", OUT / "charts"


def load(con):
    my = pd.read_csv(DATA / "member_years.csv")
    for col in ("female", "dual_eligible"):
        my[col] = my[col].astype(int)
    my.to_sql("member_years", con, index=False)
    pd.read_csv(DATA / "hcc_reference.csv").to_sql("hcc_reference", con, index=False)


def run_sql(con, name):
    return pd.read_sql_query((SQL / name).read_text(), con)


def validate(con):
    dq = run_sql(con, "01_data_quality_checks.sql")
    dq["status"] = dq.failed_rows.map(lambda n: "PASS" if n == 0 else "FAIL - excluded")
    # failing records are quarantined, not silently dropped
    con.execute("""CREATE TABLE member_years_clean AS SELECT * FROM member_years
                    WHERE county IS NOT NULL AND county <> '' AND raf_score BETWEEN 0 AND 10""")
    excluded = con.execute("SELECT COUNT(*) FROM member_years").fetchone()[0] - \
        con.execute("SELECT COUNT(*) FROM member_years_clean").fetchone()[0]
    return dq, excluded


def statistics(clean):
    lines = []
    for seg in ("MA", "ACA"):
        s = clean[clean.segment == seg]
        a, b = s[s.payment_year == 2024].raf_score, s[s.payment_year == 2025].raf_score
        t, p = stats.ttest_ind(b, a, equal_var=False)
        lines.append(f"{seg}: mean RAF 2024 = {a.mean():.4f}, 2025 = {b.mean():.4f}, "
                     f"Welch t = {t:.2f}, p = {p:.2e}")
    model = smf.ols("raf_score ~ age + female + dual_eligible + hcc_count + C(segment)", data=clean).fit()
    lines += ["", "OLS: raf_score ~ age + female + dual_eligible + hcc_count + segment", str(model.summary().tables[1]),
              f"R-squared = {model.rsquared:.3f}"]
    return "\n".join(lines)


def charts(trend, recap, county):
    CHARTS.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    for (seg, plan), g in trend.groupby(["segment", "plan"]):
        ax[0].plot(g.payment_year, g.avg_raf, marker="o", label=f"{plan}")
    ax[0].set(title="Average RAF score by plan", xlabel="Payment year", ylabel="Avg RAF", xticks=[2023, 2024, 2025])
    ax[0].legend(fontsize=7)
    r = recap[recap.payment_year == recap.payment_year.max()].sort_values("recapture_rate_pct")
    ax[1].barh(r.plan, r.recapture_rate_pct, color="#1F3864")
    ax[1].set(title=f"HCC recapture rate, {r.payment_year.iloc[0]}", xlabel="% of prior-year HCCs recaptured")
    fig.tight_layout()
    fig.savefig(CHARTS / "raf_trend_and_recapture.png", dpi=130)
    plt.close(fig)

    fig = make_subplots(rows=2, cols=2, subplot_titles=(
        "Average RAF by plan", "HCC recapture rate by plan", "Average RAF by county (latest year)", "Members by plan"))
    for plan, g in trend.groupby("plan"):
        fig.add_scatter(x=g.payment_year, y=g.avg_raf, name=plan, mode="lines+markers", row=1, col=1)
    for plan, g in recap.groupby("plan"):
        fig.add_bar(x=g.payment_year.astype(str), y=g.recapture_rate_pct, name=f"{plan} recapture", row=1, col=2,
                    showlegend=False)
    for seg, g in county.groupby("segment"):
        fig.add_bar(x=g.county, y=g.avg_raf, name=f"{seg} county RAF", row=2, col=1)
    latest = trend[trend.payment_year == trend.payment_year.max()]
    fig.add_bar(x=latest.plan, y=latest.members, name="Members", row=2, col=2, showlegend=False)
    fig.update_layout(height=820, title="Medicare Advantage & ACA Risk Adjustment Dashboard (synthetic data)",
                      template="plotly_white", barmode="group")
    fig.write_html(OUT / "risk_adjustment_dashboard.html", include_plotlyjs="cdn")


def main():
    OUT.mkdir(exist_ok=True)
    TABLEAU.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(":memory:")
    load(con)
    dq, excluded = validate(con)
    trend = run_sql(con, "02_raf_trend_by_plan.sql")
    recap = run_sql(con, "03_hcc_recapture_rate.sql")
    prev = run_sql(con, "04_hcc_prevalence.sql")
    county = run_sql(con, "05_raf_by_county.sql")
    clean = pd.read_sql_query("SELECT * FROM member_years_clean", con)

    dq.to_csv(OUT / "data_quality_report.csv", index=False)
    for name, df in (("raf_trend_by_plan", trend), ("hcc_recapture_rate", recap),
                     ("hcc_prevalence", prev), ("raf_by_county", county)):
        df.to_csv(TABLEAU / f"{name}.csv", index=False)
    stats_txt = statistics(clean)
    (OUT / "statistical_tests.txt").write_text(stats_txt)
    charts(trend, recap, county)
    build_deck(OUT / "Risk_Adjustment_Insights.pptx", trend, recap, prev, dq, excluded, CHARTS)

    print(dq.to_string(index=False), f"\nExcluded records: {excluded}\n")
    print(trend.to_string(index=False), "\n")
    print(recap.to_string(index=False), "\n")
    print(stats_txt)


if __name__ == "__main__":
    main()
