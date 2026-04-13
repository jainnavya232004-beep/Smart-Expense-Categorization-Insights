"""Visualization helpers: pandas + numpy + matplotlib + seaborn. Saves PNGs under output_dir."""

import os
from typing import Dict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sns.set()

# --- helpers ---


def create_folder(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def _save_plot(output_dir: str, filename: str) -> str:
    create_folder(output_dir)
    path = os.path.join(output_dir, filename)
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def _blank(output_dir: str, filename: str, message: str) -> Dict[str, str]:
    plt.figure(figsize=(8, 4))
    plt.text(0.5, 0.5, message, ha="center", va="center")
    plt.axis("off")
    p = _save_plot(output_dir, filename)
    return {"chart_path": p, "insight": message}


def _debit_df(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["type"] == "debit"].copy()


def _wide_monthly(df: pd.DataFrame) -> pd.DataFrame:
    expense = _debit_df(df)
    return expense.pivot_table(index="month", columns="category", values="abs_amount", aggfunc="sum", fill_value=0)


# --- chart functions (signature used by app/services/charts.py) ---


def monthly_stacked_bar(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = _debit_df(df)
    if expense.empty:
        return _blank(output_dir, "monthly_stacked_bar.png", "No debit data for stacked bar")
    data = expense.groupby(["month", "category"])["abs_amount"].sum().unstack(fill_value=0)
    data.plot(kind="bar", stacked=True, figsize=(8, 4))
    plt.title("Monthly Spending (Stacked)")
    p = _save_plot(output_dir, "monthly_stacked_bar.png")
    top = data.sum(axis=1).idxmax()
    return {"chart_path": p, "insight": f"Highest total spending month: {top}."}


def monthly_line_trend(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = _debit_df(df)
    if expense.empty:
        return _blank(output_dir, "monthly_line_trend.png", "No debit data for monthly trend")
    s = expense.groupby("month")["abs_amount"].sum()
    plt.figure(figsize=(9, 4))
    plt.plot(s.index, s.values, marker="o")
    plt.title("Month-over-Month Spending")
    p = _save_plot(output_dir, "monthly_line_trend.png")
    return {"chart_path": p, "insight": f"Peaks in {s.idxmax()}, lowest in {s.idxmin()}."}


def month_category_heatmap(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = _debit_df(df)
    if expense.empty:
        return _blank(output_dir, "month_category_heatmap.png", "No debit data for heatmap")
    pivot = expense.pivot_table(index="month", columns="category", values="abs_amount", aggfunc="sum", fill_value=0)
    plt.figure(figsize=(10, 5))
    sns.heatmap(pivot, cmap="Blues")
    plt.title("Month vs Category Intensity")
    p = _save_plot(output_dir, "month_category_heatmap.png")
    mi = np.unravel_index(np.argmax(pivot.values), pivot.values.shape)
    return {
        "chart_path": p,
        "insight": f"Most intense: month {pivot.index[mi[0]]}, category {pivot.columns[mi[1]]}.",
    }


def box_plot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    plt.figure(figsize=(6, 4))
    sns.boxplot(x=df["abs_amount"])
    plt.title("Transaction Amount Spread")
    p = _save_plot(output_dir, "box_plot.png")
    q1, q3 = np.percentile(df["abs_amount"], [25, 75])
    iqr = q3 - q1
    outliers = int(((df["abs_amount"] < q1 - 1.5 * iqr) | (df["abs_amount"] > q3 + 1.5 * iqr)).sum())
    return {"chart_path": p, "insight": f"Detected {outliers} potential outliers."}


def violin_plot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    plt.figure(figsize=(6, 4))
    sns.violinplot(x=df["type"], y=df["abs_amount"])
    plt.title("Amount by Type")
    p = _save_plot(output_dir, "violin_plot.png")
    return {"chart_path": p, "insight": "Shows distribution shape by credit vs debit."}


def strip_plot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    plt.figure(figsize=(9, 4))
    sample = df.sample(min(800, len(df)), random_state=42)
    sns.stripplot(data=sample, x="category", y="abs_amount", jitter=0.25, size=3)
    plt.xticks(rotation=45)
    plt.title("Strip Plot")
    p = _save_plot(output_dir, "strip_plot.png")
    return {"chart_path": p, "insight": "Individual points per category."}


def swarm_plot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    plt.figure(figsize=(9, 4))
    sample = df.sample(min(400, len(df)), random_state=7)
    sns.swarmplot(data=sample, x="category", y="abs_amount", size=3)
    plt.xticks(rotation=45)
    plt.title("Swarm Plot")
    p = _save_plot(output_dir, "swarm_plot.png")
    return {"chart_path": p, "insight": "Non-overlapping points where possible."}


def histogram_plot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    plt.figure(figsize=(6, 4))
    sns.histplot(df["abs_amount"], bins=20)
    plt.title("Histogram")
    p = _save_plot(output_dir, "histogram_plot.png")
    return {"chart_path": p, "insight": "Frequency of transaction sizes."}


def kde_plot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    plt.figure(figsize=(6, 4))
    sns.kdeplot(df["abs_amount"], fill=True)
    plt.title("KDE Plot")
    p = _save_plot(output_dir, "kde_plot.png")
    return {"chart_path": p, "insight": "Smooth density of amounts."}


def joint_plot_food_travel(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    wide = _wide_monthly(df)
    if "Food" not in wide.columns or "Travel" not in wide.columns or len(wide) < 2:
        return _blank(output_dir, "joint_plot_food_travel.png", "Need Food and Travel across months")
    jp = sns.jointplot(x=wide["Food"], y=wide["Travel"], kind="scatter", height=6)
    jp.fig.suptitle("Food vs Travel (monthly)", y=1.02)
    create_folder(output_dir)
    path = os.path.join(output_dir, "joint_plot_food_travel.png")
    jp.savefig(path, dpi=120)
    plt.close("all")
    corr = float(np.corrcoef(wide["Food"], wide["Travel"])[0, 1])
    return {"chart_path": path, "insight": f"Monthly correlation Food vs Travel: {corr:.2f}."}


def pair_plot_categories(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    wide = _wide_monthly(df)
    if wide.shape[1] < 3 or len(wide) < 2:
        return _blank(output_dir, "pair_plot_categories.png", "Need at least 3 categories and 2 months")
    top_cols = wide.sum().sort_values(ascending=False).head(min(5, wide.shape[1])).index
    pp = sns.pairplot(wide[top_cols])
    create_folder(output_dir)
    path = os.path.join(output_dir, "pair_plot_categories.png")
    pp.savefig(path, dpi=120)
    plt.close("all")
    return {"chart_path": path, "insight": f"Pair plot for top categories: {', '.join(top_cols)}."}


def correlation_heatmap(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    wide = _wide_monthly(df)
    if wide.shape[1] < 2:
        return _blank(output_dir, "correlation_heatmap.png", "Need at least 2 categories")
    plt.figure(figsize=(8, 6))
    sns.heatmap(wide.corr(), annot=True, cmap="coolwarm", center=0)
    plt.title("Category Correlation")
    p = _save_plot(output_dir, "correlation_heatmap.png")
    return {"chart_path": p, "insight": "Positive cells: categories move together month to month."}


def pie_chart_category(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = _debit_df(df)
    if expense.empty:
        return _blank(output_dir, "pie_chart_category.png", "No debit data for pie")
    data = expense.groupby("category")["abs_amount"].sum()
    plt.figure(figsize=(7, 7))
    plt.pie(data.values, labels=data.index, autopct="%1.1f%%", startangle=90)
    plt.title("Category Share")
    p = _save_plot(output_dir, "pie_chart_category.png")
    return {"chart_path": p, "insight": f"Largest share: {data.idxmax()}."}


def bar_top_categories(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = _debit_df(df)
    if expense.empty:
        return _blank(output_dir, "bar_top_categories.png", "No debit data")
    data = expense.groupby("category")["abs_amount"].sum().sort_values(ascending=False).head(8)
    plt.figure(figsize=(9, 4))
    sns.barplot(x=data.index, y=data.values)
    plt.xticks(rotation=45)
    plt.title("Top Categories")
    p = _save_plot(output_dir, "bar_top_categories.png")
    return {"chart_path": p, "insight": f"Top category: {data.index[0]}."}


def count_plot_category(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    plt.figure(figsize=(9, 4))
    sns.countplot(data=df, x="category", order=df["category"].value_counts().index)
    plt.xticks(rotation=45)
    plt.title("Transactions per Category")
    p = _save_plot(output_dir, "count_plot_category.png")
    top = df["category"].value_counts().idxmax()
    return {"chart_path": p, "insight": f"Most frequent category: {top}."}


def weekly_monthly_comparison(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = _debit_df(df)
    if expense.empty:
        return _blank(output_dir, "weekly_monthly_comparison.png", "No debit data")
    weekly = expense.groupby("week")["abs_amount"].sum()
    monthly = expense.groupby("month")["abs_amount"].sum()
    plt.figure(figsize=(8, 4))
    plt.plot(weekly.index, weekly.values, marker="o", label="Weekly")
    plt.plot(monthly.index, monthly.values, marker="o", label="Monthly")
    plt.legend()
    plt.xticks(rotation=45)
    plt.title("Weekly vs Monthly")
    p = _save_plot(output_dir, "weekly_monthly_comparison.png")
    return {"chart_path": p, "insight": "Weekly shows short-term spikes; monthly shows trend."}


def weekday_weekend_bar(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = _debit_df(df)
    if expense.empty:
        return _blank(output_dir, "weekday_weekend_bar.png", "No debit data")
    g = expense.groupby("is_weekend")["abs_amount"].mean()
    labels = ["Weekday", "Weekend"]
    vals = [float(g.get(False, 0)), float(g.get(True, 0))]
    plt.figure(figsize=(6, 4))
    sns.barplot(x=labels, y=vals)
    plt.title("Avg Spending: Weekday vs Weekend")
    p = _save_plot(output_dir, "weekday_weekend_bar.png")
    insight = "Weekend average higher." if vals[1] > vals[0] else "Weekday average higher."
    return {"chart_path": p, "insight": insight}


def rolling_average_7day(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = _debit_df(df)
    if expense.empty:
        return _blank(output_dir, "rolling_average_7day.png", "No debit data")
    daily = expense.groupby(expense["date"].dt.date)["abs_amount"].sum().sort_index()
    roll = daily.rolling(window=7, min_periods=1).mean()
    plt.figure(figsize=(10, 4))
    plt.plot(daily.index, daily.values, alpha=0.35, label="Daily")
    plt.plot(roll.index, roll.values, color="red", label="7-day rolling")
    plt.legend()
    plt.xticks(rotation=45)
    plt.title("7-Day Rolling Average")
    p = _save_plot(output_dir, "rolling_average_7day.png")
    return {"chart_path": p, "insight": "Rolling average smooths daily noise."}


def cumulative_spending_curve(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = _debit_df(df)
    if expense.empty:
        return _blank(output_dir, "cumulative_spending_curve.png", "No debit data")
    daily = expense.groupby(expense["date"].dt.date)["abs_amount"].sum().sort_index()
    cum = daily.cumsum()
    plt.figure(figsize=(10, 4))
    plt.plot(cum.index, cum.values)
    plt.xticks(rotation=45)
    plt.title("Cumulative Spending")
    p = _save_plot(output_dir, "cumulative_spending_curve.png")
    return {"chart_path": p, "insight": f"Cumulative total: {cum.iloc[-1]:.2f}."}


def income_vs_expense_line(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    income = df[df["type"] == "credit"].groupby("month")["abs_amount"].sum()
    expense = df[df["type"] == "debit"].groupby("month")["abs_amount"].sum()
    if income.empty and expense.empty:
        return _blank(output_dir, "income_vs_expense_line.png", "No data")
    months = sorted(set(income.index) | set(expense.index))
    plt.figure(figsize=(9, 4))
    plt.plot(months, [income.get(m, 0) for m in months], marker="o", label="Income")
    plt.plot(months, [expense.get(m, 0) for m in months], marker="o", label="Expense")
    plt.legend()
    plt.title("Income vs Expense by Month")
    p = _save_plot(output_dir, "income_vs_expense_line.png")
    msg = (
        "Income above expense on average."
        if np.mean([income.get(m, 0) for m in months]) >= np.mean([expense.get(m, 0) for m in months])
        else "Expense dominates on average."
    )
    return {"chart_path": p, "insight": msg}


def dashboard_subplot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = _debit_df(df)
    if expense.empty:
        return _blank(output_dir, "dashboard_subplot.png", "No debit data for dashboard")
    by_cat = expense.groupby("category")["abs_amount"].sum().sort_values(ascending=False).head(6)
    monthly = expense.groupby("month")["abs_amount"].sum()
    daily = expense.groupby(expense["date"].dt.date)["abs_amount"].sum().sort_index()
    weekday = expense.groupby("day_name")["abs_amount"].sum()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = weekday.reindex(order).fillna(0)

    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    ax = axes.ravel()
    sns.barplot(x=by_cat.index, y=by_cat.values, ax=ax[0])
    ax[0].tick_params(axis="x", rotation=45)
    ax[0].set_title("Top Categories")
    ax[1].plot(monthly.index, monthly.values, marker="o")
    ax[1].set_title("Monthly")
    sns.histplot(df["abs_amount"], bins=25, ax=ax[2])
    ax[2].set_title("Histogram")
    roll = daily.rolling(7, min_periods=1).mean()
    ax[3].plot(roll.index, roll.values, color="red")
    ax[3].tick_params(axis="x", rotation=45)
    ax[3].set_title("7d rolling")
    sns.barplot(x=weekday.index, y=weekday.values, ax=ax[4])
    ax[4].tick_params(axis="x", rotation=45)
    ax[4].set_title("By weekday")
    inc = df[df["type"] == "credit"].groupby("month")["abs_amount"].sum()
    all_m = sorted(set(monthly.index) | set(inc.index))
    ax[5].plot(all_m, [inc.get(m, 0) for m in all_m], marker="o", label="Income")
    ax[5].plot(all_m, [monthly.get(m, 0) for m in all_m], marker="o", label="Expense")
    ax[5].legend()
    ax[5].set_title("Income vs Expense")
    plt.suptitle("Dashboard", y=1.02)
    create_folder(output_dir)
    path = os.path.join(output_dir, "dashboard_subplot.png")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return {"chart_path": path, "insight": "Combined view of key patterns."}


def load_and_prepare(csv_path: str) -> pd.DataFrame:
    """Load CSV for standalone use (same shape as batch pipeline)."""
    df = pd.read_csv(csv_path)
    expected = {"date", "description", "amount", "type"}
    colmap = {c.lower(): c for c in df.columns}
    rename = {colmap[k]: k for k in expected if k in colmap}
    df = df.rename(columns=rename)
    for need in expected:
        if need not in df.columns:
            df[need] = pd.NA
    df["description"] = df["description"].fillna("UNKNOWN TRANSACTION")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["type"] = df["type"].astype(str).str.strip().str.lower()
    inferred = np.where(df["amount"] < 0, "debit", "credit")
    df["type"] = np.where(df["type"].isin(["credit", "debit"]), df["type"], inferred)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").fillna(pd.Timestamp("1970-01-01"))
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["week"] = df["date"].dt.to_period("W").astype(str)
    df["day_name"] = df["date"].dt.day_name()
    df["is_weekend"] = df["date"].dt.dayofweek >= 5
    df["abs_amount"] = df["amount"].abs()
    if "category" not in df.columns:
        df["category"] = "Other"
    else:
        df["category"] = df["category"].fillna("Other")
    return df


def generate_all_visuals(csv_path: str, output_dir: str = "data/charts") -> Dict[str, Dict[str, str]]:
    df = load_and_prepare(csv_path)
    return {
        "monthly_stacked_bar": monthly_stacked_bar(df, output_dir),
        "monthly_line_trend": monthly_line_trend(df, output_dir),
        "month_category_heatmap": month_category_heatmap(df, output_dir),
        "box_plot": box_plot(df, output_dir),
        "violin_plot": violin_plot(df, output_dir),
        "strip_plot": strip_plot(df, output_dir),
        "swarm_plot": swarm_plot(df, output_dir),
        "histogram_plot": histogram_plot(df, output_dir),
        "kde_plot": kde_plot(df, output_dir),
        "joint_plot_food_travel": joint_plot_food_travel(df, output_dir),
        "pair_plot_categories": pair_plot_categories(df, output_dir),
        "correlation_heatmap": correlation_heatmap(df, output_dir),
        "pie_chart_category": pie_chart_category(df, output_dir),
        "bar_top_categories": bar_top_categories(df, output_dir),
        "count_plot_category": count_plot_category(df, output_dir),
        "weekly_monthly_comparison": weekly_monthly_comparison(df, output_dir),
        "weekday_weekend_bar": weekday_weekend_bar(df, output_dir),
        "rolling_average_7day": rolling_average_7day(df, output_dir),
        "cumulative_spending_curve": cumulative_spending_curve(df, output_dir),
        "income_vs_expense_line": income_vs_expense_line(df, output_dir),
        "dashboard_subplot": dashboard_subplot(df, output_dir),
    }
