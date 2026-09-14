from __future__ import annotations

import structlog

from app.workers.celery_app import celery_app


logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)
def process_consultation_reminder(
    self,
    consultation_id: str,
) -> dict[str, str]:
    """
    Asynchronous reminder workflow boundary.

    External notification providers can be plugged into this
    task without blocking the API request.
    """

    logger.info(
        "consultation_reminder_processed",
        consultation_id=consultation_id,
        task_id=self.request.id,
    )

    return {
        "status": "processed",
        "consultation_id": consultation_id,
    }


@celery_app.task
def health_check_task() -> str:
    return "ok"
