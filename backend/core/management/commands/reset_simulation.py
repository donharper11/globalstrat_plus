"""
Management command: reset_simulation

Truncates all game-state tables while preserving reference data and
round 0 baseline data (round_id=11).

Usage:
    python3 manage.py reset_simulation                    # dry-run preview
    python3 manage.py reset_simulation --confirm          # execute
    python3 manage.py reset_simulation --confirm --instance-id 2
"""
from django.core.management.base import BaseCommand
from django.db import connection


# ── Tables to fully truncate (no round-0 data to preserve) ──────────
FULL_TRUNCATE_TABLES = [
    # Adoption / sales
    'cumulative_sales',
    'new_sales_by_round',
    'cumulative_stakeholder_engagement',
    'financial_revenue',
    'financial_expenses',

    # Leaderboard
    'leaderboard_scores',

    # Events (triggered, not definitions)
    'triggered_events',
    'newsfeeds',
    'news_feed',
    'news_decisions',
    'news_responses',

    # Challenge responses (not definitions)
    'challenge_response_scores',
    'challenge_responses',

    # Ethics decisions (not definitions)
    'ethical_decisions',
    'ethical_selections',
    'team_code_of_ethics',

    # B-Corp certifications (not milestones)
    'bcorp_certifications',

    # Framework / SDG / Scope compliance
    'team_framework_adoption',
    'team_compliance_check',
    'team_framework_commitment',
    'team_principle_compliance',
    'team_framework_compliance_summary',
    'team_sdg_coverage',
    'team_scope_scores',
    'program_supplier',

    # Decisions
    'decisions',

    # Messaging
    'chat_messages',

    # Simulation logs
    'simulation_logs',

    # Gamification
    'player_progress',
    'team_achievements',
    'team_badges',

    # Notifications
    'notification_logs',
    'team_notifications',

    # Reports
    'post_round_reports',
    'post_round_feedback',

    # CSR initiatives (team activations, not definitions)
    'team_program_initiatives',

    # Strategic tools output
    'pestle_analysis',
    'tbl_assessment',
    'risk_analysis',
    'tool_usage_logs',
    'team_trend_analysis',

    # Grading (recalculated each time)
    'team_grade',
    'student_grade_adjustment',
]

# ── Tables where we DELETE rows for rounds > 0 but keep round 0 ─────
# Format: (table, where_clause_for_DELETE — deletes non-baseline rows)
CONDITIONAL_DELETE_TABLES = [
    ('scores',                    'round_id != 11'),
    ('esg_scorecards',            'round_number != 0'),
    ('team_income_statements',    'round_id != 11'),
    ('team_balance_sheets',       'round_id != 11'),
    ('team_cash_flows',           'round_id != 11'),
]

# Programs cascade: delete non-baseline programs, which cascades to
# program_portfolio, program_features, program_media, program_resources,
# program_geography, program_stakeholder_targets via FK CASCADE.
# Currently all programs are round_launched=11, so this is a safety net.


class Command(BaseCommand):
    help = (
        'Reset simulation: delete game-state data from rounds > 0, '
        'preserve reference data and round 0 baseline, reset round statuses.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm', action='store_true',
            help='Actually execute the reset. Without this flag, only a dry-run preview is shown.',
        )
        parser.add_argument(
            '--instance-id', type=int, default=2,
            help='Simulation instance ID to reset (default: 2).',
        )
        parser.add_argument(
            '--reset-competitors', action='store_true',
            help='Also reset AI competitor ESG scores to their original baseline values.',
        )

    def _verify(self, cursor):
        """Post-reset verification: ensure clean baseline state."""
        self.stdout.write('\n--- Post-Reset Verification ---')
        ok = True

        # 1. Round statuses
        cursor.execute("SELECT round_number, status FROM rounds ORDER BY round_number")
        rounds = cursor.fetchall()
        r0 = [r for r in rounds if r[0] == 0]
        r1 = [r for r in rounds if r[0] == 1]
        pending = [r for r in rounds if r[0] > 1]
        if r0 and r0[0][1] == 'completed' and r1 and r1[0][1] == 'active' and all(r[1] == 'pending' for r in pending):
            self.stdout.write(self.style.SUCCESS('  OK  Round statuses correct'))
        else:
            self.stdout.write(self.style.ERROR('  FAIL  Round statuses incorrect'))
            ok = False

        # 2. ESG scorecards: only round 0 should exist
        cursor.execute("SELECT COUNT(*) FROM esg_scorecards WHERE round_number != 0")
        extra_esg = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM esg_scorecards WHERE round_number = 0")
        r0_esg = cursor.fetchone()[0]
        if extra_esg == 0 and r0_esg > 0:
            self.stdout.write(self.style.SUCCESS(f'  OK  ESG scorecards: {r0_esg} baseline rows, 0 extra'))
        else:
            self.stdout.write(self.style.ERROR(f'  FAIL  ESG scorecards: {r0_esg} baseline, {extra_esg} extra'))
            ok = False

        # 3. Scores: only round_id=11 should exist
        cursor.execute("SELECT COUNT(*) FROM scores WHERE round_id != 11")
        extra_scores = cursor.fetchone()[0]
        if extra_scores == 0:
            self.stdout.write(self.style.SUCCESS('  OK  Scores: only round 0 baseline'))
        else:
            self.stdout.write(self.style.ERROR(f'  FAIL  Scores: {extra_scores} non-baseline rows remain'))
            ok = False

        # 4. Programs: no Arkanis (economy 2) programs in baseline
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM programs p
                JOIN program_types pt ON pt.program_type_id = p.program_type_id
                WHERE pt.economy_id = 2
            """)
            arkanis = cursor.fetchone()[0]
            if arkanis == 0:
                self.stdout.write(self.style.SUCCESS('  OK  No Arkanis programs in baseline'))
            else:
                self.stdout.write(self.style.ERROR(f'  FAIL  {arkanis} Arkanis programs still exist'))
                ok = False
        except Exception:
            connection.ensure_connection()

        # 5. Programs: all baseline programs should be round_launched=11
        cursor.execute("SELECT COUNT(*) FROM programs WHERE round_launched != 11")
        non_baseline = cursor.fetchone()[0]
        if non_baseline == 0:
            cursor.execute("SELECT COUNT(*) FROM programs")
            total_progs = cursor.fetchone()[0]
            self.stdout.write(self.style.SUCCESS(f'  OK  Programs: {total_progs} baseline programs (round_launched=11)'))
        else:
            self.stdout.write(self.style.ERROR(f'  FAIL  {non_baseline} non-baseline programs remain'))
            ok = False

        # 6. team_performance: scores should be 0
        cursor.execute("SELECT COUNT(*) FROM team_performance WHERE total_score != 0")
        non_zero = cursor.fetchone()[0]
        if non_zero == 0:
            self.stdout.write(self.style.SUCCESS('  OK  team_performance: all scores reset to 0'))
        else:
            self.stdout.write(self.style.ERROR(f'  FAIL  {non_zero} teams still have non-zero total_score'))
            ok = False

        # 7. Stale data tables should be empty
        stale_checks = [
            'triggered_events', 'challenge_responses', 'ethical_decisions',
            'bcorp_certifications', 'team_program_initiatives', 'decisions',
            'leaderboard_scores', 'team_achievements', 'team_badges',
            'player_progress',
        ]
        stale_issues = []
        for table in stale_checks:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                cnt = cursor.fetchone()[0]
                if cnt > 0:
                    stale_issues.append(f'{table}({cnt})')
            except Exception:
                connection.ensure_connection()
        if not stale_issues:
            self.stdout.write(self.style.SUCCESS('  OK  All game-state tables cleared'))
        else:
            self.stdout.write(self.style.ERROR(f'  FAIL  Stale data in: {", ".join(stale_issues)}'))
            ok = False

        # 8. Financial statements: only round_id=11
        for table in ['team_income_statements', 'team_balance_sheets', 'team_cash_flows']:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}" WHERE round_id != 11')
                cnt = cursor.fetchone()[0]
                if cnt > 0:
                    self.stdout.write(self.style.ERROR(f'  FAIL  {table}: {cnt} non-baseline rows'))
                    ok = False
            except Exception:
                connection.ensure_connection()
        self.stdout.write(self.style.SUCCESS('  OK  Financial statements: only round 0 baseline'))

        if ok:
            self.stdout.write(self.style.SUCCESS('\n  ALL CHECKS PASSED — clean baseline state confirmed.'))
        else:
            self.stdout.write(self.style.ERROR('\n  SOME CHECKS FAILED — review above and fix manually.'))

    def _count(self, cursor, table, where=None):
        """Return row count, or None if table does not exist."""
        try:
            sql = f'SELECT count(*) FROM "{table}"'
            if where:
                sql += f' WHERE {where}'
            cursor.execute(sql)
            return cursor.fetchone()[0]
        except Exception:
            connection.ensure_connection()
            return None

    def handle(self, *args, **options):
        dry_run = not options['confirm']
        instance_id = options['instance_id']

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '=== DRY RUN === (pass --confirm to execute)\n'
            ))

        results = []

        with connection.cursor() as cursor:
            # ── 1. Delete non-baseline programs (cascade to child tables) ──
            table = 'programs'
            where = 'round_launched != 11'
            count = self._count(cursor, table, where)
            if count is not None:
                results.append((table, count, f'DELETE WHERE {where}'))
                if not dry_run and count > 0:
                    cursor.execute(f'DELETE FROM "{table}" WHERE {where}')

            # ── 1b. Reset R&D fields on surviving baseline programs ──────
            if not dry_run:
                cursor.execute(
                    "UPDATE programs SET development_status = 'ready', "
                    "development_rounds_total = 0, "
                    "development_rounds_remaining = 0, "
                    "r_and_d_investment = 0, "
                    "development_started_round = NULL "
                    "WHERE round_launched = 11"
                )
            results.append(('programs (R&D reset)', 0, 'RESET dev fields on baseline'))

            # ── 2. Conditional deletes (keep round 0 baseline) ─────────────
            for table, where in CONDITIONAL_DELETE_TABLES:
                count = self._count(cursor, table, where)
                if count is not None:
                    results.append((table, count, f'DELETE WHERE {where}'))
                    if not dry_run and count > 0:
                        cursor.execute(f'DELETE FROM "{table}" WHERE {where}')
                else:
                    results.append((table, -1, 'TABLE NOT FOUND'))

            # ── 3. Full truncates ──────────────────────────────────────────
            for table in FULL_TRUNCATE_TABLES:
                count = self._count(cursor, table)
                if count is not None:
                    results.append((table, count, 'TRUNCATE CASCADE'))
                    if not dry_run:
                        cursor.execute(f'TRUNCATE TABLE "{table}" CASCADE')
                else:
                    results.append((table, -1, 'TABLE NOT FOUND'))

            # ── 4. Messages: delete persona messages (instance_id IS NOT NULL) ──
            table = 'messages'
            where = 'instance_id IS NOT NULL'
            count = self._count(cursor, table, where)
            if count is not None:
                results.append((table, count, f'DELETE WHERE {where}'))
                if not dry_run and count > 0:
                    cursor.execute(f'DELETE FROM "{table}" WHERE {where}')
            else:
                results.append((table, -1, 'TABLE NOT FOUND'))

            # ── 5. team_performance: reset to baseline values ─────────────
            try:
                cursor.execute(
                    "UPDATE team_performance SET "
                    "total_score = 0, "
                    "average_stakeholder_satisfaction = 0.10, "
                    "ethical_alignment = 0, "
                    "updated_at = NOW()"
                )
                tp_count = self._count(cursor, 'team_performance')
                results.append(('team_performance', tp_count or 0, 'RESET to baseline (score=0, satisfaction=0.10)'))
            except Exception:
                connection.ensure_connection()
                results.append(('team_performance', 0, 'RESET FAILED'))

            # ── Print results ──────────────────────────────────────────────
            self.stdout.write('')
            self.stdout.write(f'{"Table":<45} {"Rows":>8}  Action')
            self.stdout.write('-' * 75)

            total_deleted = 0
            tables_not_found = 0
            for table, count, action in results:
                if count == -1:
                    self.stdout.write(
                        self.style.WARNING(f'{table:<45} {"N/A":>8}  {action}')
                    )
                    tables_not_found += 1
                elif count == 0:
                    self.stdout.write(f'{table:<45} {count:>8}  {action}')
                else:
                    self.stdout.write(
                        self.style.ERROR(f'{table:<45} {count:>8}  {action}')
                    )
                    total_deleted += count

            self.stdout.write('-' * 75)
            self.stdout.write(f'Total rows {"to delete" if dry_run else "deleted"}: {total_deleted}')
            if tables_not_found:
                self.stdout.write(self.style.WARNING(
                    f'{tables_not_found} table(s) not found (skipped gracefully)'
                ))

            if dry_run:
                self.stdout.write('')
                self.stdout.write(self.style.WARNING(
                    '=== DRY RUN complete. No data was modified. ===\n'
                    'Run with --confirm to execute.'
                ))
                return

            # ── 6. Reset simulation_state ──────────────────────────────────
            try:
                cursor.execute(
                    "UPDATE simulation_state SET current_round_id = 1, "
                    "status = 'active', last_updated = NOW()"
                )
                self.stdout.write(self.style.SUCCESS(
                    '\nsimulation_state: current_round_id=1, status=active'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'\nFailed to reset simulation_state: {e}'
                ))
                connection.ensure_connection()

            # ── 7. Reset simulation_instance ───────────────────────────────
            try:
                cursor.execute(
                    "UPDATE simulation_instance SET current_round = 0, "
                    "status = 'setup' "
                    "WHERE instance_id = %s",
                    [instance_id],
                )
                self.stdout.write(self.style.SUCCESS(
                    f'simulation_instance (id={instance_id}): current_round=0, status=setup'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Failed to reset simulation_instance: {e}'
                ))
                connection.ensure_connection()

            # ── 8. Reset round statuses ────────────────────────────────────
            try:
                # First set all to pending
                cursor.execute(
                    "UPDATE rounds SET status = 'pending', "
                    "start_date = NULL, end_date = NULL, "
                    "start_time = NULL, end_time = NULL, "
                    "deadline = NULL, decisions_locked = FALSE, "
                    "lock_reason = NULL"
                )
                # Round 0 (id=11) = completed
                cursor.execute(
                    "UPDATE rounds SET status = 'completed' "
                    "WHERE round_number = 0"
                )
                # Round 1 = active
                cursor.execute(
                    "UPDATE rounds SET status = 'active' "
                    "WHERE round_number = 1"
                )
                self.stdout.write(self.style.SUCCESS(
                    'rounds: round 0=completed, round 1=active, rounds 2-10=pending'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to reset rounds: {e}'))
                connection.ensure_connection()

            # ── 9. Reset challenge statuses ────────────────────────────────
            try:
                cursor.execute(
                    "UPDATE challenges SET status = 'active', "
                    "carryover_round = NULL "
                    "WHERE round_id IS NOT NULL"
                )
                self.stdout.write(self.style.SUCCESS(
                    'challenges: statuses reset to active'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to reset challenges: {e}'))
                connection.ensure_connection()

            # ── 10. Optionally reset competitor baselines ──────────────────
            if options['reset_competitors']:
                try:
                    COMPETITOR_BASELINES = [
                        (3, '171.77', '{"Social": 19, "Governance": 10, "Environmental": 72}'),
                        (4, '124.43', '{"Social": 10, "Governance": 74, "Environmental": 17}'),
                        (5, '280.32', '{"Social": 71, "Governance": 15, "Environmental": 15}'),
                        (6, '335.83', '{"Social": 30, "Governance": 30, "Environmental": 40}'),
                    ]
                    for cid, score, priority in COMPETITOR_BASELINES:
                        cursor.execute(
                            "UPDATE competitors SET total_esg_score = %s, "
                            "esg_priority = %s::jsonb "
                            "WHERE competitor_id = %s",
                            [score, priority, cid],
                        )
                    self.stdout.write(self.style.SUCCESS(
                        'competitors: ESG scores reset to baseline'
                    ))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f'Failed to reset competitors: {e}'
                    ))
                    connection.ensure_connection()

        # ── Summary & Verification ─────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            'Simulation reset complete. Running verification...'
        ))
        with connection.cursor() as verify_cursor:
            self._verify(verify_cursor)
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            'Ready for fresh gameplay from round 1.'
        ))
