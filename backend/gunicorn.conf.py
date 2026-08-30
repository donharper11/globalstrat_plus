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
# Raised again after the deadline burst. At realistic think time the host is
# not compute-bound -- CPU averaged 27% and reached 63% during the burst -- so
# the workers were blocked on remote-database I/O, not on the CPU, while 288
# saves and 24 locks arrived at once and queued about eighteen deep per worker
# at roughly 500 ms each. Blocked workers are cheap: 32 of them still hold
# concurrent PostgreSQL connections well inside the limit of 100, and preload
# keeps their memory modest against 36 GB.
#
# This does not help the sign-in storm, which is genuinely CPU-bound on PBKDF2
# and is recorded as its own finding.
workers = 32
worker_class = 'sync'
timeout = 120
keepalive = 5


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

# preload_app was tried and reverted (CRV2-07). It was adopted to remove a
# worker cold start that later proved to be sign-in contamination, and a
# direct comparison found no benefit: time to settle was 38.65 s with it and
# 31.64 s without, with slow-request counts of 29 against 31 and maxima of
# 1328 ms against 1244 ms. Measured under the rule set before the run -- keep
# only if it saves more than a second -- it saves nothing, so it is not
# shipped.
