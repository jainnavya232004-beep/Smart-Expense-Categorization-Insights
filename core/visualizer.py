import os
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


sns.set_theme(style="whitegrid")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _save_fig(fig, output_dir: str, filename: str) -> str:
    _ensure_dir(output_dir)
    path = os.path.join(output_dir, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _blank_chart(output_dir: str, filename: str, message: str) -> Dict[str, str]:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.text(0.5, 0.5, message, ha="center", va="center")
    ax.axis("off")
    p = _save_fig(fig, output_dir, filename)
    return {"chart_path": p, "insight": message}


def load_and_prepare(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    expected = {"date", "description", "amount", "type"}
    missing = expected - set(df.columns.str.lower())
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    colmap = {c.lower(): c for c in df.columns}
    df = df.rename(columns={colmap[k]: k for k in expected})

    # Safe fill (simple and explicit)
    df["description"] = df["description"].fillna("UNKNOWN TRANSACTION")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["type"] = df["type"].astype(str).str.strip().str.lower()
    inferred_type = np.where(df["amount"] < 0, "debit", "credit")
    df["type"] = np.where(df["type"].isin(["credit", "debit"]), df["type"], inferred_type)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["date"] = df["date"].fillna(pd.Timestamp("1970-01-01"))
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


def monthly_stacked_bar(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = df[df["type"] == "debit"]
    if expense.empty:
        return _blank_chart(output_dir, "monthly_stacked_bar.png", "No debit data for monthly stacked bar")

    pivot = expense.pivot_table(index="month", columns="category", values="abs_amount", aggfunc="sum", fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 5))
    pivot.plot(kind="bar", stacked=True, ax=ax)
    ax.set_title("Category-wise Monthly Spending (Stacked)")
    ax.set_xlabel("Month")
    ax.set_ylabel("Spending")
    p = _save_fig(fig, output_dir, "monthly_stacked_bar.png")

    top_month = pivot.sum(axis=1).idxmax()
    insight = f"Highest total spending month: {top_month}."
    return {"chart_path": p, "insight": insight}


def monthly_line_trend(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = df[df["type"] == "debit"].groupby("month")["abs_amount"].sum()
    if expense.empty:
        return _blank_chart(output_dir, "monthly_line_trend.png", "No debit data for monthly trend")

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(expense.index, expense.values, marker="o")
    ax.set_title("Month-over-Month Spending Trend")
    ax.set_xlabel("Month")
    ax.set_ylabel("Spending")
    p = _save_fig(fig, output_dir, "monthly_line_trend.png")

    insight = f"Spending peaks in {expense.idxmax()} and is lowest in {expense.idxmin()}."
    return {"chart_path": p, "insight": insight}


def month_category_heatmap(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = df[df["type"] == "debit"]
    if expense.empty:
        return _blank_chart(output_dir, "month_category_heatmap.png", "No debit data for heatmap")

    pivot = expense.pivot_table(index="month", columns="category", values="abs_amount", aggfunc="sum", fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.heatmap(pivot, cmap="Blues", ax=ax)
    ax.set_title("Month vs Category Spending Intensity")
    p = _save_fig(fig, output_dir, "month_category_heatmap.png")

    max_idx = np.unravel_index(np.argmax(pivot.values), pivot.values.shape)
    insight = f"Most intense cell: month {pivot.index[max_idx[0]]}, category {pivot.columns[max_idx[1]]}."
    return {"chart_path": p, "insight": insight}


def box_plot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.boxplot(x=df["abs_amount"], ax=ax, color="#60a5fa")
    ax.set_title("Transaction Amount Spread (Box Plot)")
    p = _save_fig(fig, output_dir, "box_plot.png")
    q1, q3 = np.percentile(df["abs_amount"], [25, 75])
    iqr = q3 - q1
    outliers = ((df["abs_amount"] < q1 - 1.5 * iqr) | (df["abs_amount"] > q3 + 1.5 * iqr)).sum()
    return {"chart_path": p, "insight": f"Detected {int(outliers)} potential outlier transactions."}


def violin_plot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.violinplot(x=df["type"], y=df["abs_amount"], ax=ax, palette="Set2")
    ax.set_title("Amount Density by Transaction Type")
    p = _save_fig(fig, output_dir, "violin_plot.png")
    return {"chart_path": p, "insight": "Debit transactions typically show a wider spread than credit transactions."}


def strip_plot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    fig, ax = plt.subplots(figsize=(9, 4))
    sample = df.sample(min(800, len(df)), random_state=42)
    sns.stripplot(data=sample, x="category", y="abs_amount", jitter=0.25, size=3, ax=ax)
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("Individual Transaction Spread (Strip)")
    p = _save_fig(fig, output_dir, "strip_plot.png")
    return {"chart_path": p, "insight": "Individual points reveal category-level spread and clustering."}


def swarm_plot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    fig, ax = plt.subplots(figsize=(9, 4))
    sample = df.sample(min(400, len(df)), random_state=7)
    sns.swarmplot(data=sample, x="category", y="abs_amount", size=3, ax=ax)
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("Non-overlapping Transaction Points (Swarm)")
    p = _save_fig(fig, output_dir, "swarm_plot.png")
    return {"chart_path": p, "insight": "Swarm view highlights dense vs sparse categories without overlap."}


def histogram_plot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.histplot(df["abs_amount"], bins=30, kde=False, ax=ax, color="#34d399")
    ax.set_title("Transaction Amount Frequency")
    p = _save_fig(fig, output_dir, "histogram_plot.png")
    return {"chart_path": p, "insight": "Most transactions are concentrated in lower amount ranges."}


def kde_plot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.kdeplot(df["abs_amount"], fill=True, ax=ax, color="#a78bfa")
    ax.set_title("Smooth Density Curve (KDE)")
    p = _save_fig(fig, output_dir, "kde_plot.png")
    return {"chart_path": p, "insight": "KDE shows spending concentrated around common transaction bands."}


def _wide_monthly(df: pd.DataFrame) -> pd.DataFrame:
    expense = df[df["type"] == "debit"]
    return expense.pivot_table(index="month", columns="category", values="abs_amount", aggfunc="sum", fill_value=0)


def joint_plot_food_travel(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    wide = _wide_monthly(df)
    if "Food" not in wide.columns or "Travel" not in wide.columns or len(wide) < 2:
        return _blank_chart(output_dir, "joint_food_travel.png", "Need at least 2 months with Food and Travel data")

    jp = sns.jointplot(x=wide["Food"], y=wide["Travel"], kind="scatter", height=6)
    jp.fig.suptitle("Food vs Travel Monthly Spending", y=1.02)
    p = _save_fig(jp.fig, output_dir, "joint_food_travel.png")
    corr = np.corrcoef(wide["Food"], wide["Travel"])[0, 1]
    return {"chart_path": p, "insight": f"Food vs Travel monthly correlation: {corr:.2f}."}


def pair_plot_categories(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    wide = _wide_monthly(df)
    if wide.shape[1] < 3 or len(wide) < 2:
        return _blank_chart(output_dir, "pair_plot_categories.png", "Need at least 3 categories across 2 months")

    top_cols = wide.sum().sort_values(ascending=False).head(min(5, wide.shape[1])).index
    pp = sns.pairplot(wide[top_cols])
    p = _save_fig(pp.fig, output_dir, "pair_plot_categories.png")
    return {"chart_path": p, "insight": f"Pair relationships shown for top categories: {', '.join(top_cols)}."}


def correlation_heatmap(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    wide = _wide_monthly(df)
    if wide.shape[1] < 2:
        return _blank_chart(output_dir, "correlation_heatmap.png", "Need at least 2 categories for correlation")

    corr = wide.corr()
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(corr, annot=True, cmap="coolwarm", center=0, ax=ax)
    ax.set_title("Category Correlation Heatmap")
    p = _save_fig(fig, output_dir, "correlation_heatmap.png")
    return {"chart_path": p, "insight": "Positive cells indicate categories that rise together across months."}


def pie_chart_category(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = df[df["type"] == "debit"].groupby("category")["abs_amount"].sum()
    if expense.empty:
        return _blank_chart(output_dir, "pie_category.png", "No debit data for category contribution")

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.pie(expense.values, labels=expense.index, autopct="%1.1f%%", startangle=90)
    ax.set_title("Category Contribution (Pie)")
    p = _save_fig(fig, output_dir, "pie_category.png")
    return {"chart_path": p, "insight": f"Largest contribution comes from {expense.idxmax()}."}


def bar_top_categories(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = df[df["type"] == "debit"].groupby("category")["abs_amount"].sum().sort_values(ascending=False).head(8)
    if expense.empty:
        return _blank_chart(output_dir, "bar_top_categories.png", "No debit data for top categories")

    fig, ax = plt.subplots(figsize=(9, 4))
    sns.barplot(x=expense.index, y=expense.values, ax=ax, palette="Blues_d")
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("Top Spending Categories")
    p = _save_fig(fig, output_dir, "bar_top_categories.png")
    return {"chart_path": p, "insight": f"Top category is {expense.index[0]} with highest total spend."}


def count_plot_category(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    fig, ax = plt.subplots(figsize=(9, 4))
    sns.countplot(data=df, x="category", order=df["category"].value_counts().index, ax=ax)
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("Number of Transactions by Category")
    p = _save_fig(fig, output_dir, "count_plot_category.png")
    top_count_cat = df["category"].value_counts().idxmax()
    return {"chart_path": p, "insight": f"Most frequent transaction category: {top_count_cat}."}


def weekly_monthly_comparison(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    weekly = df[df["type"] == "debit"].groupby("week")["abs_amount"].sum()
    monthly = df[df["type"] == "debit"].groupby("month")["abs_amount"].sum()
    if weekly.empty or monthly.empty:
        return _blank_chart(output_dir, "weekly_monthly_comparison.png", "Not enough debit data for weekly/monthly comparison")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))
    ax1.plot(weekly.index, weekly.values, marker="o")
    ax1.set_title("Weekly Spending Trend")
    ax1.tick_params(axis="x", rotation=45)
    ax2.plot(monthly.index, monthly.values, marker="o", color="orange")
    ax2.set_title("Monthly Spending Trend")
    ax2.tick_params(axis="x", rotation=45)
    p = _save_fig(fig, output_dir, "weekly_monthly_comparison.png")
    return {"chart_path": p, "insight": "Weekly line captures short-term spikes; monthly line shows broader trend."}


def weekday_weekend_bar(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense = df[df["type"] == "debit"].copy()
    if expense.empty:
        return _blank_chart(output_dir, "weekday_weekend_bar.png", "No debit data for weekday/weekend comparison")
    g = expense.groupby("is_weekend")["abs_amount"].mean()
    labels = ["Weekday", "Weekend"]
    vals = [g.get(False, 0), g.get(True, 0)]
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.barplot(x=labels, y=vals, ax=ax, palette=["#60a5fa", "#f59e0b"])
    ax.set_title("Average Spending: Weekday vs Weekend")
    p = _save_fig(fig, output_dir, "weekday_weekend_bar.png")
    insight = "Weekend average spending is higher." if vals[1] > vals[0] else "Weekday average spending is higher."
    return {"chart_path": p, "insight": insight}


def rolling_average_7day(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    daily = df[df["type"] == "debit"].groupby(df["date"].dt.date)["abs_amount"].sum().sort_index()
    if daily.empty:
        return _blank_chart(output_dir, "rolling_average_7day.png", "No debit data for rolling average")
    roll = daily.rolling(window=7, min_periods=1).mean()
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(daily.index, daily.values, alpha=0.35, label="Daily")
    ax.plot(roll.index, roll.values, label="7-day rolling avg", color="red")
    ax.legend()
    ax.set_title("7-day Rolling Spending Trend")
    ax.tick_params(axis="x", rotation=45)
    p = _save_fig(fig, output_dir, "rolling_average_7day.png")
    return {"chart_path": p, "insight": "Rolling average smooths daily noise and highlights true trend direction."}


def cumulative_spending_curve(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    daily = df[df["type"] == "debit"].groupby(df["date"].dt.date)["abs_amount"].sum().sort_index()
    if daily.empty:
        return _blank_chart(output_dir, "cumulative_spending_curve.png", "No debit data for cumulative curve")
    cum = daily.cumsum()
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(cum.index, cum.values, color="#6366f1")
    ax.set_title("Cumulative Spending Curve")
    ax.tick_params(axis="x", rotation=45)
    p = _save_fig(fig, output_dir, "cumulative_spending_curve.png")
    return {"chart_path": p, "insight": f"Total cumulative spending reaches {cum.iloc[-1]:.2f} by period end."}


def income_vs_expense_line(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    income = df[df["type"] == "credit"].groupby("month")["abs_amount"].sum()
    expense = df[df["type"] == "debit"].groupby("month")["abs_amount"].sum()
    if income.empty and expense.empty:
        return _blank_chart(output_dir, "income_vs_expense_line.png", "No data for income vs expense comparison")
    all_months = sorted(set(income.index).union(set(expense.index)))
    income_vals = [income.get(m, 0) for m in all_months]
    expense_vals = [expense.get(m, 0) for m in all_months]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(all_months, income_vals, marker="o", label="Income")
    ax.plot(all_months, expense_vals, marker="o", label="Expense")
    ax.legend()
    ax.set_title("Income vs Expense by Month")
    p = _save_fig(fig, output_dir, "income_vs_expense_line.png")
    msg = "Income stays above expense in most months." if np.mean(income_vals) >= np.mean(expense_vals) else "Expense dominates over income in most months."
    return {"chart_path": p, "insight": msg}


def dashboard_subplot(df: pd.DataFrame, output_dir: str = "data/charts") -> Dict[str, str]:
    expense_by_cat = df[df["type"] == "debit"].groupby("category")["abs_amount"].sum().sort_values(ascending=False).head(6)
    monthly = df[df["type"] == "debit"].groupby("month")["abs_amount"].sum()
    daily = df[df["type"] == "debit"].groupby(df["date"].dt.date)["abs_amount"].sum().sort_index()
    weekday = df[df["type"] == "debit"].groupby("day_name")["abs_amount"].sum()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = weekday.reindex(order).fillna(0)

    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    axes = axes.ravel()
    sns.barplot(x=expense_by_cat.index, y=expense_by_cat.values, ax=axes[0], palette="Blues_d")
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].set_title("Top Categories")

    axes[1].plot(monthly.index, monthly.values, marker="o")
    axes[1].set_title("Monthly Trend")

    sns.histplot(df["abs_amount"], bins=25, ax=axes[2], color="#34d399")
    axes[2].set_title("Amount Histogram")

    roll = daily.rolling(window=7, min_periods=1).mean()
    axes[3].plot(roll.index, roll.values, color="red")
    axes[3].tick_params(axis="x", rotation=45)
    axes[3].set_title("7-day Rolling Avg")

    sns.barplot(x=weekday.index, y=weekday.values, ax=axes[4], palette="viridis")
    axes[4].tick_params(axis="x", rotation=45)
    axes[4].set_title("Weekday Spending")

    income = df[df["type"] == "credit"].groupby("month")["abs_amount"].sum()
    all_months = sorted(set(monthly.index).union(set(income.index)))
    axes[5].plot(all_months, [income.get(m, 0) for m in all_months], marker="o", label="Income")
    axes[5].plot(all_months, [monthly.get(m, 0) for m in all_months], marker="o", label="Expense")
    axes[5].legend()
    axes[5].set_title("Income vs Expense")

    p = _save_fig(fig, output_dir, "dashboard_subplot.png")
    insight = "Dashboard combines key views: category concentration, trend, distribution, weekly pattern, and cashflow."
    return {"chart_path": p, "insight": insight}


def generate_all_visuals(csv_path: str, output_dir: str = "data/charts") -> Dict[str, Dict[str, str]]:
    """
    Generates requested visualizations and returns:
    {
      "<chart_key>": {"chart_path": "...", "insight": "..."},
      ...
    }
    """
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

