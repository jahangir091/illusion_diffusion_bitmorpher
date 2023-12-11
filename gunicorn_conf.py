# gunicorn_conf.py
from multiprocessing import cpu_count
import os

def get_project_name():
    cwd = os.getcwd()
    return cwd.split('/')[-1]


bind = "0.0.0.0:8001"

# Worker Options
# workers = cpu_count() + 1
workers = 2
worker_class = 'uvicorn.workers.UvicornWorker'

# Logging Options
loglevel = 'debug'
accesslog = '/var/log/{0}/access.log'.format(get_project_name())
errorlog = '/var/log/{0}/error.log'.format(get_project_name())
