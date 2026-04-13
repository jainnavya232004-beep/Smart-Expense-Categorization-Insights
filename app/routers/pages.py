import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from app.config import BASE_DIR
from app.services import analytics, charts
from app.services.transactions import latest_batch_id

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    raw = request.query_params.get("batch_id")
    if raw not in (None, ""):
        try:
            bid = int(raw)
        except ValueError:
            bid = latest_batch_id()
    else:
        bid = latest_batch_id()

    summary = analytics.summary(batch_id=bid)
    top = analytics.top_spending_category(batch_id=bid) or {"category": None, "amount": 0}
    cat_sum = analytics.category_summary(batch_id=bid, txn_type="debit")
    monthly = analytics.monthly_trend(batch_id=bid)
    png_urls = charts.chart_urls_for_batch(bid) if bid is not None else {}
    gallery = charts.chart_gallery_for_batch(bid) if bid is not None else []

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "batch_id": bid,
            "summary": summary,
            "top": top,
            "cat_sum": cat_sum,
            "monthly": monthly,
            "png_urls": png_urls,
            "gallery": gallery,
        },
    )


@router.get("/transactions", response_class=HTMLResponse)
def transactions_page(request: Request):
    return templates.TemplateResponse(request, "transactions.html")


@router.get("/charts", response_class=HTMLResponse)
def charts_page(request: Request):
    return templates.TemplateResponse(request, "charts.html")

