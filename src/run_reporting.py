"""Monthly membership reporting cycle: load -> validate -> SQL reporting -> reconciliation ->
forecast + variance -> Power BI extracts, Excel workbook, charts and an interactive dashboard."""
import sqlite3
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from build_excel import build_workbook

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
DATA, SQL, OUT = ROOT / "data", ROOT / "sql", ROOT / "outputs"
PBI, CHARTS = OUT / "powerbi", OUT / "charts"
TRAIN_END, LAST_ACTUAL, HORIZON_END = "2025-12-01", "2026-09-01", "2027-12-01"


def load(con):
    for table, file in (("membership", "membership_monthly.csv"), ("finance", "finance_billed_membership.csv"),
                        ("budget", "budget_2026.csv"), ("dim_product", "dim_product.csv")):
        pd.read_csv(DATA / file).to_sql(table, con, index=False)


def q(con, name):
    return pd.read_sql_query((SQL / name).read_text(), con)


def holt_winters(series, steps):
    model = ExponentialSmoothing(series, trend="add", seasonal="add", seasonal_periods=12).fit()
    return model.forecast(steps)


def forecast(summary):
    """Back-test on Jan-Sep 2026 (model trained through Dec 2025), then refit on all actuals and project."""
    rows, accuracy = [], []
    for prod, g in summary.groupby("product"):
        s = g.set_index(pd.to_datetime(g.month)).members.asfreq("MS")
        train, test = s[:TRAIN_END], s[TRAIN_END:].iloc[1:]
        back = holt_winters(train, len(test))
        mape = float(np.mean(np.abs((test.values - back.values) / test.values)) * 100)
        accuracy.append((prod, round(mape, 2)))
        for m, a, f in zip(test.index, test.values, back.values):
            rows.append((m, prod, a, round(f), "backtest"))
        fut = holt_winters(s, len(pd.date_range(s.index[-1], HORIZON_END, freq="MS")) - 1)
        rows += [(m, prod, np.nan, round(f), "forecast") for m, f in fut.items()]
    fc = pd.DataFrame(rows, columns=["month", "product", "actual_members", "forecast_members", "type"])
    fc["variance"] = fc.actual_members - fc.forecast_members
    fc["variance_pct"] = (100 * fc.variance / fc.forecast_members).round(2)
    fc["flag"] = np.where(fc.variance_pct.abs() > 2, "RESEARCH", np.where(fc.type == "backtest", "OK", ""))
    return fc, pd.DataFrame(accuracy, columns=["product", "backtest_mape_pct"])


def powerbi_extracts(con, summary, fc, budget_var):
    """Star schema for Power BI: one fact per grain plus conformed dimensions."""
    PBI.mkdir(parents=True, exist_ok=True)
    pd.read_sql_query("SELECT * FROM membership", con).to_csv(PBI / "fact_membership.csv", index=False)
    pd.read_sql_query("SELECT * FROM budget", con).to_csv(PBI / "fact_budget.csv", index=False)
    fc.to_csv(PBI / "fact_forecast.csv", index=False, date_format="%Y-%m-%d")
    pd.read_sql_query("SELECT * FROM dim_product", con).to_csv(PBI / "dim_product.csv", index=False)
    dates = pd.DataFrame({"month": pd.date_range("2021-01-01", HORIZON_END, freq="MS")})
    dates["year"], dates["month_num"] = dates.month.dt.year, dates.month.dt.month
    dates["month_name"], dates["quarter"] = dates.month.dt.strftime("%b"), "Q" + dates.month.dt.quarter.astype(str)
    dates["is_enrollment_period"] = dates.month_num.isin([1, 2, 3])
    dates.to_csv(PBI / "dim_date.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame({"region": ["Philadelphia", "Montgomery", "Delaware", "Bucks", "Chester"],
                  "market": "Southeastern PA"}).to_csv(PBI / "dim_region.csv", index=False)


def sheets_extracts(con, summary, budget_var):
    """Flat CSV tabs that google_sheets/build_membership_report.gs imports into a Google Sheet."""
    gs = OUT / "google_sheets"
    gs.mkdir(exist_ok=True)
    data = summary.assign(year=summary.month.str[:4].astype(int))
    data.fillna("").to_csv(gs / "data.csv", index=False)
    pd.read_sql_query("SELECT * FROM dim_product", con).to_csv(gs / "products.csv", index=False)
    budget_var[["month", "product", "actual_members", "budget_members"]].to_csv(gs / "budget.csv", index=False)


def charts(summary, fc, recon):
    CHARTS.mkdir(parents=True, exist_ok=True)
    total = summary.groupby("month").members.sum()
    total.index = pd.to_datetime(total.index)
    fct = fc[fc.type == "forecast"].groupby("month").forecast_members.sum()
    bt = fc[fc.type == "backtest"].groupby("month").forecast_members.sum()

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.3))
    ax[0].plot(total.index, total / 1000, label="Actual", color="#1F3864")
    ax[0].plot(bt.index, bt / 1000, "--", label="Back-test forecast", color="#C55A11")
    ax[0].plot(fct.index, fct / 1000, ":", label="Forecast", color="#548235")
    ax[0].set(title="Total membership (thousands)", ylabel="Members (K)")
    ax[0].legend()
    lb = summary[summary.month == LAST_ACTUAL].sort_values("yoy_pct")
    ax[1].barh(lb["product"], lb.yoy_pct, color=np.where(lb.yoy_pct < 0, "#C00000", "#1F3864"))
    ax[1].set(title=f"YoY membership growth, {pd.Timestamp(LAST_ACTUAL):%b %Y}", xlabel="% change")
    fig.tight_layout()
    fig.savefig(CHARTS / "membership_trend_forecast.png", dpi=130)
    plt.close(fig)

    fig = make_subplots(rows=2, cols=2, subplot_titles=(
        "Membership by product", "Actual vs forecast (total)", "YoY growth by product (latest month)",
        "Finance reconciliation exceptions"))
    for prod, g in summary.groupby("product"):
        fig.add_scatter(x=g.month, y=g.members, name=prod, row=1, col=1)
    fig.add_scatter(x=total.index, y=total, name="Actual total", row=1, col=2, line=dict(color="#1F3864"))
    fig.add_scatter(x=bt.index, y=bt, name="Back-test", row=1, col=2, line=dict(dash="dash"))
    fig.add_scatter(x=fct.index, y=fct, name="Forecast", row=1, col=2, line=dict(dash="dot"))
    fig.add_bar(x=lb["product"], y=lb.yoy_pct, name="YoY %", row=2, col=1, showlegend=False)
    ex = recon[recon.status != "OK"]
    fig.add_bar(x=ex["product"] + " " + ex.region + " " + ex.month.str[:7], y=ex.variance_pct, row=2, col=2,
                name="Variance %", showlegend=False)
    fig.update_layout(height=820, template="plotly_white",
                      title="Membership Reporting & Forecasting Dashboard (synthetic data)")
    fig.write_html(OUT / "membership_dashboard.html", include_plotlyjs="cdn")


def main():
    OUT.mkdir(exist_ok=True)
    con = sqlite3.connect(":memory:")
    load(con)
    checks = q(con, "04_data_validation.sql")
    summary = q(con, "01_membership_summary.sql")
    recon = q(con, "02_finance_reconciliation.sql")
    budget_var = q(con, "03_budget_variance.sql")
    fc, acc = forecast(summary)

    checks.to_csv(OUT / "data_validation_report.csv", index=False)
    recon[recon.status != "OK"].to_csv(OUT / "reconciliation_exceptions.csv", index=False)
    acc.to_csv(OUT / "forecast_accuracy.csv", index=False)
    powerbi_extracts(con, summary, fc, budget_var)
    charts(summary, fc, recon)
    build_workbook(OUT / "Membership_Report.xlsx", summary, budget_var, fc, recon, con)
    sheets_extracts(con, summary, budget_var)

    print(checks.to_string(index=False), "\n")
    print(acc.to_string(index=False), "\n")
    print(recon[recon.status != "OK"].to_string(index=False), "\n")
    print(budget_var[budget_var.month == LAST_ACTUAL].to_string(index=False))
    print(fc[fc.flag == "RESEARCH"].to_string(index=False))


if __name__ == "__main__":
    main()
