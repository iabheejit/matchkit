"""APScheduler manager for scheduled tasks."""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import settings
from scheduler.jobs import jobs

logger = logging.getLogger(__name__)


class SchedulerManager:
    """Manage scheduled tasks with APScheduler."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._is_running = False

    def setup_jobs(self):
        """Set up all scheduled jobs based on configured frequency."""
        freq = settings.email_frequency.lower()
        if freq == "monthly":
            email_trigger = CronTrigger(
                day=settings.monthly_email_day,
                hour=settings.weekly_email_hour,
                minute=0,
            )
            email_label = f"Send Monthly Digest Emails (day {settings.monthly_email_day})"
        else:
            email_day = self._day_name_to_cron(settings.weekly_email_day)
            email_trigger = CronTrigger(
                day_of_week=email_day,
                hour=settings.weekly_email_hour,
                minute=0,
            )
            email_label = f"Send Weekly Digest Emails ({settings.weekly_email_day})"

        self.scheduler.add_job(
            jobs.run_weekly_emails,
            email_trigger,
            id="email_digest",
            name=email_label,
            replace_existing=True,
        )

        refresh_freq = settings.match_refresh_frequency.lower()
        if refresh_freq == "monthly":
            refresh_trigger = CronTrigger(day=1, hour=3, minute=0)
            refresh_label = "Monthly Match Score Refresh (1st of month)"
        else:
            refresh_trigger = CronTrigger(day_of_week="sun", hour=3, minute=0)
            refresh_label = "Weekly Match Score Refresh (Sundays)"

        self.scheduler.add_job(
            jobs.run_match_refresh,
            refresh_trigger,
            id="match_refresh",
            name=refresh_label,
            replace_existing=True,
        )

    def start(self):
        if not self._is_running:
            self.setup_jobs()
            self.scheduler.start()
            self._is_running = True
            logger.info("Scheduler started")
            self._log_scheduled_jobs()

    def stop(self):
        if self._is_running:
            self.scheduler.shutdown()
            self._is_running = False
            logger.info("Scheduler stopped")

    def get_job_status(self) -> dict:
        status = {
            "is_running": self._is_running,
            "jobs": [],
            "last_results": {},
        }

        if self._is_running:
            for job in self.scheduler.get_jobs():
                status["jobs"].append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": (
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                    "trigger": str(job.trigger),
                })

        for job_name, result in jobs.last_results.items():
            status["last_results"][job_name] = {
                "success": result.success,
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat(),
                "duration_seconds": result.duration_seconds,
                "records_processed": result.records_processed,
                "errors": result.errors,
            }

        return status

    async def trigger_job(self, job_name: str) -> dict:
        job_map = {
            "weekly_emails": jobs.run_weekly_emails,
            "email_digest": jobs.run_weekly_emails,
            "match_refresh": jobs.run_match_refresh,
        }

        if job_name not in job_map:
            return {"error": f"Unknown job: {job_name}. Available: {list(job_map.keys())}"}

        result = await job_map[job_name]()

        return {
            "job_name": result.job_name,
            "success": result.success,
            "duration_seconds": result.duration_seconds,
            "records_processed": result.records_processed,
            "errors": result.errors,
            "details": result.details,
        }

    def _day_name_to_cron(self, day_name: str) -> str:
        days = {
            "monday": "mon", "tuesday": "tue", "wednesday": "wed",
            "thursday": "thu", "friday": "fri", "saturday": "sat",
            "sunday": "sun",
        }
        return days.get(day_name.lower(), "mon")

    def _log_scheduled_jobs(self):
        for job in self.scheduler.get_jobs():
            next_run = (
                job.next_run_time.strftime("%Y-%m-%d %H:%M") if job.next_run_time else "N/A"
            )
            logger.info(f"  Job: {job.name} — next run: {next_run}")


# Singleton instance
scheduler_manager = SchedulerManager()
