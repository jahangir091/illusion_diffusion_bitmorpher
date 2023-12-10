# gunicorn_conf.py
from multiprocessing import cpu_count

bind = "0.0.0.0:8000"

# Worker Options
# workers = cpu_count() + 1
workers = 2
worker_class = 'uvicorn.workers.UvicornWorker'

# Logging Options
loglevel = 'debug'
accesslog = '/var/log/rembg/access.log'
errorlog = '/var/log/rembg/error.log'
