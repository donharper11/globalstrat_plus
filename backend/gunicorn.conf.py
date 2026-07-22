# Gunicorn configuration for GlobalStrat+ backend
# Usage: gunicorn -c gunicorn.conf.py globalstrat.wsgi:application

bind = '0.0.0.0:8002'
workers = 3
worker_class = 'sync'
timeout = 120
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Process naming
proc_name = 'globalstrat'

# Graceful restart
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 50
