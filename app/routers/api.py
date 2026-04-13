import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.db import get_connection
from app.logger import get_logger
from app.services import analytics, charts
from app.services.ingest import process_upload
from app.services.transactions import export_rows, latest_batch_id, list_transactions

router = APIRouter(tags=["api"])
logger = get_logger(__name__)


class RuleCreate(BaseModel):
    keyword: str = Field(..., min_length=1)
    category_id: int


def _batch_id_arg(batch_id: str | None):
    if batch_id is None or batch_id == "":
        return latest_batch_id()
    try:
        return int(batch_id)
    except ValueError:
        return None


def _parse_batch_id_optional(batch_id: str | None) -> int | None:
    if batch_id in (None, ""):
        return None
    try:
        return int(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid batch_id") from e


def _parse_batch_id_or_latest(batch_id: str | None) -> int | None:
    if batch_id in (None, ""):
        return latest_batch_id()
    try:
        return int(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid batch_id") from e


def _iso_date_or_none(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value[:10]).date().isoformat()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date: {value}") from e


def _resolve_period_dates(period: str | None) -> tuple[str | None, str | None]:
    if period is None or period == "":
        return None, None
    p = period.lower()
    today = datetime.now().date()
    if p == "weekly":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start.isoformat(), end.isoformat()
    if p == "monthly":
        start = today.replace(day=1)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1, day=1)
        else:
            next_month = start.replace(month=start.month + 1, day=1)
        end = next_month - timedelta(days=1)
        return start.isoformat(), end.isoformat()
    raise HTTPException(status_code=400, detail="period must be weekly or monthly")


def _pdf_bytes_from_rows(rows: list[dict], batch_id: int, period: str, applied: dict) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40

    def new_page_if_needed(curr_y: float) -> float:
        if curr_y < 60:
            pdf.showPage()
            return height - 40
        return curr_y

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, "Smart Expense Categorization - Export Report")
    y -= 24
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, f"Batch ID: {batch_id}")
    y -= 14
    pdf.drawString(40, y, f"Period: {period}")
    y -= 14
    pdf.drawString(40, y, f"Filters: {applied}")
    y -= 20

    total_income = sum(float(r["amount"]) for r in rows if r["type"] == "credit")
    total_expense = sum(abs(float(r["amount"])) for r in rows if r["type"] == "debit")
    pdf.drawString(40, y, f"Rows: {len(rows)}")
    y -= 14
    pdf.drawString(40, y, f"Total income: {total_income:.2f}")
    y -= 14
    pdf.drawString(40, y, f"Total expense: {total_expense:.2f}")
    y -= 20

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Date")
    pdf.drawString(120, y, "Description")
    pdf.drawString(360, y, "Type")
    pdf.drawString(420, y, "Category")
    pdf.drawRightString(560, y, "Amount")
    y -= 14
    pdf.setFont("Helvetica", 9)

    for row in rows:
        y = new_page_if_needed(y)
        desc = str(row["description"])[:40]
        pdf.drawString(40, y, str(row["date"]))
        pdf.drawString(120, y, desc)
        pdf.drawString(360, y, str(row["type"]))
        pdf.drawString(420, y, str(row["category"])[:18])
        pdf.drawRightString(560, y, f"{float(row['amount']):.2f}")
        y -= 12

    pdf.save()
    return buffer.getvalue()


@router.post("/upload")
async def upload(
    file: UploadFile | None = File(None, description="Single CSV upload"),
    files: list[UploadFile] | None = File(None, description="Multiple CSV uploads"),
):
    upload_list: list[UploadFile] = []
    if files:
        upload_list.extend(files)
    if file is not None:
        upload_list.append(file)
    if not upload_list:
        raise HTTPException(status_code=400, detail="No file selected")
    logger.info("Upload request received with %d file(s)", len(upload_list))

    outputs: list[dict] = []
    total_records = 0
    for up in upload_list:
        if not up.filename:
            raise HTTPException(status_code=400, detail="File name missing")
        raw = await up.read()
        if not raw:
            raise HTTPException(status_code=400, detail=f"Empty file: {up.filename}")
        try:
            result = process_upload(raw, up.filename)
        except ValueError as e:
            logger.warning("Upload validation failed for %s: %s", up.filename, str(e))
            raise HTTPException(status_code=400, detail=f"{up.filename}: {e}") from e
        except Exception as e:
            logger.exception("Upload processing failed for %s", up.filename)
            raise HTTPException(status_code=500, detail=f"{up.filename}: Processing failed: {e}") from e

        bid = result["batch_id"]
        chart_urls = charts.generate_charts_for_batch(bid)
        inserted = int(result["inserted"])
        total_records += inserted
        outputs.append(
            {
                "filename": up.filename,
                "batch_id": bid,
                "total_records": inserted,
                "skipped_errors": result.get("skipped_errors") or [],
                "chart_urls": chart_urls,
                "auto_filled_rows": result.get("auto_filled_rows") or [],
            }
        )
        logger.info("Upload processed: file=%s batch_id=%s rows=%s", up.filename, bid, inserted)

    if len(outputs) == 1:
        one = outputs[0]
        return {
            "message": "File processed successfully",
            "filename": one["filename"],
            "total_records": one["total_records"],
            "batch_id": one["batch_id"],
            "skipped_errors": one["skipped_errors"],
            "chart_urls": one["chart_urls"],
            "auto_filled_rows": one["auto_filled_rows"],
            "uploads": outputs,
        }

    return {
        "message": "Files processed successfully",
        "file_count": len(outputs),
        "total_records": total_records,
        "uploads": outputs,
    }


@router.get("/transactions")
def get_transactions(
    page: str | None = Query(None),
    limit: str | None = Query(None),
    batch_id: str | None = Query(None),
    category: str | None = Query(None),
    txn_type: str | None = Query(None, alias="type"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    bid = _parse_batch_id_optional(batch_id)
    items, total, pg, lim = list_transactions(
        page=page,
        limit=limit,
        batch_id=bid,
        category=category,
        txn_type=txn_type,
        start_date=start_date,
        end_date=end_date,
    )
    effective = bid if bid is not None else latest_batch_id()
    return {
        "items": items,
        "total": total,
        "page": pg,
        "limit": lim,
        "batch_id": effective,
    }


@router.get("/transactions/filter")
def filter_transactions(
    page: str | None = Query(None),
    limit: str | None = Query(None),
    batch_id: str | None = Query(None),
    category: str | None = Query(None),
    txn_type: str | None = Query(None, alias="type"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    return get_transactions(
        page=page,
        limit=limit,
        batch_id=batch_id,
        category=category,
        txn_type=txn_type,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/summary")
def get_summary(
    batch_id: str | None = Query(None),
    regenerate: bool = Query(
        False,
        description="If true, rebuild PNGs with matplotlib (slow). Otherwise return existing file URLs only.",
    ),
):
    bid = _batch_id_arg(batch_id)
    data = analytics.summary(batch_id=bid)
    if bid is None:
        chart_urls: dict = {}
    elif regenerate:
        chart_urls = charts.generate_charts_for_batch(bid)
    else:
        chart_urls = charts.chart_urls_for_batch(bid)
    return {**data, "batch_id": bid, "chart_urls": chart_urls}


@router.get("/category-summary")
def category_summary(
    batch_id: str | None = Query(None),
    txn_type: str | None = Query(None, alias="type"),
):
    bid = _batch_id_arg(batch_id)
    t = txn_type if txn_type in ("credit", "debit") else None
    return analytics.category_summary(batch_id=bid, txn_type=t)


@router.get("/top-category")
def top_category(batch_id: str | None = Query(None)):
    bid = _batch_id_arg(batch_id)
    top = analytics.top_spending_category(batch_id=bid)
    if top is None:
        return {"category": None, "amount": 0}
    return top


@router.get("/monthly-trend")
def monthly_trend(
    batch_id: str | None = Query(None),
    year: str | None = Query(None),
):
    bid = _batch_id_arg(batch_id)
    y = int(year) if year and year.isdigit() else None
    return analytics.monthly_trend(batch_id=bid, year=y)


@router.get("/weekly-trend")
def weekly_trend(
    batch_id: str | None = Query(None),
    year: int = Query(..., ge=1970, le=2100, description="ISO year for selected week"),
    week: int = Query(..., ge=1, le=53, description="ISO week number (1-53)"),
):
    bid = _batch_id_arg(batch_id)
    try:
        week_start = datetime.fromisocalendar(year, week, 1).date()
        week_end = datetime.fromisocalendar(year, week, 7).date()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid ISO week selection: {e}") from e
    points = analytics.weekly_trend(batch_id=bid, week_start=week_start, week_end=week_end)
    return {
        "batch_id": bid,
        "year": year,
        "week": week,
        "start_date": week_start.isoformat(),
        "end_date": week_end.isoformat(),
        "points": points,
    }


@router.get("/categories")
def categories():
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name FROM categories ORDER BY id ASC").fetchall()
    return [{"id": r["id"], "name": r["name"]} for r in rows]


@router.get("/rules")
def rules_list():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.id, r.keyword, r.category_id, c.name AS category
            FROM rules r
            JOIN categories c ON c.id = r.category_id
            ORDER BY r.priority DESC, r.keyword ASC
            """
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/rules", status_code=201)
def rules_create(rule: RuleCreate):
    keyword = rule.keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword is required")
    cid = rule.category_id

    with get_connection() as conn:
        row = conn.execute("SELECT id FROM categories WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Invalid category_id")
        cur = conn.execute(
            "INSERT INTO rules (keyword, category_id, priority) VALUES (?, ?, ?)",
            (keyword.lower(), cid, 10),
        )
        conn.commit()
        rid = cur.lastrowid

    return {"id": rid, "keyword": keyword.lower(), "category_id": cid}


@router.get("/export")
def export_csv(
    batch_id: str | None = Query(None),
    format: str = Query("csv", description="Export format: csv or pdf"),
    period: str | None = Query(None, description="Date shortcut: weekly or monthly"),
    txn_type: str | None = Query(None, alias="type"),
    category: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    bid = _parse_batch_id_or_latest(batch_id)
    if bid is None:
        raise HTTPException(status_code=404, detail="No data to export")

    range_start, range_end = _resolve_period_dates(period)
    parsed_start = _iso_date_or_none(start_date) or range_start
    parsed_end = _iso_date_or_none(end_date) or range_end
    rows = export_rows(
        batch_id=bid,
        txn_type=txn_type,
        category=category,
        start_date=parsed_start,
        end_date=parsed_end,
    )
    fmt = format.lower().strip()
    period_label = period.lower().strip() if period else "custom_all"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")

    if fmt == "pdf":
        payload = _pdf_bytes_from_rows(
            rows=rows,
            batch_id=bid,
            period=period_label,
            applied={
                "type": txn_type,
                "category": category,
                "start_date": parsed_start,
                "end_date": parsed_end,
            },
        )
        name = f"categorized_batch_{bid}_{period_label}_{stamp}.pdf"
        return Response(
            content=payload,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    if fmt != "csv":
        raise HTTPException(status_code=400, detail="format must be csv or pdf")

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "description", "amount", "type", "category"])
    for r in rows:
        w.writerow([r["date"], r["description"], r["amount"], r["type"], r["category"]])

    name = f"categorized_batch_{bid}_{period_label}_{stamp}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/charts/regenerate")
def regenerate_charts(batch_id: str | None = Query(None)):
    bid = batch_id
    if bid in (None, ""):
        bid = latest_batch_id()
    if bid is None:
        raise HTTPException(status_code=400, detail="batch_id required")
    try:
        bid = int(bid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid batch_id") from None
    urls = charts.generate_charts_for_batch(bid)
    return {"batch_id": bid, "chart_urls": urls}

