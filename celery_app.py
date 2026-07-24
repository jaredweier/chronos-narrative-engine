import os
from celery import Celery
from config import REDIS_URL

celery_app = Celery(
    'chronos',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_routes={
        'tasks.transcribe_video_task': {'queue': 'audio'},
        'tasks.process_vision_task': {'queue': 'vision'},
        'tasks.redact_video_task': {'queue': 'vision'},
        '*': {'queue': 'celery'}
    }
)

if __name__ == '__main__':
    celery_app.start()
