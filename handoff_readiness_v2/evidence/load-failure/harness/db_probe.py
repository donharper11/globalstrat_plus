"""Database saturation, taken from the server rather than inferred."""


def run(database):
    from django.db import connection
    out = {}
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = %s",
                    [database])
        out['connections_now'] = cur.fetchone()[0]
        cur.execute("SELECT setting::int FROM pg_settings "
                    "WHERE name = 'max_connections'")
        out['max_connections'] = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = %s AND wait_event_type = 'Lock'",
                    [database])
        out['waiting_on_locks'] = cur.fetchone()[0]
        cur.execute("SELECT deadlocks, xact_commit, xact_rollback "
                    "FROM pg_stat_database WHERE datname = %s", [database])
        row = cur.fetchone()
        out['deadlocks'], out['commits'], out['rollbacks'] = row
    return out
