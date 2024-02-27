# gunicorn_conf.py
from multiprocessing import cpu_count
import os


bind = 'unix:/run/illusion_diffusion/gunicorn.sock'

# Worker Options
# workers = cpu_count() + 1
workers = 1
worker_class = 'uvicorn.workers.UvicornWorker'

# Logging Options
loglevel = 'debug'
accesslog = '/var/log/illusion_diffusion/access.log'
errorlog = '/var/log/illusion_diffusion/error.log'
