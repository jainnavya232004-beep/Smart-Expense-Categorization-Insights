# core/visualizer.py
# Makes PNG charts from a transaction DataFrame. Each chart returns:
#   {"chart_path": full path to PNG, "insight": short text summary}

import os

import matplotlib

# No GUI window — save files only (good for servers)
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sns.set()

# ---------------------------------------------------------------------------
# Small helper functions (used by many charts)
# ---------------------------------------------------------------------------


def make_folder_if_needed(folder_path):
    """Create folder if it does not exist."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)


def save_figure_and_close(output_dir, file_name):
    """Save the current matplotlib figure to a PNG and close it."""
    make_folder_if_needed(output_dir)
    full_path = os.path.join(output_dir, file_name)
    plt.tight_layout()
    plt.savefig(full_path, dpi=120)
    plt.close()
    return full_path


def blank_chart(output_dir, file_name, message):
    """Draw a simple 'no data' image."""
    plt.figure(figsize=(8, 4))
    plt.text(0.5, 0.5, message, ha="center", va="center")
    plt.axis("off")
    path = save_figure_and_close(output_dir, file_name)
    return {"chart_path": path, "insight": message}


def get_only_debit_rows(df):
    """Debit rows are expenses (money out)."""
    mask = df["type"] == "debit"
    return df[mask].copy()


def monthly_amount_table(df):
    """
    Rows = month, columns = category, values = total debit amount.
    Used for correlation chart.
    """
    debits = get_only_debit_rows(df)
    table = debits.pivot_table(
        index="month",
        columns="category",
        values="abs_amount",
        aggfunc="sum",
        fill_value=0,
    )
    return table


# ---------------------------------------------------------------------------
# Chart 1–12: internal functions (df, output_dir) -> dict
# ---------------------------------------------------------------------------


def _chart_monthly_stacked_bar(df, output_dir):
    debits = get_only_debit_rows(df)
    if len(debits) == 0:
        return blank_chart(output_dir, "monthly_stacked_bar.png", "No debit data")

    grouped = debits.groupby(["month", "category"])["abs_amount"].sum()
    wide = grouped.unstack(fill_value=0)
    wide.plot(kind="bar", stacked=True, figsize=(8, 4))
    plt.title("Monthly spending by category (stacked)")
    path = save_figure_and_close(output_dir, "monthly_stacked_bar.png")

    total_per_month = wide.sum(axis=1)
    best_month = total_per_month.idxmax()
    insight = "Highest total spending in month: " + str(best_month) + "."
    return {"chart_path": path, "insight": insight}


def _chart_monthly_line_trend(df, output_dir):
    debits = get_only_debit_rows(df)
    if len(debits) == 0:
        return blank_chart(output_dir, "monthly_line_trend.png", "No debit data")

    per_month = debits.groupby("month")["abs_amount"].sum()
    plt.figure(figsize=(9, 4))
    plt.plot(per_month.index, per_month.values, marker="o")
    plt.title("Total debits per month")
    path = save_figure_and_close(output_dir, "monthly_line_trend.png")

    insight = "Peak month: " + str(per_month.idxmax()) + ", lowest: " + str(per_month.idxmin()) + "."
    return {"chart_path": path, "insight": insight}


def _chart_month_category_heatmap(df, output_dir):
    debits = get_only_debit_rows(df)
    if len(debits) == 0:
        return blank_chart(output_dir, "month_category_heatmap.png", "No debit data")

    table = debits.pivot_table(
        index="month",
        columns="category",
        values="abs_amount",
        aggfunc="sum",
        fill_value=0,
    )
    plt.figure(figsize=(10, 5))
    sns.heatmap(table, cmap="Blues")
    plt.title("Month vs category (darker = more spend)")
    path = save_figure_and_close(output_dir, "month_category_heatmap.png")

    # Find which month+category cell has the largest value (simple, no fancy numpy)
    flat = table.stack()
    best_index = flat.idxmax()
    best_month = best_index[0]
    best_cat = best_index[1]
    insight = "Strongest area: " + str(best_month) + " / " + str(best_cat) + "."
    return {"chart_path": path, "insight": insight}


def _chart_pie_category(df, output_dir):
    debits = get_only_debit_rows(df)
    if len(debits) == 0:
        return blank_chart(output_dir, "pie_chart_category.png", "No debit data")

    totals = debits.groupby("category")["abs_amount"].sum()
    plt.figure(figsize=(7, 7))
    plt.pie(totals.values, labels=totals.index, autopct="%1.1f%%", startangle=90)
    plt.title("Share of debits by category")
    path = save_figure_and_close(output_dir, "pie_chart_category.png")

    top = totals.idxmax()
    insight = "Largest share of spending: " + str(top) + "."
    return {"chart_path": path, "insight": insight}


def _chart_bar_top_categories(df, output_dir):
    debits = get_only_debit_rows(df)
    if len(debits) == 0:
        return blank_chart(output_dir, "bar_top_categories.png", "No debit data")

    totals = debits.groupby("category")["abs_amount"].sum()
    totals = totals.sort_values(ascending=False).head(8)
    plt.figure(figsize=(9, 4))
    sns.barplot(x=totals.index, y=totals.values)
    plt.xticks(rotation=45)
    plt.title("Top categories by amount")
    path = save_figure_and_close(output_dir, "bar_top_categories.png")

    first = totals.index[0]
    insight = "Top category by total amount: " + str(first) + "."
    return {"chart_path": path, "insight": insight}


def _chart_correlation_heatmap(df, output_dir):
    table = monthly_amount_table(df)
    if table.shape[1] < 2:
        return blank_chart(output_dir, "correlation_heatmap.png", "Need at least 2 categories")

    corr = table.corr()
    plt.figure(figsize=(8, 6))
    sns.heatmap(corr, annot=True, cmap="coolwarm", center=0)
    plt.title("How categories move together (by month)")
    path = save_figure_and_close(output_dir, "correlation_heatmap.png")

    insight = "Positive numbers mean two categories tend to rise or fall together across months."
    return {"chart_path": path, "insight": insight}


def _chart_weekly_monthly_comparison(df, output_dir):
    debits = get_only_debit_rows(df)
    if len(debits) == 0:
        return blank_chart(output_dir, "weekly_monthly_comparison.png", "No debit data")

    weekly = debits.groupby("week")["abs_amount"].sum()
    monthly = debits.groupby("month")["abs_amount"].sum()
    plt.figure(figsize=(8, 4))
    plt.plot(weekly.index, weekly.values, marker="o", label="Weekly")
    plt.plot(monthly.index, monthly.values, marker="o", label="Monthly")
    plt.legend()
    plt.xticks(rotation=45)
    plt.title("Weekly vs monthly totals")
    path = save_figure_and_close(output_dir, "weekly_monthly_comparison.png")

    insight = "Weekly line shows short moves; monthly line shows the longer trend."
    return {"chart_path": path, "insight": insight}


def _chart_weekday_weekend_bar(df, output_dir):
    debits = get_only_debit_rows(df)
    if len(debits) == 0:
        return blank_chart(output_dir, "weekday_weekend_bar.png", "No debit data")

    grouped = debits.groupby("is_weekend")["abs_amount"].mean()
    weekday_avg = float(grouped.get(False, 0))
    weekend_avg = float(grouped.get(True, 0))
    plt.figure(figsize=(6, 4))
    sns.barplot(x=["Weekday", "Weekend"], y=[weekday_avg, weekend_avg])
    plt.title("Average debit amount (weekday vs weekend)")
    path = save_figure_and_close(output_dir, "weekday_weekend_bar.png")

    if weekend_avg > weekday_avg:
        insight = "Average debit is higher on weekends."
    else:
        insight = "Average debit is higher on weekdays."
    return {"chart_path": path, "insight": insight}


def _chart_rolling_average_7day(df, output_dir):
    debits = get_only_debit_rows(df)
    if len(debits) == 0:
        return blank_chart(output_dir, "rolling_average_7day.png", "No debit data")

    by_day = debits.groupby(debits["date"].dt.date)["abs_amount"].sum()
    by_day = by_day.sort_index()
    rolling = by_day.rolling(window=7, min_periods=1).mean()

    plt.figure(figsize=(10, 4))
    plt.plot(by_day.index, by_day.values, alpha=0.35, label="Daily total")
    plt.plot(rolling.index, rolling.values, color="red", label="7-day average")
    plt.legend()
    plt.xticks(rotation=45)
    plt.title("Daily spending vs 7-day rolling average")
    path = save_figure_and_close(output_dir, "rolling_average_7day.png")

    insight = "The red line smooths daily ups and downs so you see the real trend."
    return {"chart_path": path, "insight": insight}


def _chart_cumulative_spending_curve(df, output_dir):
    debits = get_only_debit_rows(df)
    if len(debits) == 0:
        return blank_chart(output_dir, "cumulative_spending_curve.png", "No debit data")

    by_day = debits.groupby(debits["date"].dt.date)["abs_amount"].sum()
    by_day = by_day.sort_index()
    cumulative = by_day.cumsum()

    plt.figure(figsize=(10, 4))
    plt.plot(cumulative.index, cumulative.values)
    plt.xticks(rotation=45)
    plt.title("Cumulative debit spending over time")
    path = save_figure_and_close(output_dir, "cumulative_spending_curve.png")

    total = cumulative.iloc[-1]
    insight = "Total money out (cumulative) by end of period: " + str(round(total, 2)) + "."
    return {"chart_path": path, "insight": insight}


def _chart_income_vs_expense_line(df, output_dir):
    credits = df[df["type"] == "credit"]
    debits = df[df["type"] == "debit"]
    income_by_month = credits.groupby("month")["abs_amount"].sum()
    expense_by_month = debits.groupby("month")["abs_amount"].sum()

    if len(income_by_month) == 0 and len(expense_by_month) == 0:
        return blank_chart(output_dir, "income_vs_expense_line.png", "No data")

    all_months = set(income_by_month.index) | set(expense_by_month.index)
    all_months = sorted(all_months)

    income_list = []
    expense_list = []
    for m in all_months:
        income_list.append(float(income_by_month.get(m, 0)))
        expense_list.append(float(expense_by_month.get(m, 0)))

    plt.figure(figsize=(9, 4))
    plt.plot(all_months, income_list, marker="o", label="Income")
    plt.plot(all_months, expense_list, marker="o", label="Expense")
    plt.legend()
    plt.title("Income vs expense by month")
    path = save_figure_and_close(output_dir, "income_vs_expense_line.png")

    avg_in = float(np.mean(income_list))
    avg_out = float(np.mean(expense_list))
    if avg_in >= avg_out:
        insight = "On average, income is higher than expense across these months."
    else:
        insight = "On average, expense is higher than income across these months."
    return {"chart_path": path, "insight": insight}


def _chart_dashboard_subplot(df, output_dir):
    debits = get_only_debit_rows(df)
    if len(debits) == 0:
        return blank_chart(output_dir, "dashboard_subplot.png", "No debit data")

    top_cats = debits.groupby("category")["abs_amount"].sum()
    top_cats = top_cats.sort_values(ascending=False).head(6)

    monthly = debits.groupby("month")["abs_amount"].sum()
    daily = debits.groupby(debits["date"].dt.date)["abs_amount"].sum()
    daily = daily.sort_index()

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_weekday = debits.groupby("day_name")["abs_amount"].sum()
    by_weekday = by_weekday.reindex(day_order)
    by_weekday = by_weekday.fillna(0)

    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    ax_list = [axes[0][0], axes[0][1], axes[0][2], axes[1][0], axes[1][1], axes[1][2]]

    sns.barplot(x=top_cats.index, y=top_cats.values, ax=ax_list[0])
    ax_list[0].tick_params(axis="x", rotation=45)
    ax_list[0].set_title("Top categories")

    ax_list[1].plot(monthly.index, monthly.values, marker="o")
    ax_list[1].set_title("Monthly debits")

    sns.histplot(df["abs_amount"], bins=25, ax=ax_list[2])
    ax_list[2].set_title("All amounts (distribution)")

    roll = daily.rolling(7, min_periods=1).mean()
    ax_list[3].plot(roll.index, roll.values, color="red")
    ax_list[3].tick_params(axis="x", rotation=45)
    ax_list[3].set_title("7-day rolling")

    sns.barplot(x=by_weekday.index, y=by_weekday.values, ax=ax_list[4])
    ax_list[4].tick_params(axis="x", rotation=45)
    ax_list[4].set_title("Total by weekday")

    inc = df[df["type"] == "credit"].groupby("month")["abs_amount"].sum()
    months_both = set(monthly.index) | set(inc.index)
    months_both = sorted(months_both)
    inc_vals = [float(inc.get(m, 0)) for m in months_both]
    exp_vals = [float(monthly.get(m, 0)) for m in months_both]
    ax_list[5].plot(months_both, inc_vals, marker="o", label="Income")
    ax_list[5].plot(months_both, exp_vals, marker="o", label="Expense")
    ax_list[5].legend()
    ax_list[5].set_title("Income vs expense")

    plt.suptitle("Summary dashboard", y=1.02)
    make_folder_if_needed(output_dir)
    path = os.path.join(output_dir, "dashboard_subplot.png")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)

    insight = "Six small charts in one image: overview of spending patterns."
    return {"chart_path": path, "insight": insight}


# Maps name -> internal function (used by run_one_chart and by charts.py)
CHART_FUNCTIONS = {
    "monthly_stacked_bar": _chart_monthly_stacked_bar,
    "monthly_line_trend": _chart_monthly_line_trend,
    "month_category_heatmap": _chart_month_category_heatmap,
    "pie_chart_category": _chart_pie_category,
    "bar_top_categories": _chart_bar_top_categories,
    "correlation_heatmap": _chart_correlation_heatmap,
    "weekly_monthly_comparison": _chart_weekly_monthly_comparison,
    "weekday_weekend_bar": _chart_weekday_weekend_bar,
    "rolling_average_7day": _chart_rolling_average_7day,
    "cumulative_spending_curve": _chart_cumulative_spending_curve,
    "income_vs_expense_line": _chart_income_vs_expense_line,
    "dashboard_subplot": _chart_dashboard_subplot,
}

# Backwards compatibility for code that reads _BUILDERS
_BUILDERS = CHART_FUNCTIONS


def run_one_chart(chart_name, df, output_dir="data/charts"):
    """Run a single chart by its string name."""
    fn = CHART_FUNCTIONS[chart_name]
    return fn(df, output_dir)


# ---------------------------------------------------------------------------
# Public API — same names as before (app/services/charts.py uses these)
# ---------------------------------------------------------------------------


def monthly_stacked_bar(df, output_dir="data/charts"):
    return _chart_monthly_stacked_bar(df, output_dir)


def monthly_line_trend(df, output_dir="data/charts"):
    return _chart_monthly_line_trend(df, output_dir)


def month_category_heatmap(df, output_dir="data/charts"):
    return _chart_month_category_heatmap(df, output_dir)


def pie_chart_category(df, output_dir="data/charts"):
    return _chart_pie_category(df, output_dir)


def bar_top_categories(df, output_dir="data/charts"):
    return _chart_bar_top_categories(df, output_dir)


def correlation_heatmap(df, output_dir="data/charts"):
    return _chart_correlation_heatmap(df, output_dir)


def weekly_monthly_comparison(df, output_dir="data/charts"):
    return _chart_weekly_monthly_comparison(df, output_dir)


def weekday_weekend_bar(df, output_dir="data/charts"):
    return _chart_weekday_weekend_bar(df, output_dir)


def rolling_average_7day(df, output_dir="data/charts"):
    return _chart_rolling_average_7day(df, output_dir)


def cumulative_spending_curve(df, output_dir="data/charts"):
    return _chart_cumulative_spending_curve(df, output_dir)


def income_vs_expense_line(df, output_dir="data/charts"):
    return _chart_income_vs_expense_line(df, output_dir)


def dashboard_subplot(df, output_dir="data/charts"):
    return _chart_dashboard_subplot(df, output_dir)
