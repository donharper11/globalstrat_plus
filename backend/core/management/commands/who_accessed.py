"""Answer "who accessed Team X, Round Y?" from the read-evidence table.

The question a disclosure dispute actually asks. It is answered from
`competition_sensitive_read_event` alone — no web-server log, no reasoning from
absence — and it reports refused attempts alongside successful reads, because
a rival who tried and was denied is part of the answer.
"""
import json

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from core.models import SensitiveReadEvent


class Command(BaseCommand):
    help = 'Report who read a team\'s raw decisions or audit payloads.'

    def add_arguments(self, parser):
        parser.add_argument('--game', type=int, default=None)
        parser.add_argument('--team', type=int, default=None)
        parser.add_argument('--round', type=int, default=None)
        parser.add_argument('--user', type=int, default=None,
                            help='Filter to one actor id.')
        parser.add_argument('--category', choices=('decisions', 'audit'),
                            default=None)
        parser.add_argument('--outcome', choices=('allowed', 'denied', 'error'),
                            default=None)
        parser.add_argument('--since', default=None,
                            help='ISO timestamp lower bound.')
        parser.add_argument('--limit', type=int, default=200)
        parser.add_argument('--json', action='store_true')

    def handle(self, *args, **options):
        queryset = SensitiveReadEvent.objects.all()
        for field, key in (('game_id_read', 'game'), ('team_id_read', 'team'),
                           ('round_number_read', 'round'),
                           ('actor_user_id', 'user'), ('category', 'category'),
                           ('outcome', 'outcome')):
            if options[key] is not None:
                queryset = queryset.filter(**{field: options[key]})
        if options['since']:
            moment = parse_datetime(options['since'])
            if moment is None:
                raise SystemExit(f"Cannot parse --since {options['since']!r}")
            queryset = queryset.filter(created_at__gte=moment)

        total = queryset.count()
        rows = list(queryset.order_by('-id')[:options['limit']])
        records = [{
            'id': row.id,
            'at': row.created_at.isoformat(),
            'actor_user_id': row.actor_user_id,
            'username': row.username,
            'outcome': row.outcome,
            'status': row.status_code,
            'category': row.category,
            'game': row.game_id_read,
            'team': row.team_id_read,
            'round': row.round_number_read,
            'endpoint': row.endpoint,
            'request_id': row.request_id,
        } for row in rows]

        if options['json']:
            self.stdout.write(json.dumps(
                {'total': total, 'shown': len(records), 'reads': records},
                indent=2, sort_keys=True))
            return

        self.stdout.write(f'{total} matching reads; showing {len(records)} '
                          '(most recent first).')
        for record in records:
            who = record['username'] or f"user {record['actor_user_id']}" \
                if record['actor_user_id'] is not None else 'anonymous'
            self.stdout.write(
                f"  {record['at']}  {record['outcome']:<8} {who:<24} "
                f"g{record['game']} t{record['team']} r{record['round']}  "
                f"{record['category']:<9} {record['endpoint']}  "
                f"req={record['request_id']}")
        if not records:
            self.stdout.write(
                'No matching reads. This table records every registered route '
                'in core/services/read_inventory.json; an empty result means '
                'nobody reached one of them with these filters.')
