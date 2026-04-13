import os

import pandas as pd

from app.config import CHARTS_DIR
from app.db import get_connection
from app.services import analytics
from core import visualizer


def ensure_charts_dir():
    os.makedirs(CHARTS_DIR, exist_ok=True)


def _safe_name(batch_id: int) -> str:
    return str(int(batch_id))


def chart_urls_for_batch(batch_id: int) -> dict:
    """Return URLs for PNGs if they exist. Fast — no matplotlib (for /api/summary hot path)."""
    base = f"batch_{_safe_name(batch_id)}"
    cat_name = f"{base}_category_spending.png"
    month_name = f"{base}_monthly_trend.png"
    cat_path = os.path.join(CHARTS_DIR, cat_name)
    month_path = os.path.join(CHARTS_DIR, month_name)
    out = {}
    if os.path.isfile(cat_path):
        out["category_spending"] = f"/static/charts/{cat_name}"
    if os.path.isfile(month_path):
        out["monthly_trend"] = f"/static/charts/{month_name}"
    return out


def chart_gallery_for_batch(batch_id: int) -> list[dict]:
    base = f"batch_{_safe_name(batch_id)}_"
    if not os.path.isdir(CHARTS_DIR):
        return []
    files = sorted([n for n in os.listdir(CHARTS_DIR) if n.startswith(base) and n.endswith(".png")])
    gallery = []
    for name in files:
        label = name.removeprefix(base).removesuffix(".png").replace("_", " ").title()
        gallery.append({"key": name, "title": label, "url": f"/static/charts/{name}"})
    return gallery


def _batch_df(batch_id: int) -> pd.DataFrame:
    sql = """
        SELECT t.date,
               t.description_raw AS description,
               t.amount,
               t.type,
               c.name AS category
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        WHERE t.batch_id = ?
        ORDER BY t.date ASC, t.id ASC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (int(batch_id),)).fetchall()
    if not rows:
        return pd.DataFrame(columns=["date", "description", "amount", "type", "category"])
    df = pd.DataFrame([dict(r) for r in rows])
    df["description"] = df["description"].fillna("UNKNOWN TRANSACTION")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["type"] = df["type"].astype(str).str.strip().str.lower()
    inferred = df["amount"].apply(lambda x: "debit" if float(x) < 0 else "credit")
    df["type"] = df["type"].where(df["type"].isin(["credit", "debit"]), inferred)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").fillna(pd.Timestamp("1970-01-01"))
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["week"] = df["date"].dt.to_period("W").astype(str)
    df["day_name"] = df["date"].dt.day_name()
    df["is_weekend"] = df["date"].dt.dayofweek >= 5
    df["abs_amount"] = df["amount"].abs()
    df["category"] = df["category"].fillna("Other")
    return df


def generate_advanced_charts_for_batch(batch_id: int) -> dict:
    """Generate extended visualization charts per batch and return URLs + insights."""
    ensure_charts_dir()
    df = _batch_df(batch_id)
    if df.empty:
        return {}

    funcs = {
        "monthly_stacked_bar": visualizer.monthly_stacked_bar,
        "monthly_line_trend": visualizer.monthly_line_trend,
        "month_category_heatmap": visualizer.month_category_heatmap,
        "box_plot": visualizer.box_plot,
        "violin_plot": visualizer.violin_plot,
        "strip_plot": visualizer.strip_plot,
        "swarm_plot": visualizer.swarm_plot,
        "histogram_plot": visualizer.histogram_plot,
        "kde_plot": visualizer.kde_plot,
        "joint_plot_food_travel": visualizer.joint_plot_food_travel,
        "pair_plot_categories": visualizer.pair_plot_categories,
        "correlation_heatmap": visualizer.correlation_heatmap,
        "pie_chart_category": visualizer.pie_chart_category,
        "bar_top_categories": visualizer.bar_top_categories,
        "count_plot_category": visualizer.count_plot_category,
        "weekly_monthly_comparison": visualizer.weekly_monthly_comparison,
        "weekday_weekend_bar": visualizer.weekday_weekend_bar,
        "rolling_average_7day": visualizer.rolling_average_7day,
        "cumulative_spending_curve": visualizer.cumulative_spending_curve,
        "income_vs_expense_line": visualizer.income_vs_expense_line,
        "dashboard_subplot": visualizer.dashboard_subplot,
    }

    out = {}
    bid = int(batch_id)
    for key, fn in funcs.items():
        try:
            result = fn(df.copy(), output_dir=CHARTS_DIR)
            src = result["chart_path"]
            dst_name = f"batch_{_safe_name(bid)}_{key}.png"
            dst = os.path.join(CHARTS_DIR, dst_name)
            if os.path.isfile(src) and src != dst:
                os.replace(src, dst)
            out[key] = {"url": f"/static/charts/{dst_name}", "insight": result.get("insight", "")}
        except Exception:
            # Keep upload successful even if one optional chart fails.
            continue
    return out


def generate_charts_for_batch(batch_id: int) -> dict:
    """Save PNGs to static/charts and return public URLs. Heavy (matplotlib) — use on upload/regenerate only."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ensure_charts_dir()
    bid = int(batch_id)
    cat = analytics.category_summary(batch_id=bid, txn_type="debit")
    monthly = analytics.monthly_trend(batch_id=bid)

    base = f"batch_{_safe_name(bid)}"
    cat_path = os.path.join(CHARTS_DIR, f"{base}_category_spending.png")
    month_path = os.path.join(CHARTS_DIR, f"{base}_monthly_trend.png")

    if cat:
        labels = [c["category"] for c in cat]
        values = [c["amount"] for c in cat]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.barh(labels[::-1], values[::-1], color="#2563eb")
        ax.set_xlabel("Amount (debit total)")
        ax.set_title("Spending by category")
        fig.tight_layout()
        fig.savefig(cat_path, dpi=120)
        plt.close(fig)

    if monthly:
        labels = [m["month"] for m in monthly]
        values = [m["amount"] for m in monthly]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(labels, values, marker="o", color="#059669")
        ax.set_ylabel("Total debits")
        ax.set_title("Monthly spending trend")
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()
        fig.savefig(month_path, dpi=120)
        plt.close(fig)

    base_urls = {
        "category_spending": f"/static/charts/{base}_category_spending.png",
        "monthly_trend": f"/static/charts/{base}_monthly_trend.png",
    }
    advanced = generate_advanced_charts_for_batch(bid)
    if advanced:
        base_urls["advanced"] = advanced
    return base_urls
