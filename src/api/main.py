from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.agents.analysis_agent import analyze_ticker, render_report
from src.agents.critic_agent import critique_report
from src.agents.errors import alert_credit_exhausted, clear_credit_alert, is_insufficient_credit_error
from src.config import NTFY_TOPIC
from src.notifications.events import notify_flagged_claims, notify_report_ready
from src.notifications.notifier import NtfyNotifier
from src.portfolio.change_detection import check_and_record_portfolio_changes
from src.portfolio.robinhood import get_portfolio_summary
from src.storage import db

app = FastAPI(title="Stock Research Agents")
templates = Jinja2Templates(directory="src/api/templates")

db.init_db()


def _get_notifier() -> NtfyNotifier | None:
    if not NTFY_TOPIC:
        return None
    return NtfyNotifier(topic=NTFY_TOPIC)


def _run_analysis(ticker: str) -> int:
    """Shared by the page route and the JSON API route: run the full
    pipeline, persist, and notify. Returns the new report's id.

    Raises HTTPException(503) with a clear message if the Anthropic API is
    rejecting calls for insufficient credit specifically -- rather than
    letting that surface as an opaque 500, since "you're out of API
    credit" has an obvious, actionable fix a generic error message hides.
    """
    notifier = _get_notifier()

    try:
        report = analyze_ticker(ticker)
        report = critique_report(report)
    except Exception as e:
        if is_insufficient_credit_error(e):
            alert_credit_exhausted(notifier)
            raise HTTPException(
                status_code=503,
                detail="Anthropic API credit balance is too low. Add credits at "
                "console.anthropic.com, then try again.",
            )
        raise

    clear_credit_alert()
    report_id = db.save_report(report)

    if notifier:
        notify_report_ready(notifier, report, report_id)
        notify_flagged_claims(notifier, report, report_id)

    return report_id


# --- HTML pages (server-rendered, no JS framework) ---


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    reports = db.get_reports()
    watchlist = db.get_watchlist()
    portfolio = get_portfolio_summary()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"reports": reports, "watchlist": watchlist, "portfolio": portfolio},
    )


@app.get("/reports/{report_id}", response_class=HTMLResponse)
def report_detail_page(request: Request, report_id: int):
    report = db.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return templates.TemplateResponse(
        request, "report_detail.html", {"report": report, "rendered": render_report(report)}
    )


@app.post("/analyze/{ticker}")
def analyze_page(ticker: str):
    report_id = _run_analysis(ticker.upper())
    return RedirectResponse(url=f"/reports/{report_id}", status_code=303)


@app.post("/watchlist/add")
def watchlist_add_page(ticker: str = Form(...)):
    db.add_to_watchlist(ticker)
    return RedirectResponse(url="/", status_code=303)


@app.post("/watchlist/{ticker}/remove")
def watchlist_remove_page(ticker: str):
    db.remove_from_watchlist(ticker)
    return RedirectResponse(url="/", status_code=303)


# --- JSON API (for programmatic use, e.g. a future scheduler) ---


@app.get("/api/reports")
def api_list_reports():
    return db.get_reports()


@app.get("/api/reports/{report_id}")
def api_get_report(report_id: int):
    report = db.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.post("/api/reports/{ticker}")
def api_create_report(ticker: str):
    report_id = _run_analysis(ticker.upper())
    return db.get_report(report_id)


@app.get("/api/watchlist")
def api_get_watchlist():
    return db.get_watchlist()


@app.post("/api/watchlist/{ticker}")
def api_add_watchlist(ticker: str):
    db.add_to_watchlist(ticker)
    return {"status": "added", "ticker": ticker.upper()}


@app.delete("/api/watchlist/{ticker}")
def api_remove_watchlist(ticker: str):
    db.remove_from_watchlist(ticker)
    return {"status": "removed", "ticker": ticker.upper()}


@app.get("/api/portfolio")
def api_get_portfolio():
    return get_portfolio_summary()


@app.post("/api/portfolio/check")
def api_check_portfolio():
    newly_overweight = check_and_record_portfolio_changes(_get_notifier())
    return {"newly_overweight": newly_overweight}
