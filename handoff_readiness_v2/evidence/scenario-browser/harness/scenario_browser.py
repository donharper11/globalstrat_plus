#!/usr/bin/env python3
"""Focused real-browser certification for one authored scenario.

The harness owns a disposable PostgreSQL database and local HTTP processes. It
never reads a deployed database or binds the production port.  It checks the
scenario's decision surface before resolution, its round-one result after real
Phase 1 processing, and the reopened decision surface after advancing to round
two.  English and zh-CN are exercised in separate Chromium contexts.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import importlib.util
import json
import os
import pathlib
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_WORKTREE = HERE.parents[3]
SCENARIOS = {
    'consumer_electronics_2026': {
        'file': 'scenarios/consumer_electronics_2026.yaml',
        'name': 'Consumer Electronics 2026',
    },
    'clean_energy_tech_2026': {
        'file': 'scenarios/clean_energy_tech_2026.yaml',
        'name': 'Clean Energy Technology 2026',
    },
    'media_entertainment_2026': {
        'file': 'scenarios/media_entertainment_2026.yaml',
        'name': 'Global Media & Entertainment 2026',
    },
}
LANGUAGES = ('en', 'zh-CN')
PASSWORD = 'scenario-browser-pass'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Disposable scenario decision/results/transition browser check')
    parser.add_argument(
        '--scenario', choices=sorted(SCENARIOS),
        default='consumer_electronics_2026',
        help='authored scenario slug (Consumer Electronics remains the default)')
    parser.add_argument(
        '--worktree', type=pathlib.Path, default=DEFAULT_WORKTREE,
        help='candidate worktree whose backend and frontend build are exercised')
    parser.add_argument(
        '--runtime', type=pathlib.Path,
        help='disposable logs/screenshots directory (default: a /tmp directory)')
    parser.add_argument(
        '--output', type=pathlib.Path,
        help='JSON report path (default: <runtime>/report.json)')
    parser.add_argument(
        '--candidate-revision',
        help='expected product revision; backend/frontend must be unchanged from it')
    parser.add_argument('--dry-run', action='store_true',
                        help='validate and print the resolved configuration only')
    return parser


def resolved_config(options: argparse.Namespace) -> dict:
    worktree = options.worktree.resolve()
    runtime = (options.runtime or pathlib.Path(
        f'/tmp/globalstrat-scenario-browser-{options.scenario}-{os.getpid()}')).resolve()
    output = (options.output or runtime / 'report.json').resolve()
    return {
        'scenario': options.scenario,
        'scenario_file': str(worktree / 'backend' /
                             SCENARIOS[options.scenario]['file']),
        'worktree': str(worktree),
        'runtime': str(runtime),
        'output': str(output),
        'frontend_build': str(
            worktree / 'frontend' / 'globalstrat-frontend' / 'build'),
        'languages': list(LANGUAGES),
        'candidate_revision': options.candidate_revision,
    }


def seed_fixture(scenario_slug: str) -> dict:
    """Create a minimal playable cohort. Called inside ``manage.py shell``."""
    from django.contrib.auth.models import User as DjangoUser
    from django.core.management import call_command
    from django.utils import timezone

    from core.models import Enrollment, Game, Round, Scenario, Team, User
    from core.models.course import Course, Section, SimulationInstance
    from core.models.team_state import TeamProduct, TeamProductMarket
    from core.utils.passwords import hash_password

    authored = SCENARIOS[scenario_slug]
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser(
            'scenario_browser_admin', 'browser@example.invalid', 'x')
    call_command('load_scenario', file=authored['file'], verbosity=0)
    scenario = Scenario.objects.get(name=authored['name'])
    game_name = f'Scenario browser: {scenario.name}'
    call_command('initialize_game', scenario=scenario.id, teams=2,
                 name=game_name, verbosity=0)
    game = Game.objects.get(name=game_name)
    teams = list(Team.objects.filter(game=game).order_by('id'))

    hashed = hash_password(PASSWORD)
    instructor, _ = User.objects.get_or_create(
        username='scenario_browser_instructor',
        defaults={'role': 'instructor',
                  'email': 'browser-instructor@example.invalid'})
    User.objects.filter(pk=instructor.pk).update(
        password_hash=hashed, role='instructor')
    course = Course.objects.create(
        course_code='SCENARIO-BROWSER', course_name='Scenario browser check',
        instructor_id=instructor.user_id, academic_year='2026',
        semester='Certification', is_active=True, created_at=timezone.now())
    section = Section.objects.create(
        course=course, section_code='BROWSER', section_name='Browser check',
        max_teams=2, team_size_min=1, team_size_max=2,
        is_active=True, created_at=timezone.now())
    game.section_id = section.section_id
    game.save(update_fields=['section_id'])
    SimulationInstance.objects.create(
        section=section, game_id=game.id, current_round=game.current_round,
        total_rounds=scenario.num_rounds, status='active',
        started_at=timezone.now(), created_at=timezone.now())

    students = []
    for index, team in enumerate(teams, start=1):
        username = f'scenario_browser_student_{index}'
        student, _ = User.objects.get_or_create(
            username=username,
            defaults={'role': 'student',
                      'email': f'{username}@example.invalid'})
        User.objects.filter(pk=student.pk).update(
            password_hash=hashed, role='student', team_id=team.id)
        Enrollment.objects.update_or_create(
            user_id=student.user_id, section=section,
            defaults={'team_id': team.id, 'is_active': True,
                      'enrolled_at': timezone.now()})
        students.append({'username': username, 'password': PASSWORD,
                         'team_id': team.id, 'user_id': student.user_id})

    primary_team = teams[0]
    product = (TeamProduct.objects.filter(team=primary_team)
               .order_by('id').first())
    product_market = (TeamProductMarket.objects
                      .filter(team_product__team=primary_team, is_active=True)
                      .select_related('market').order_by('id').first())
    if product is None or product_market is None:
        raise RuntimeError('scenario initialized without a product-market row')
    current = Round.objects.get(
        game=game, round_number=game.current_round)
    return {
        'game_id': game.id,
        'game_name': game.name,
        'scenario': scenario.name,
        'scenario_zh': getattr(scenario, 'name_zh', '') or scenario.name,
        'scenario_slug': scenario_slug,
        'round_number': current.round_number,
        'round_status': current.status,
        'team_id': primary_team.id,
        'team_name': primary_team.name,
        'student': students[0],
        'instructor': {'username': instructor.username, 'password': PASSWORD},
        'expected_product': product.name,
        'expected_market': {
            'en': product_market.market.name,
            'zh-CN': (getattr(product_market.market, 'name_zh', '')
                      or product_market.market.name),
        },
    }


def load_stack_module(worktree: pathlib.Path):
    path = (worktree / 'handoff_readiness_v2' / 'evidence' / 'load-failure' /
            'harness' / 'stack.py')
    spec = importlib.util.spec_from_file_location('scenario_browser_stack', path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load disposable stack helper: {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_database(stack, database: str, scenario_slug: str) -> dict:
    body = (
        'import json, sys\n'
        f'sys.path.insert(0, {str(HERE)!r})\n'
        'from scenario_browser import seed_fixture\n'
        f'fixture = seed_fixture({scenario_slug!r})\n'
        'print("---SCENARIO-BROWSER-SEED---")\n'
        'print(json.dumps(fixture, ensure_ascii=False))\n')
    result = stack.R.manage(database, 'shell', '-c', body, timeout=1800)
    marker = '---SCENARIO-BROWSER-SEED---'
    if result.returncode or marker not in result.stdout:
        raise RuntimeError(
            'scenario seeding failed:\n' + result.stdout[-4000:] +
            result.stderr[-4000:])
    payload = result.stdout.split(marker, 1)[1].strip().splitlines()[0]
    return json.loads(payload)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@contextlib.contextmanager
def frontend_proxy(worktree: pathlib.Path, build: pathlib.Path,
                   backend_base: str, runtime: pathlib.Path, stack):
    app_port = free_port()
    serve_app = (worktree / 'handoff_readiness_v2' / 'evidence' /
                 'post-close-disputes' / 'harness' / 'serve_app.py')
    log_path = runtime / 'frontend-proxy.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(
            [sys.executable, str(serve_app), str(build), backend_base,
             str(app_port)], stdout=log, stderr=subprocess.STDOUT,
            preexec_fn=os.setsid)
        try:
            base = f'http://127.0.0.1:{app_port}'
            stack.wait_for(base + '/', timeout=120)
            yield base
        finally:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=20)


def http_json(method: str, url: str, token: str | None = None,
              payload: dict | None = None) -> tuple[int, object, float]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header('Content-Type', 'application/json')
    if token:
        request.add_header('Authorization', f'Bearer {token}')
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=1800) as response:
            raw = response.read()
            body = json.loads(raw) if raw else {}
            return response.status, body, time.monotonic() - started
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            body = json.loads(raw) if raw else {}
        except ValueError:
            body = raw.decode('utf-8', 'replace')
        return exc.code, body, time.monotonic() - started


def instructor_token(base: str, fixture: dict) -> str:
    status, body, _ = http_json(
        'POST', base + '/api/auth/login/', payload=fixture['instructor'])
    if status != 200 or not isinstance(body, dict) or 'access' not in body:
        raise RuntimeError(f'instructor login failed: {status} {body}')
    return body['access']


def browser_request(page, path: str, method: str = 'GET',
                    payload: dict | None = None) -> dict:
    return page.evaluate("""async ({path, method, payload}) => {
      const response = await fetch(path, {method, headers: {
        Authorization: 'Bearer ' + localStorage.getItem('access_token'),
        'Accept-Language': localStorage.getItem('gs_language') || 'en',
        'Content-Type': 'application/json'
      }, body: payload == null ? undefined : JSON.stringify(payload)});
      return {status: response.status,
              body: await response.json().catch(() => null)};
    }""", {'path': path, 'method': method, 'payload': payload})


def browser_fetch(page, path: str) -> dict:
    return browser_request(page, path)


def login_page(browser, base: str, fixture: dict, language: str, record: dict):
    context = browser.new_context(viewport={'width': 1500, 'height': 1000})
    page = context.new_page()
    # Keep the pass offline without manufacturing browser console failures.
    page.route('**://fonts.googleapis.com/**', lambda route: route.fulfill(
        status=200, content_type='text/css', body=''))
    page.route('**://fonts.gstatic.com/**', lambda route: route.fulfill(
        status=200, content_type='font/woff2', body=b''))
    page.on('console', lambda message: record['console'].append({
        'language': language, 'type': message.type, 'text': message.text[:500]
    }) if message.type in ('warning', 'error') else None)
    page.on('response', lambda response: record['network'].append({
        'language': language, 'status': response.status,
        'url': response.url[:300]
    }) if response.status >= 400 else None)
    page.goto(base + '/login', wait_until='domcontentloaded')
    page.evaluate('(lang) => localStorage.setItem("gs_language", lang)', language)
    page.reload(wait_until='domcontentloaded')
    page.fill('input#username, input[name="username"]',
              fixture['student']['username'])
    page.fill('input#password, input[name="password"]',
              fixture['student']['password'])
    page.click('button[type="submit"]')
    page.wait_for_function('() => !!localStorage.getItem("access_token")',
                           timeout=30000)
    # AuthContext also persists this preference after login.  Waiting only for
    # the token races that PUT: a new English context can briefly receive the
    # preceding Chinese context's scenario fields even though its chrome is
    # already English. Make the same public preference call explicitly before
    # checking localized API-backed content.
    preference = browser_request(
        page, '/api/user/preferences/', 'PUT', {'language': language})
    if preference['status'] != 200:
        raise RuntimeError(
            f'language preference failed: {preference["status"]} '
            f'{preference.get("body")}')
    return context, page


def add_check(record: dict, language: str, phase: str, name: str,
              passed: bool, detail: str = '') -> None:
    record['checks'].append({
        'language': language, 'phase': phase, 'name': name,
        'passed': bool(passed), 'detail': str(detail)[:1200],
    })
    print(f"  {'PASS' if passed else 'FAIL'} {language:<5} {phase:<10} {name}",
          flush=True)


def decision_checks(browser, base: str, fixture: dict, language: str,
                    record: dict, worktree: pathlib.Path) -> None:
    context, page = login_page(browser, base, fixture, language, record)
    try:
        path = (f"/games/{fixture['game_id']}/teams/{fixture['team_id']}"
                '/decisions/marketing')
        page.goto(base + path, wait_until='domcontentloaded')
        page.wait_for_timeout(4500)
        text = page.inner_text('body')
        locale = json.loads((worktree / 'frontend' / 'globalstrat-frontend' /
                             'src' / 'locales' / f'{language}.json').read_text())
        title = locale['marketing']['title']
        market = fixture['expected_market'][language]
        add_check(record, language, 'decision', 'localized page title',
                  title in text, title)
        add_check(record, language, 'decision', 'scenario product rendered',
                  fixture['expected_product'] in text,
                  fixture['expected_product'])
        add_check(record, language, 'decision', 'scenario market rendered',
                  market in text, market)
        context_api = browser_fetch(
            page, f"/api/games/{fixture['game_id']}/teams/"
                  f"{fixture['team_id']}/context/marketing/")
        context_text = json.dumps(context_api.get('body'), ensure_ascii=False)
        add_check(record, language, 'decision', 'marketing context API',
                  context_api['status'] == 200 and
                  fixture['expected_product'] in context_text and market in context_text,
                  f"HTTP {context_api['status']}")
        if language == 'en' and isinstance(context_api.get('body'), dict):
            # Put one authentic product-market through the student write path,
            # so the results screen has a scenario market to render.  A forced
            # resolution of an entirely blank firm validly yields no market
            # rows and cannot prove the scenario-specific results surface.
            body = context_api['body']
            product = next(
                row for row in body['product_markets']
                if row['product_name'] == fixture['expected_product'])
            market_row = next(
                row for row in product['markets']
                if row['market__name'] == fixture['expected_market']['en'])
            market_id = market_row['market_id']
            key = f"{product['product_id']}_{market_id}"
            band = body['price_bands'][key]
            capacity_rows = body['production_capacity']
            source = next((row for row in capacity_rows
                           if row['market_id'] == market_id), capacity_rows[0])
            available = (int(source.get('own_capacity') or 0) +
                         int(source.get('contract_mfg_capacity') or 0))
            volume = max(1, min(1000, available))
            decision = {
                'team_product': product['product_id'],
                'market': market_id,
                'retail_price': band['anchor'],
                'promotion_budget': 0,
                'campaign_focus_feature_ids': [],
                'channel_digital_pct': 0.34,
                'channel_traditional_pct': 0.33,
                'channel_trade_pct': 0.33,
                'distribution_strategy': 'mass_retail',
                'distribution_investment': 0,
                'sales_team_count': 0,
                'distribution_channel_detail': {},
                'production_volume': volume,
                'production_source_market': source['market_id'],
                'demand_estimate': volume,
            }
            saved = browser_request(
                page, f"/api/games/{fixture['game_id']}/teams/"
                      f"{fixture['team_id']}/decisions/round/1/marketing/",
                'PATCH', {'marketing_decisions': [decision]})
            record['decision_fixture'] = {
                'product': fixture['expected_product'],
                'market': fixture['expected_market']['en'],
                'production_volume': volume,
                'status': saved['status'],
            }
            add_check(record, language, 'decision', 'scenario decision saved',
                      saved['status'] == 200, f"HTTP {saved['status']}")
        summary = browser_fetch(
            page, f"/api/games/{fixture['game_id']}/teams/"
                  f"{fixture['team_id']}/decisions/round/1/summary/")
        add_check(record, language, 'decision', 'round-one summary API',
                  summary['status'] == 200,
                  f"HTTP {summary['status']}")
        page.screenshot(path=str(pathlib.Path(record['runtime']) /
                                 f"{fixture['scenario_slug']}-decision-{language}.png"),
                        full_page=True)
    finally:
        context.close()


def results_checks(browser, base: str, fixture: dict, language: str,
                   record: dict, worktree: pathlib.Path) -> None:
    context, page = login_page(browser, base, fixture, language, record)
    try:
        path = (f"/games/{fixture['game_id']}/teams/{fixture['team_id']}"
                '/results/1')
        page.goto(base + path, wait_until='domcontentloaded')
        page.wait_for_timeout(8000)
        locale = json.loads((worktree / 'frontend' / 'globalstrat-frontend' /
                             'src' / 'locales' / f'{language}.json').read_text())
        title = locale['results_page']['title'].replace('{{round}}', '1')
        # Do not rely on Ant Design's remembered/default tab. Select the
        # surface named by the assertion before asking what it rendered.
        performance_tab = locale['results']['performance_overview']
        page.get_by_role('tab', name=performance_tab).click()
        page.wait_for_timeout(500)
        text = page.inner_text('body')
        add_check(record, language, 'results', 'localized results title',
                  title in text, title)
        add_check(record, language, 'results', 'performance result rendered',
                  locale['results_page']['performance_index'].casefold()
                  in text.casefold(),
                  locale['results_page']['performance_index'])
        results = browser_fetch(
            page, f"/api/games/{fixture['game_id']}/teams/"
                  f"{fixture['team_id']}/results/round/1/")
        body = results.get('body') if isinstance(results.get('body'), dict) else {}
        markets = body.get('markets') or []
        expected_market = fixture['expected_market'][language]
        market_names = [row.get('market_name') for row in markets]
        add_check(record, language, 'results', 'scenario results API',
                  results['status'] == 200 and bool(body.get('performance')) and
                  expected_market in market_names,
                  f"HTTP {results['status']}; markets={market_names}")
        tab_label = locale['results']['market_results']
        page.get_by_role('tab', name=tab_label).click()
        page.wait_for_timeout(1000)
        text = page.inner_text('body')
        add_check(record, language, 'results', 'scenario market result rendered',
                  expected_market in text, expected_market)
        page.screenshot(path=str(pathlib.Path(record['runtime']) /
                                 f"{fixture['scenario_slug']}-results-{language}.png"),
                        full_page=True)
    finally:
        context.close()


def transition_checks(browser, base: str, fixture: dict, language: str,
                      record: dict, worktree: pathlib.Path) -> None:
    context, page = login_page(browser, base, fixture, language, record)
    try:
        path = (f"/games/{fixture['game_id']}/teams/{fixture['team_id']}"
                '/decisions/summary')
        page.goto(base + path, wait_until='domcontentloaded')
        page.wait_for_timeout(4500)
        text = page.inner_text('body')
        locale = json.loads((worktree / 'frontend' / 'globalstrat-frontend' /
                             'src' / 'locales' / f'{language}.json').read_text())
        add_check(record, language, 'transition', 'round-two UI state',
                  'R2' in text and locale['summary_page']['title'] in text,
                  'R2; ' + locale['summary_page']['title'])
        summary = browser_fetch(
            page, f"/api/games/{fixture['game_id']}/teams/"
                  f"{fixture['team_id']}/decisions/round/2/summary/")
        add_check(record, language, 'transition', 'round-two summary API',
                  summary['status'] == 200,
                  f"HTTP {summary['status']}")
        page.screenshot(path=str(pathlib.Path(record['runtime']) /
                                 f"{fixture['scenario_slug']}-round2-{language}.png"),
                        full_page=True)
    finally:
        context.close()


def git_text(worktree: pathlib.Path, *args: str) -> str:
    return subprocess.run(['git', *args], cwd=worktree, capture_output=True,
                          text=True, check=True).stdout.strip()


def run(options: argparse.Namespace) -> int:
    config = resolved_config(options)
    print(json.dumps(config, indent=2, ensure_ascii=False))
    worktree = pathlib.Path(config['worktree'])
    runtime = pathlib.Path(config['runtime'])
    output = pathlib.Path(config['output'])
    if options.dry_run:
        required = [
            worktree / 'backend' / SCENARIOS[options.scenario]['file'],
            worktree / 'handoff_readiness_v2' / 'evidence' / 'load-failure' /
            'harness' / 'stack.py',
            worktree / 'handoff_readiness_v2' / 'evidence' /
            'post-close-disputes' / 'harness' / 'serve_app.py',
        ]
        missing = [str(path) for path in required if not path.exists()]
        print(json.dumps({'dry_run': True, 'missing': missing,
                          'frontend_build_exists': pathlib.Path(
                              config['frontend_build']).joinpath('index.html').exists()},
                         indent=2))
        return 1 if missing else 0

    build = pathlib.Path(config['frontend_build'])
    if not (build / 'index.html').exists():
        raise SystemExit(f'frontend build missing: {build}; run npm run build')
    runtime.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    revision = git_text(worktree, 'rev-parse', 'HEAD')
    product_matches = None
    if options.candidate_revision:
        product_matches = subprocess.run(
            ['git', 'diff', '--quiet', options.candidate_revision, '--',
             'backend', 'frontend',
             ':(exclude)backend/scripts/run-scenario-browser-postgres'],
            cwd=worktree).returncode == 0
        if not product_matches:
            raise SystemExit('backend/frontend differ from --candidate-revision')

    record = {
        'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'revision': revision,
        'candidate_revision': options.candidate_revision,
        'product_tree_matches_candidate': product_matches,
        'scenario_slug': options.scenario,
        'runtime': str(runtime),
        'checks': [], 'console': [], 'network': [],
    }
    stack = load_stack_module(worktree)
    from playwright.sync_api import sync_playwright

    with stack.disposable_stack(
            'scenario_' + options.scenario.replace('_2026', ''), seed=False
    ) as (backend_base, database, _):
        fixture = seed_database(stack, database, options.scenario)
        record['fixture'] = fixture
        with frontend_proxy(worktree, build, backend_base, runtime, stack) as base:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(args=[
                    '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
                try:
                    for language in LANGUAGES:
                        decision_checks(browser, base, fixture, language,
                                        record, worktree)

                    token = instructor_token(backend_base, fixture)
                    process_status, process_body, process_seconds = http_json(
                        'POST', backend_base +
                        f"/api/games/{fixture['game_id']}/round-control/process/",
                        token, {'force': True,
                                'reason': 'Disposable scenario browser check'})
                    record['process'] = {
                        'status': process_status,
                        'seconds': round(process_seconds, 3),
                        'processing_status': (process_body.get('round', {})
                                              .get('processing_status'))
                        if isinstance(process_body, dict) else None,
                    }
                    if process_status != 200:
                        raise RuntimeError(
                            f'round-one processing failed: {process_status} {process_body}')
                    for language in LANGUAGES:
                        results_checks(browser, base, fixture, language,
                                       record, worktree)

                    advance_status, advance_body, advance_seconds = http_json(
                        'POST', backend_base +
                        f"/api/games/{fixture['game_id']}/round-control/advance/",
                        token, {})
                    record['advance'] = {
                        'status': advance_status,
                        'seconds': round(advance_seconds, 3),
                        'next_round': advance_body.get('next_round')
                        if isinstance(advance_body, dict) else None,
                    }
                    if advance_status != 200 or record['advance']['next_round'] != 2:
                        raise RuntimeError(
                            f'round advance failed: {advance_status} {advance_body}')
                    for language in LANGUAGES:
                        transition_checks(browser, base, fixture, language,
                                          record, worktree)
                finally:
                    browser.close()

    failed = [check for check in record['checks'] if not check['passed']]
    record['summary'] = {
        'checks': len(record['checks']),
        'passed': len(record['checks']) - len(failed),
        'failed': len(failed),
        'console_errors': sum(1 for row in record['console']
                              if row['type'] == 'error'),
        'network_4xx_5xx': len(record['network']),
        'passed_gate': not failed,
    }
    output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n',
                      encoding='utf-8')
    print(json.dumps(record['summary'], indent=2))
    print(f'report: {output}')
    return 0 if not failed else 1


def main() -> int:
    return run(build_parser().parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
