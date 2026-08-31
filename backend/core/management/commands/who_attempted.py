"""Answer "did anyone try to act on our competition?" from the refusal ledger.

The companion to `who_accessed`. That command answers who *read* a team's
decisions; this one answers who tried to *change* a game they do not own and
was refused at the authorization boundary.

Read-only by construction: it runs one SELECT and writes nothing. The rows it
reports are append-only, trigger-protected and chained, and this command has no
means of altering them even if it wanted to.

Payloads are not stored on these rows and so cannot be printed here. What the
caller was trying to send is not needed to investigate that they were refused,
and copying another cohort's payload into the evidence trail would defeat the
boundary that produced it.
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from core.models import AuthorizationRefusalEvent

COLUMNS = ('at', 'actor', 'game', 'method', 'endpoint', 'outcome',
           'reason', 'request_id')


class Command(BaseCommand):
    help = ('Report refused attempts to act on a game the caller does not own '
            '(authorization refusals).')

    def add_arguments(self, parser):
        parser.add_argument('--game', type=int, default=None,
                            help='Only attempts against this game id.')
        parser.add_argument('--request-id', default=None,
                            help='The exact correlation id from a 403 response.')
        parser.add_argument('--user', type=int, default=None,
                            help='Only attempts by this actor id.')
        parser.add_argument('--username', default=None,
                            help='Only attempts by this username (exact).')
        parser.add_argument('--method', default=None,
                            help='POST, PUT, PATCH or DELETE.')
        parser.add_argument('--route-contains', default=None,
                            help='Substring of the route or endpoint.')
        parser.add_argument('--since', default=None,
                            help='ISO timestamp lower bound.')
        parser.add_argument('--until', default=None,
                            help='ISO timestamp upper bound.')
        parser.add_argument('--limit', type=int, default=200)
        parser.add_argument('--json', action='store_true',
                            help='Machine-readable output for an incident file.')

    def _moment(self, value, flag):
        moment = parse_datetime(value)
        if moment is None:
            raise CommandError(f'Cannot parse {flag} {value!r}; use ISO 8601.')
        return moment

    def handle(self, *args, **options):
        queryset = AuthorizationRefusalEvent.objects.all()
        for field, key in (('game_id_attempted', 'game'),
                           ('actor_user_id', 'user'),
                           ('username', 'username'),
                           ('request_id', 'request_id')):
            if options[key] is not None:
                queryset = queryset.filter(**{field: options[key]})
        if options['method']:
            queryset = queryset.filter(method__iexact=options['method'])
        if options['route_contains']:
            from django.db.models import Q
            fragment = options['route_contains']
            queryset = queryset.filter(Q(route__icontains=fragment)
                                       | Q(endpoint__icontains=fragment))
        if options['since']:
            queryset = queryset.filter(
                created_at__gte=self._moment(options['since'], '--since'))
        if options['until']:
            queryset = queryset.filter(
                created_at__lte=self._moment(options['until'], '--until'))

        total = queryset.count()
        rows = list(queryset.order_by('-id')[:options['limit']])
        records = [{
            'id': row.id,
            'at': row.created_at.isoformat(),
            'actor_user_id': row.actor_user_id,
            'username': row.username,
            'game': row.game_id_attempted,
            'method': row.method,
            'route': row.route,
            'endpoint': row.endpoint,
            'outcome': row.outcome,
            'reason': row.reason,
            'request_id': row.request_id,
        } for row in rows]

        if options['json']:
            self.stdout.write(json.dumps(
                {'total': total, 'shown': len(records),
                 'refusals': records},
                indent=2, sort_keys=True))
            return

        if not records:
            self.stdout.write('No refused attempts match those filters.')
            return

        self.stdout.write(f'{total} refused attempt(s); showing {len(records)}.')
        self.stdout.write('')
        for row in records:
            actor = row['username'] or f"user {row['actor_user_id']}"
            self.stdout.write(f"{row['at']}  {actor}")
            self.stdout.write(
                f"    {row['method']} {row['endpoint']}  -> {row['outcome']}")
            self.stdout.write(f"    reason      {row['reason']}")
            self.stdout.write(f"    game        {row['game']}")
            self.stdout.write(f"    request id  {row['request_id']}")
            self.stdout.write('')
