# Gunicorn configuration for GlobalStrat+ backend
# Usage: gunicorn -c gunicorn.conf.py globalstrat.wsgi:application

bind = '0.0.0.0:8002'

# CRV2-07. Three sync workers could not carry the field profile: 24 teams x 4
# members held p95 at 4099 ms and max at 24321 ms against thresholds of 2000
# and 10000. Nothing was failing -- zero 5xx, zero transport failures, and
# every one of 2427 acknowledged writes reconciled -- the requests were simply
# queued. A sync worker serves one request at a time, so three workers cap
# throughput at three divided by the service time: measured at 139 ms per
# request, that is about 21 requests a second, and the field profile wants
# more.
#
# 17 is gunicorn's own guidance for sync workers, (2 x cores) + 1 on 8 cores.
# Memory is not a constraint here (35 GB) and neither is PostgreSQL: Django
# opens a connection per request with CONN_MAX_AGE unset, so workers bound
# concurrent connections at 17 against a limit of 100.
workers = 17
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
