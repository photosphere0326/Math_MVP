#!/usr/bin/env python3
"""
Celery Worker 실행 스크립트

사용법:
    python celery_worker.py

또는 직접 celery 명령어:
    celery -A app.celery_app worker --loglevel=info --concurrency=2
"""

import os
import sys

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.celery_app import celery_app

if __name__ == '__main__':
    # Celery worker 시작
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=2',
        '--queues=math_generation,grading'
    ])