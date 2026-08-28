"""Replay one resolved round and prove the result is byte-identical.

The supported command GSP-CRV2-01 requirement 6 asks for. It exports the
recorded manifest first, optionally restores the pre-resolution backup,
**verifies the input before anything is mutated**, re-runs resolution, and
prints per-section diffs for whatever did not match.

Typical use, against an isolated database:

    DB_NAME=globalstrat_replay python3 manage.py replay_round \\
        --game-id 31 --round 3 --restore \\
        --confirm REPLAY-GAME-31-ROUND-3 \\
        --evidence-dir handoff_readiness_v2/evidence/determinism/run-a

Verification is a hard gate: if the restored database does not rebuild to the
recorded input manifest, the command reports the differing sections and exits
without calling the engine.
"""
import gzip
import json
import pathlib

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from core.models import Game, ResolutionManifest, Round
from core.services.canonical_json import canonical_dumps, canonical_sha256
from core.services import resolution_manifest as rm


EXIT_INPUT_MISMATCH = 2
EXIT_OUTPUT_MISMATCH = 3


class Command(BaseCommand):
    help = 'Verify and replay a resolved round, reporting per-section diffs.'

    def add_arguments(self, parser):
        parser.add_argument('--game-id', type=int, required=True)
        parser.add_argument('--round', type=int, required=True, dest='round_number')
        parser.add_argument('--evidence-dir', required=True,
                            help='Directory for the manifest, diffs and report.')
        parser.add_argument('--expected-manifest',
                            help='Manifest JSON exported by an earlier run, '
                                 'plain or gzipped. Use this when the database '
                                 'holding the original row has already been '
                                 'overwritten.')
        parser.add_argument('--require-env', action='append', default=[],
                            metavar='KEY=VALUE',
                            help='Assert an environment-fingerprint field '
                                 'before doing anything, e.g. '
                                 '--require-env tz_env=Asia/Kolkata. Repeatable. '
                                 'A label on a run is not evidence that the run '
                                 'happened that way; this makes the claim fail '
                                 'closed.')
        parser.add_argument('--allow-source-mismatch', action='store_true',
                            help='Replay even though the running source tree '
                                 'differs from the one that resolved the round. '
                                 'The result is then not a reproduction.')
        parser.add_argument('--export-only', action='store_true',
                            help='Write the recorded manifest and stop.')
        parser.add_argument('--verify-only', action='store_true',
                            help='Verify the input state and stop before the engine.')
        parser.add_argument('--restore', action='store_true',
                            help='Restore the pre-resolution backup first. '
                                 'Destroys the target database.')
        parser.add_argument('--confirm', default='',
                            help='Required with --restore: REPLAY-GAME-<id>-ROUND-<n>.')
        parser.add_argument('--label', default='replay',
                            help='Name for this run inside the evidence files.')
        parser.add_argument('--wait-narrative', type=int, default=0,
                            help='Seconds to wait for Phase 2 before hashing the '
                                 'narrative envelope again. Phase 2 is the only '
                                 'LLM path, so this is what shows that a changed '
                                 'model moves the prose and not the result.')

    # -- helpers ------------------------------------------------------------

    def _write(self, directory, name, payload):
        target = directory / name
        target.write_text(canonical_dumps(payload) + '\n', encoding='utf-8')
        return target

    def _read_manifest_file(self, path):
        """Read an exported manifest, transparently handling gzip."""
        target = pathlib.Path(path)
        if not target.exists() and target.with_suffix(
                target.suffix + '.gz').exists():
            target = target.with_suffix(target.suffix + '.gz')
        opener = gzip.open if target.suffix == '.gz' else open
        with opener(target, 'rt', encoding='utf-8') as stream:
            return json.load(stream)

    def _export(self, manifest):
        rm.require_schema_version(manifest)
        return {
            'schema_version': manifest.schema_version,
            'source_tree_sha256': manifest.source_tree_sha256,
            'game_id': manifest.game_id,
            'round_number': manifest.round.round_number,
            'seed': manifest.seed,
            'input_sha256': manifest.input_sha256,
            'output_sha256': manifest.output_sha256,
            'narrative_sha256': manifest.narrative_sha256,
            'code_revision': manifest.code_revision,
            'backup_path': manifest.backup_path,
            'environment': manifest.environment,
            'input_manifest': manifest.input_manifest,
            'output_manifest': manifest.output_manifest,
            'narrative_manifest': manifest.narrative_manifest,
        }

    # -- main ---------------------------------------------------------------

    def handle(self, *args, **options):
        game_id, round_number = options['game_id'], options['round_number']
        evidence = pathlib.Path(options['evidence_dir']).resolve()
        evidence.mkdir(parents=True, exist_ok=True)

        # Environment assertions run first: if this process is not the
        # environment the run claims to be, nothing it produces is evidence.
        observed = rm.environment_fingerprint()
        env_report = self._check_required_env(options['require_env'], observed)

        expected = None
        if options['expected_manifest']:
            expected = self._read_manifest_file(options['expected_manifest'])
        else:
            manifest = ResolutionManifest.objects.select_related('game', 'round').filter(
                game_id=game_id, round__round_number=round_number).first()
            if not manifest:
                raise CommandError(
                    f'No resolution manifest for game {game_id} round {round_number}. '
                    f'Pass --expected-manifest if the database has been replaced.')
            expected = self._export(manifest)
        if rm.envelope_schema_version(expected) != rm.MANIFEST_SCHEMA_VERSION:
            raise CommandError(
                f'Manifest is schema version {expected.get("schema_version")}; '
                f'replay requires version {rm.MANIFEST_SCHEMA_VERSION}. A '
                f'version-1 manifest does not describe the full envelope and '
                f'its hashes are not comparable.')
        manifest_path = self._write(evidence, 'expected-manifest.json', expected)
        self.stdout.write(f'Recorded manifest exported to {manifest_path}')
        if options['export_only']:
            return

        # Source identity, before the restore and before the engine. A replay
        # that runs different code is not a reproduction of anything.
        from core.services.build_identity import build_identity
        identity = build_identity()
        source_report = {
            'expected_source_tree_sha256': expected.get('source_tree_sha256', ''),
            'actual_source_tree_sha256': identity['source_tree_sha256'],
            'expected_code_revision': expected.get('code_revision', ''),
            'actual_code_revision': identity['code_revision'],
            'source_file_count': identity['source_file_count'],
            'override': bool(options['allow_source_mismatch']),
        }
        source_report['matches'] = (
            source_report['expected_source_tree_sha256'] ==
            source_report['actual_source_tree_sha256'])
        self._write(evidence, 'source-identity.json',
                    {**source_report, 'required_env': env_report})
        if not source_report['matches']:
            message = (
                'Source tree mismatch: the round was resolved by '
                f'{source_report["expected_source_tree_sha256"] or "(unrecorded)"} '
                f'but this process is running '
                f'{source_report["actual_source_tree_sha256"]}. Check out the '
                f'recorded revision '
                f'({source_report["expected_code_revision"] or "unknown"}) '
                f'before replaying.')
            if not options['allow_source_mismatch']:
                raise CommandError(message + ' Pass --allow-source-mismatch to '
                                             'proceed; the run is then not a '
                                             'reproduction.')
            self.stderr.write(self.style.WARNING(message))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Source verified: {source_report["actual_source_tree_sha256"]}'))

        if options['restore']:
            token = f'REPLAY-GAME-{game_id}-ROUND-{round_number}'
            if options['confirm'] != token:
                raise CommandError(f'Confirmation mismatch; expected {token}.')
            if not getattr(settings, 'COMPETITION_RECOVERY_ENABLED', False):
                raise CommandError(
                    'Restoring requires COMPETITION_RECOVERY_ENABLED=true and an '
                    'isolated database.')
            from core.services.competition_backup import restore_database
            verified = restore_database(expected['backup_path'])
            connection.connect()
            self.stdout.write(
                f'Restored {verified["path"]} (sha256 {verified["sha256"]}).')

        game = Game.objects.filter(pk=game_id).first()
        round_obj = Round.objects.filter(game_id=game_id,
                                         round_number=round_number).first()
        if not game or not round_obj:
            raise CommandError('Game or round is not present in this database.')

        # --- verify the input before a single value is mutated -------------
        rebuilt_input, _snapshot = rm.build_input_manifest(game, round_obj)
        recorded_input = expected['input_manifest']
        input_report = {
            'expected_sha256': canonical_sha256(recorded_input),
            'actual_sha256': canonical_sha256(rebuilt_input),
            'recorded_sha256': expected['input_sha256'],
        }
        input_report['matches'] = (
            input_report['expected_sha256'] == input_report['actual_sha256'])
        if not input_report['matches']:
            input_report['section_diffs'] = rm.diff_sections(
                recorded_input.get('sections', {}), rebuilt_input.get('sections', {}))
            input_report['scalar_diffs'] = {
                name: {'expected': recorded_input.get(name),
                       'actual': rebuilt_input.get(name)}
                for name in ('seed', 'seed_inputs', 'migrations', 'round_number',
                             'game', 'field_inventory_sha256')
                if recorded_input.get(name) != rebuilt_input.get(name)}
        self._write(evidence, 'input-verification.json', input_report)
        if not input_report['matches']:
            self.stderr.write(self.style.ERROR(
                'INPUT VERIFICATION FAILED — the engine was not run.'))
            self._print_diffs(input_report.get('section_diffs', {}),
                              input_report.get('scalar_diffs', {}))
            raise SystemExit(EXIT_INPUT_MISMATCH)
        self.stdout.write(self.style.SUCCESS(
            f'Input verified: {input_report["actual_sha256"]}'))
        if options['verify_only']:
            return

        # --- replay --------------------------------------------------------
        from core.engine.advance_round import process_round
        result = process_round(game_id)
        round_obj.refresh_from_db()
        replayed = ResolutionManifest.objects.select_related(
            'game', 'round').get(round=round_obj)

        recorded_output = expected['output_manifest']
        output_report = {
            'label': options['label'],
            'process_result': {k: v for k, v in result.items()
                               if k != 'phase_1_time'},
            'expected_output_sha256': canonical_sha256(recorded_output),
            'actual_output_sha256': replayed.output_sha256,
            'expected_narrative_sha256': expected['narrative_sha256'],
            'actual_narrative_sha256': replayed.narrative_sha256,
            'expected_code_revision': expected['code_revision'],
            'actual_code_revision': replayed.code_revision,
            'expected_environment': expected['environment'],
            'actual_environment': replayed.environment,
            'source_identity': source_report,
            'required_env': env_report,
        }
        output_report['competitive_match'] = (
            output_report['expected_output_sha256'] ==
            output_report['actual_output_sha256'])
        output_report['narrative_match'] = (
            output_report['expected_narrative_sha256'] ==
            output_report['actual_narrative_sha256'])
        if not output_report['competitive_match']:
            output_report['section_diffs'] = rm.diff_sections(
                recorded_output.get('sections', {}),
                replayed.output_manifest.get('sections', {}))
            output_report['digest_diffs'] = {
                name: {'expected': recorded_output.get('section_digests', {}).get(name),
                       'actual': replayed.output_section_digests.get(name)}
                for name in sorted(set(recorded_output.get('section_digests', {})) |
                                   set(replayed.output_section_digests))
                if recorded_output.get('section_digests', {}).get(name) !=
                replayed.output_section_digests.get(name)}
        if options['wait_narrative']:
            phase_2, narrative_body = self._wait_for_phase_2(
                round_obj, options['wait_narrative'])
            output_report['post_phase_2'] = phase_2
            # The prose itself, not only its digest: "the narrative differed"
            # is a claim a reader should be able to check.
            self._write(evidence, 'post-phase2-narrative.json', narrative_body)

        self._write(evidence, 'replay-report.json', output_report)
        self._write(evidence, 'replayed-manifest.json', self._export(replayed))

        self.stdout.write(
            f'Competitive hash expected {output_report["expected_output_sha256"]}')
        self.stdout.write(
            f'Competitive hash actual   {output_report["actual_output_sha256"]}')
        self.stdout.write(
            f'Narrative hash expected   {output_report["expected_narrative_sha256"]}')
        self.stdout.write(
            f'Narrative hash actual     {output_report["actual_narrative_sha256"]}')
        if not output_report['competitive_match']:
            self.stderr.write(self.style.ERROR('COMPETITIVE HASH MISMATCH'))
            self._print_diffs(output_report.get('section_diffs', {}), {})
            raise SystemExit(EXIT_OUTPUT_MISMATCH)
        if not output_report['narrative_match']:
            self.stdout.write(self.style.WARNING(
                'Narrative hash differs. Reported separately; the competitive '
                'result is unaffected.'))
        self.stdout.write(self.style.SUCCESS('Replay reproduced the round exactly.'))

    def _check_required_env(self, requirements, observed):
        """Fail closed when the process is not the environment it claims.

        Run D of the determinism evidence exists to show a replay under a
        different timezone and locale. A shell label proves nothing about the
        process that actually did the canonicalisation, so the claim is made
        as an assertion against this process's own fingerprint.
        """
        report, failures = [], []
        for requirement in requirements:
            if '=' not in requirement:
                raise CommandError(
                    f'--require-env expects KEY=VALUE, got {requirement!r}.')
            key, _, expected_value = requirement.partition('=')
            key, expected_value = key.strip(), expected_value.strip()
            if key not in observed:
                raise CommandError(
                    f'--require-env names {key!r}, which is not an environment '
                    f'fingerprint field. Available: {sorted(observed)}.')
            actual = observed[key]
            actual_text = (','.join(str(item) for item in actual)
                           if isinstance(actual, list) else str(actual))
            ok = actual_text == expected_value
            report.append({'key': key, 'expected': expected_value,
                           'actual': actual_text, 'matches': ok})
            if not ok:
                failures.append(f'{key}: expected {expected_value!r}, '
                                f'process reports {actual_text!r}')
        if failures:
            raise CommandError(
                'This process is not the environment the run claims to be:\n  '
                + '\n  '.join(failures))
        for item in report:
            self.stdout.write(f'Environment verified: {item["key"]}='
                              f'{item["actual"]}')
        return report

    def _wait_for_phase_2(self, round_obj, seconds):
        """Let the background narrative thread finish, then re-hash the prose.

        The competitive hash is taken inside the Phase-1 transaction and so
        cannot see Phase 2 at all. Re-hashing the narrative envelope afterwards
        is what makes a changed model, or an unreachable endpoint, visible in
        the evidence instead of merely asserted.
        """
        import time as _time
        deadline = _time.monotonic() + seconds
        while _time.monotonic() < deadline:
            round_obj.refresh_from_db()
            if (round_obj.processing_status == 'FULLY_COMPLETE' or
                    round_obj.narrative_error):
                break
            _time.sleep(2)
        round_obj.refresh_from_db()
        _competitive, narrative = rm.build_output_manifest(round_obj)
        return {
            'processing_status': round_obj.processing_status,
            'narrative_generated': round_obj.narrative_generated,
            'narrative_error': round_obj.narrative_error,
            'narrative_sha256': canonical_sha256(narrative),
            'section_digests': narrative.get('section_digests', {}),
            'llm_endpoint': getattr(settings, 'DASHSCOPE_COMPATIBLE_URL', ''),
            'llm_model': getattr(settings, 'DASHSCOPE_MODEL', ''),
            'llm_key_configured': bool(getattr(settings, 'DASHSCOPE_API_KEY', '')),
        }, narrative

    def _print_diffs(self, section_diffs, scalar_diffs):
        for name, value in sorted(scalar_diffs.items()):
            self.stderr.write(f'  scalar {name}: expected {value["expected"]!r} '
                              f'actual {value["actual"]!r}')
        for name, diff in sorted(section_diffs.items()):
            self.stderr.write(
                f'  section {name}: {diff["missing_count"]} missing, '
                f'{diff["added_count"]} added, {diff["changed_count"]} changed')
            for row in diff['changed_rows'][:3]:
                for column, values in list(row['fields'].items())[:4]:
                    self.stderr.write(
                        f'      {row["row"]}.{column}: '
                        f'{values["expected"]!r} -> {values["actual"]!r}')
            for row in diff['missing_rows'][:3]:
                self.stderr.write(f'      missing {row}')
            for row in diff['added_rows'][:3]:
                self.stderr.write(f'      added   {row}')
