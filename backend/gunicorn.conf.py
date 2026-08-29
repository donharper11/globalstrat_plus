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

# CRV2-07. Without preloading, each of the 17 workers imports Django and warms
# its own caches on the first request it happens to receive. At field load the
# eight slowest requests of the whole run all landed in a single second, 18.3
# to 18.7 seconds in, at up to 18283 ms, while p99 for the run was 1720 ms:
# workers reaching their first request late, with traffic queued behind them.
# Preloading imports the application once in the arbiter before forking, so no
# request pays that cost. This matters most at the moment a class starts and
# every student signs in at once.
preload_app = True

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
# %(D)s is the request duration in microseconds, measured by gunicorn itself.
# Without it the access log cannot say whether a slow request was slow in the
# server or slow in the client observing it, and CRV2-07 needed exactly that
# distinction to explain a latency tail.
access_log_format = '%(h)s %(t)s "%(r)s" %(s)s %(b)s %(D)s'

# Process naming
proc_name = 'globalstrat'

# Graceful restart
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 50
