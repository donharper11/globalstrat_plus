"""Set a language THROUGH THE PRODUCT, and prove from the server that it stuck.

    set_language.py instructor <lang>
    set_language.py student <team-index 1..8> <lang> [member-index|all]

Walkthrough 3's harness wrote `localStorage.gs_language` and nothing else, so
the Chinese team's enrolment stayed `en` for six rounds and every stored
Phase 2 artefact for that team came out English (its own finding (d)4). This
driver does what a person does: it signs in with the interface in English,
presses the **in-game language switch** in the top bar (the student) or the
console header (the instructor) -- `components/LanguageSwitcher.js`, which
calls `PUT /api/user/preferences/` when there is a token -- and then reads
the result back three ways:

  1. `GET /api/user/preferences/` from inside the signed-in browser,
  2. the `enrollment.language` column, straight out of the database,
  3. the switch's own label, which flips to `EN` once the interface is
     Chinese.

Nothing is asserted from localStorage.
"""
import json
import subprocess
import sys

from walk import (SCRATCH, Recorder, modal_text, server_language,
                  sign_in, switch_language_in_product, sync_playwright)

ROLE = sys.argv[1]
if ROLE == 'instructor':
    WANT = sys.argv[2]
    TEAM_IX = None
    MEMBER = None
else:
    TEAM_IX = int(sys.argv[2])
    WANT = sys.argv[3]
    MEMBER = sys.argv[4] if len(sys.argv) > 4 else 'all'

fx = json.loads((SCRATCH / 'fixture.json').read_text())


def _query(*args):
    out = subprocess.run([sys.executable, str(SCRATCH / 'dbq.py')] + list(args),
                         capture_output=True, text=True, cwd=str(SCRATCH))
    rows = [l.split('\t') for l in out.stdout.strip().splitlines()]
    if not rows:
        return []
    head, body = rows[0], rows[1:]
    return [dict(zip(head, r)) for r in body]


def db_languages():
    """Both stores the platform keeps a language in.

    A student's language lives on the enrolment row; an instructor created
    from the console has no enrolment, so the W-CE2-08 repair writes the
    `user_language_preference` row for everybody. Reading only the enrolment
    reports an instructor as having no language at all.
    """
    rows = _query('enrollments')
    prefs = _query('sql', 'select u.username, p.language from '
                          'user_language_preference p join users u '
                          'on u.user_id = p.user_id')
    by_user = {r['username']: r for r in rows}
    for p in prefs:
        by_user.setdefault(p['username'], {'username': p['username']})
        by_user[p['username']]['preference_language'] = p['language']
        by_user[p['username']].setdefault('language', p['language'])
    return list(by_user.values())


def one(page, R, route, username, password, label):
    """Sign this person in in English, then press the switch."""
    ok = sign_in(page, route, username, 'en', password=password,
                 rec=None, verify_language=False)
    R.step('%s signs in with the interface in English' % label,
           'pass' if ok else 'fail', username)
    if not ok:
        return None
    page.wait_for_timeout(3000)
    for _ in range(6):                      # dismiss the post-login modal
        if not modal_text(page):
            break
        b = page.locator('.ant-modal-content button.ant-btn-primary')
        if b.count():
            b.last.click()
            page.wait_for_timeout(1200)
        else:
            page.keyboard.press('Escape')
            page.wait_for_timeout(600)
    before = server_language(page)
    R.step('before the switch, the server holds a language for %s' % username,
           'observed', before)
    R.screen(page, 'lang-%s-before' % username)
    got = switch_language_in_product(page, WANT, rec=R)
    R.screen(page, 'lang-%s-after' % username)
    R.step('the in-game switch set %s to %s on the SERVER' % (username, WANT),
           'pass' if got == WANT else 'fail',
           'before=%s after=%s clicks=%s'
           % (before, got,
              json.dumps(R.record['observed'].get('language_switch_clicks'))))
    label_now = None
    btn = page.locator('button:visible', has_text='EN')
    if btn.count():
        label_now = (btn.first.text_content() or '').strip()
    clicked = bool(R.record['observed'].get('language_switch_clicks'))
    R.step('the switch now offers the other language',
           'pass' if (not clicked) or (not WANT.startswith('zh'))
           or label_now == 'EN' else 'fail',
           'label=%r clicked=%s (the interface follows i18next, which the switch '
           'only changes when it is pressed; the server already held %s here)'
           % (label_now, clicked, WANT))
    page.evaluate('() => { localStorage.clear(); }')
    return got


def main():
    R = Recorder('set-language-%s'
                 % (ROLE if TEAM_IX is None else 't%d' % TEAM_IX), WANT)
    R.observe('want', WANT)
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        if ROLE == 'instructor':
            results[fx['instructor']] = one(
                page, R, '/instructor/login', fx['instructor'], fx['password'],
                'the instructor')
        else:
            G = json.loads((SCRATCH / 'game.json').read_text())
            team = G['teams'][TEAM_IX - 1]
            members = [r for r in G['roster']
                       if r.get('team_id') == team['team_id']]
            if MEMBER != 'all':
                members = [members[int(MEMBER)]]
            R.observe('team', team.get('team_name'))
            for m in members:
                sid = m.get('student_id') or m['username']
                results[m['username']] = one(page, R, '/login', m['username'],
                                             sid, m['username'])
        browser.close()
    R.observe('server_says', results)
    rows = db_languages()
    R.observe('enrollment_rows', rows)
    for user, got in results.items():
        row = next((r for r in rows if r.get('username') == user), None)
        stored = (row or {}).get('language')
        R.step('the stored language row for %s holds %s' % (user, WANT),
               'pass' if stored == WANT else 'fail',
               'stored=%r (row=%s)' % (stored, json.dumps(row, ensure_ascii=False)[:200]))
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
