"""
Optional scheduler for automated daily execution of the Finance Email Agent.

Uses APScheduler to run the pipeline at a configurable time.
Disabled by default — enable via SCHEDULE_ENABLED=true in .env.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def start_scheduler():
    """
    Start the APScheduler cron job if SCHEDULE_ENABLED=true.

    Configuration via .env:
        SCHEDULE_ENABLED=true
        SCHEDULE_HOUR=9        (default: 9 AM)
        SCHEDULE_MINUTE=0      (default: 0)
    """
    enabled = os.getenv("SCHEDULE_ENABLED", "false").lower() == "true"

    if not enabled:
        print("⏸️  Scheduler is disabled. Set SCHEDULE_ENABLED=true in .env to enable.")
        return

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ImportError:
        print("❌ APScheduler not installed. Run: pip install apscheduler>=3.10.0")
        return

    from src.main import main as run_pipeline

    hour = int(os.getenv("SCHEDULE_HOUR", "9"))
    minute = int(os.getenv("SCHEDULE_MINUTE", "0"))

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        trigger="cron",
        hour=hour,
        minute=minute,
        id="finance_email_agent_daily",
        name="Finance Email Agent – Daily Run",
    )

    print(f"🕐 Scheduler started. Pipeline will run daily at {hour:02d}:{minute:02d}.")
    print("   Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n⏹️  Scheduler stopped.")


if __name__ == "__main__":
    start_scheduler()