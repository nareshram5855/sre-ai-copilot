# Gunicorn config for SRE AI Copilot (production-style local serving)
import multiprocessing

# Worker setup — uvicorn workers for async FastAPI
worker_class = "uvicorn.workers.UvicornWorker"
workers = min(4, multiprocessing.cpu_count())  # cap at 4 for local dev
threads = 1  # uvicorn workers are single-threaded (async handles concurrency)

# Bind
bind = "127.0.0.1:8080"

# Timeouts — generous for LLM inference (llama3.1:8b can take 30s+)
timeout = 300
keepalive = 5
graceful_timeout = 30

# Logging
loglevel = "info"
accesslog = "/tmp/sre-ai-gunicorn-access.log"
errorlog  = "/tmp/sre-ai-gunicorn-error.log"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sµs'

# Reload on code change (disable in true production)
reload = False

# Worker lifecycle — recycle workers to prevent memory bloat from LLM inference
max_requests = 500
max_requests_jitter = 50
