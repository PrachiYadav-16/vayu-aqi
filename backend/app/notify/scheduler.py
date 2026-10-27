"""Background jobs: ingestion, alert checks and weekly retraining."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.forecast.service import get_forecast_service
from app.ingest.pipeline import ingest_live
from app.notify.engine import run_checks

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _ingest_job():
    res = ingest_live()
    if res["written"]:
        get_forecast_service().station_forecasts(force=True)
    log.info("ingest: %s", res)


def _alert_job():
    log.info("alerts: %s", run_checks())


def retrain_job():
    """Weekly: retrain on the last year of stored data; promote only if not worse."""
    backend = Path(__file__).resolve().parents[2]
    cmd = [sys.executable, "-m", "training.train_forecaster", "--source", "db", "--days", "365",
           "--promote-if-better", "--report"]
    try:
        subprocess.run(cmd, cwd=backend, check=True, timeout=3 * 3600)
        get_forecast_service().reload_model()
    except Exception as exc:
        log.error("Retraining failed: %s", exc)


def start() -> None:
    global _scheduler
    s = get_settings()
    if _scheduler or not s.run_scheduler:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(_ingest_job, "interval", minutes=s.ingest_interval_minutes, id="ingest",
                       max_instances=1, coalesce=True)
    _scheduler.add_job(_alert_job, "interval", minutes=s.alert_interval_minutes, id="alerts",
                       max_instances=1, coalesce=True)
    _scheduler.add_job(retrain_job, "cron", day_of_week="sun", hour=20, minute=30, id="retrain",
                       max_instances=1)  # Monday 02:00 IST
    _scheduler.start()
    log.info("Scheduler started")


def stop() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
