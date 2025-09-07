from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

# Redis URL 설정
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Celery 앱 생성
celery_app = Celery(
    "math_problem_generator",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"]
)

# Celery 설정
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=False,
    task_track_started=True,
    task_always_eager=False,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    task_routes={
        "app.tasks.generate_math_problems_task": {"queue": "math_generation"},
        "app.tasks.grade_problems_task": {"queue": "grading"},
        "app.tasks.grade_problems_mixed_task": {"queue": "grading"},
    },
)

# 태스크 발견을 위한 autodiscover
celery_app.autodiscover_tasks(["app"])

if __name__ == "__main__":
    celery_app.start()