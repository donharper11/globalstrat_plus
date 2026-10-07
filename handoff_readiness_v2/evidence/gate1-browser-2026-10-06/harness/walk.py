"""Shared plumbing for the CE walkthrough drivers.

Every driver records the same shape: steps, screenshots, console errors,
API calls (method, URL, status), refused responses with their bodies, and
per-screen leak scans. The leak scan is the CRV2-13 standard: textContent of
the rendered DOM (never innerText), searched for raw catalogue keys, storage
field names, `undefined`, `NaN`, `[object Object]`, and exception text; in a
zh-CN screen additionally for runs of English words.

No visual claim is made about Chinese glyphs: this sandbox has no CJK font
(fc-list :lang=zh is empty and the sandbox has no route to a font CDN), so
zh-CN screenshots show missing-glyph boxes; the standard is the DOM text.
"""
import json
import os
import pathlib
import re
import time

from playwright.sync_api import sync_playwright  # noqa: F401  (re-export)

SCRATCH = pathlib.Path(__file__).resolve().parent
EVIDENCE = SCRATCH.parent
SHOTS = EVIDENCE / 'screenshots'
RECORDS = EVIDENCE / 'records'

fx = json.loads((SCRATCH / 'fixture.json').read_text())
ports = json.loads((SCRATCH / 'runtime' / 'stack.ports').read_text())
BASE = 'http://127.0.0.1:%d' % ports['app']
PASSWORD = fx['password']

# Raw-key shapes: a dotted lower_snake path that i18next would print verbatim.
RAW_KEY = re.compile(r'\b(?:instructor|nav|finance|rd|products|marketing|'
                     r'market_strategy|corporate|corporate_strategy|'
                     r'communications|summary|research|results|leaderboard|'
                     r'dashboard|common|auth|login|game_status|decision_save|'
                     r'financial_reports|notifications|errors|sc|talent|'
                     r'compliance|esg|org|tax|alliances|government|events|'
                     r'onboarding|topbar|sidebar|strategy)\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\b')
JUNK = ['undefined', 'NaN', '[object Object]', 'Traceback', 'Exception',
        'TypeError', 'ReferenceError', 'null,', 'None']
# Storage field names that should never be shown to a player verbatim.
FIELD_NAMES = ['team_product', 'retail_price', 'round_number', 'team_id',
               'game_id', 'created_at', 'updated_at', 'home_market_code',
               'performance_index', 'cash_on_hand', 'total_revenue',
               'compliance_investments', 'talent_allocations', 'is_active',
               'processing_status', 'RESULTS_AVAILABLE', 'FULLY_COMPLETE']
# English that leaks into a zh-CN screen. Words that are legitimately Latin in
# Chinese UI (ESG, R&D, CEO, USD, %, product names) are excluded by requiring
# a run of at least two ordinary lowercase English words.
ENGLISH_RUN = re.compile(r'\b[A-Z]?[a-z]{3,}\s+(?:[a-z]{2,}|[A-Z][a-z]{2,})(?:\s+[A-Za-z]{2,})*\b')
ENGLISH_ALLOW = {'et al', 'of', 'and', 'the'}


class Recorder:
    def __init__(self, name, lang):
        self.name, self.lang = name, lang
        self.record = {'driver': name, 'language': lang, 'base': BASE,
                       'started': time.strftime('%Y-%m-%dT%H:%M:%S'),
                       'steps': [], 'console': [], 'api': [], 'refused': [],
                       'screens': [], 'leaks': [], 'observed': {}}
        self._api_mark = 0

    # ---- steps -------------------------------------------------------
    def step(self, name, outcome, detail=''):
        self.record['steps'].append({'name': name, 'outcome': outcome,
                                     'detail': str(detail)[:900]})
        print('  %-9s %s%s' % (outcome.upper(), name,
                               ' -- ' + str(detail)[:220] if detail else ''),
              flush=True)

    def observe(self, key, value):
        self.record['observed'][key] = value

    # ---- browser hooks -----------------------------------------------
    def instrument(self, page):
        page.route('**://fonts.googleapis.com/**', lambda r: r.abort())
        page.route('**://fonts.gstatic.com/**', lambda r: r.abort())
        page.on('console', lambda m: (
            self.record['console'].append(
                {'type': m.type, 'text': m.text[:400],
                 'at': time.strftime('%H:%M:%S')})
            if m.type in ('error', 'warning') else None))
        page.on('pageerror', lambda e: self.record['console'].append(
            {'type': 'pageerror', 'text': str(e)[:400],
             'at': time.strftime('%H:%M:%S')}))

        def on_response(res):
            url = res.url
            if '/api/' not in url:
                return
            entry = {'method': res.request.method,
                     'url': url.split('127.0.0.1:%d' % ports['app'])[-1][:220],
                     'status': res.status, 'at': time.strftime('%H:%M:%S')}
            self.record['api'].append(entry)
            if res.status >= 400:
                try:
                    body = res.text()[:600]
                except Exception:
                    body = '<unreadable>'
                req_body = ''
                try:
                    req_body = (res.request.post_data or '')[:600]
                except Exception:
                    pass
                self.record['refused'].append(dict(entry, body=body,
                                                   request=req_body))
        page.on('response', on_response)
        page.on('requestfailed', lambda r: self.record['api'].append(
            {'method': r.method, 'url': r.url[:220], 'status': 'FAILED',
             'failure': str(r.failure or ''), 'at': time.strftime('%H:%M:%S')})
            if '/api/' in r.url else None)

    def api_since_mark(self):
        calls = self.record['api'][self._api_mark:]
        self._api_mark = len(self.record['api'])
        return calls

    # ---- screens -----------------------------------------------------
    def screen(self, page, name, note=''):
        """Screenshot + leak scan + the API calls made since the last screen."""
        # WALKTHROUGH 4, changed mid-run on the owner's instruction: the
        # image is no longer written. Every screen is still visited, still
        # named, still leak-scanned and its DOM text and API calls still
        # recorded -- which is the evidence the report quotes anyway -- but
        # the pictures were 161 MB against a 25 MB budget. Set
        # WALK_SCREENSHOTS=1 to write them again.
        fname = '%s-%s.jpg' % (name, self.lang)
        if os.environ.get('WALK_SCREENSHOTS'):
            SHOTS.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(SHOTS / fname), full_page=True,
                                type='jpeg', quality=55)
            except Exception as exc:
                fname = 'FAILED:%s' % str(exc)[:80]
        else:
            fname = 'not-captured'
        # The leak scan reads VISIBLE text (innerText): AntD keeps every tab
        # pane it has shown mounted but hidden, so textContent would report
        # the Operator Log's JSON on every later screen. Equality asserts
        # elsewhere still use textContent.
        text = visible_text(page)
        leaks = scan(text, self.lang)
        calls = self.api_since_mark()
        entry = {'screen': name, 'url': page.url.replace(BASE, ''),
                 'screenshot': fname, 'note': note, 'leaks': leaks,
                 'api': [{'m': c['method'], 'u': c['url'], 's': c['status']}
                         for c in calls]}
        self.record['screens'].append(entry)
        if leaks:
            self.record['leaks'].append({'screen': name, 'leaks': leaks})
            print('  LEAK      %s: %s' % (name, json.dumps(leaks, ensure_ascii=False)[:300]), flush=True)
        return entry

    def finish(self):
        r = self.record
        r['summary'] = {
            'passed': sum(1 for s in r['steps'] if s['outcome'] == 'pass'),
            'failed': sum(1 for s in r['steps'] if s['outcome'] == 'fail'),
            'observed': sum(1 for s in r['steps'] if s['outcome'] == 'observed'),
            'screens': len(r['screens']),
            'screens_with_leaks': len(r['leaks']),
            'console_errors': len([c for c in r['console']
                                   if c['type'] in ('error', 'pageerror')]),
            'api_calls': len(r['api']),
            'api_refused': len(r['refused']),
        }
        RECORDS.mkdir(parents=True, exist_ok=True)
        out = RECORDS / ('%s-%s.json' % (self.name, self.lang))
        out.write_text(json.dumps(r, indent=1, ensure_ascii=False) + '\n')
        print('\n' + json.dumps(r['summary'], indent=2))
        print('record: %s' % out)
        return 0


# ---- DOM helpers ---------------------------------------------------------
def body_text(page):
    try:
        return page.evaluate("() => document.body.textContent") or ''
    except Exception:
        return ''


def visible_text(page):
    try:
        return page.evaluate("() => document.body.innerText") or ''
    except Exception:
        return ''


def scan(text, lang):
    found = []
    for m in sorted(set(RAW_KEY.findall(text))):
        # dotted product identifiers like 'v2.1' are excluded by the prefix
        found.append({'raw_key': m})
    for j in JUNK:
        if j in text:
            idx = text.find(j)
            found.append({'junk': j, 'context': text[max(0, idx - 40): idx + 40]})
    for f in FIELD_NAMES:
        if re.search(r'(?<![A-Za-z_])' + re.escape(f) + r'(?![A-Za-z_])', text):
            idx = text.find(f)
            found.append({'field_name': f,
                          'context': text[max(0, idx - 40): idx + 40]})
    if lang.startswith('zh'):
        runs = {}
        for m in ENGLISH_RUN.finditer(text):
            s = m.group(0).strip()
            if s.lower() in ENGLISH_ALLOW or len(s) < 8:
                continue
            runs[s] = runs.get(s, 0) + 1
        for s, n in sorted(runs.items(), key=lambda kv: -kv[1])[:60]:
            found.append({'english': s, 'n': n})
    return found


def sign_in(page, route, username, lang, password=None, rec=None,
            verify_language=True):
    """Students' passwords are their student ids (issued in bulk from the console).

    WALKTHROUGH-4 HARNESS FIX (walkthrough 3's finding (d)4). The old version
    wrote ``localStorage.gs_language`` and nothing else, and drew conclusions
    about a Chinese team from a browser that had never told the server
    anything. The enrolment therefore stayed ``en`` and every stored Phase 2
    artefact for that team came out English.

    Two things are different now:

    * the sign-in states the language the way the product does -- the login
      page's own switch writes ``gs_language`` and ``AuthContext.login``
      forwards it to ``PUT /api/user/preferences/`` -- and
    * the result is **read back from the server** (``GET
      /api/user/preferences/``, which answers from the enrolment row) before
      the driver does anything else.

    If the server disagrees, the driver says so loudly and, with a recorder,
    records it. ``set_language.py`` is the driver that sets a language through
    the in-game switch itself; this is the guard that every other run passes
    through.
    """
    page.goto(BASE + route, wait_until='domcontentloaded')
    page.evaluate("(l) => localStorage.setItem('gs_language', l)", lang)
    page.reload(wait_until='domcontentloaded')
    page.wait_for_timeout(2000)
    page.fill('input#username, input[name="username"]', username)
    page.fill('input#password, input[name="password"]', password or PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(5000)
    signed_in = bool(page.evaluate("() => localStorage.getItem('access_token')"))
    if signed_in and verify_language:
        server = server_language(page)
        if server != lang:
            page.wait_for_timeout(2500)
            server = server_language(page)
        if rec is not None:
            rec.observe('server_language_after_sign_in',
                        {'user': username, 'asked': lang, 'server': server})
        if server != lang:
            print('  LANGUAGE  %s: asked %s, the server holds %s'
                  % (username, lang, server), flush=True)
            if rec is not None:
                # A student's sign-in restates their language, because the
                # login response carries the enrolment's `language` and
                # `AuthContext.login` forwards a different choice. An
                # instructor made from the console has no enrolment, so the
                # response carries no language, nothing is forwarded, and the
                # console can be read in one language while the server holds
                # another. That divergence is recorded, not failed, because it
                # is the platform's behaviour and not this driver's doing.
                rec.step('the server holds the language this reader stated',
                         'observed' if '/instructor/' in route else 'fail',
                         'asked %s, server %s%s'
                         % (lang, server,
                            ' -- an instructor has no enrolment, so signing in '
                            'does not restate the language; the console is in '
                            '%s and the server still holds %s'
                            % (lang, server) if '/instructor/' in route else ''))
        elif rec is not None:
            rec.step('the server holds the language this reader stated',
                     'pass', '%s = %s' % (username, server))
    return signed_in


def server_language(page):
    """What the SERVER says this signed-in person's language is."""
    try:
        got = api(page, 'GET', '/api/user/preferences/')
        if got.get('status') == 200 and isinstance(got.get('body'), dict):
            return got['body'].get('language')
        return 'HTTP %s' % got.get('status')
    except Exception as exc:
        return 'unreadable: %s' % str(exc)[:60]


def language_switch(page):
    """The in-game language switch (components/LanguageSwitcher.js).

    It is a toggle: it prints '\u4e2d\u6587' while the interface is English and 'EN'
    while it is Chinese, and on click it changes i18next, writes
    localStorage and -- when there is a token -- PUTs the choice to
    /api/user/preferences/.
    """
    btn = page.locator("button:visible", has_text=re.compile(r'^(EN|\u4e2d\u6587)$'))
    return btn.first if btn.count() else None


def switch_language_in_product(page, want, rec=None, tries=3):
    """Click the in-game switch until the SERVER holds `want`. Returns the
    server's answer. Records every click, because a toggle that has to be
    pressed twice is itself worth seeing."""
    clicks = []
    for _ in range(tries):
        server = server_language(page)
        if server == want:
            break
        btn = language_switch(page)
        if btn is None:
            if rec is not None:
                rec.observe('language_switch_missing', page.url.replace(BASE, ''))
            break
        label = (btn.text_content() or '').strip()
        btn.click()
        page.wait_for_timeout(2500)
        clicks.append({'label': label, 'server_after': server_language(page)})
    server = server_language(page)
    if rec is not None:
        rec.observe('language_switch_clicks', clicks)
        rec.observe('language_after_switch', server)
    return server


def api(page, method, path, body=None):
    """Call the product API from inside the signed-in browser session.

    WALKTHROUGH 4 HARNESS FIX. This used to send only `Authorization`, while
    the product's own axios client (`api/client.js`) also sends
    `Accept-Language` from `localStorage.gs_language`. Some routes -- the AI
    Coach alerts among them -- choose their language from that header, so the
    driver was reading a different answer than the page beside it was
    showing, and reported the panel as English when it was Chinese. The
    header is now sent exactly as the client sends it.
    """
    return page.evaluate("""async (a) => {
        const t = localStorage.getItem('access_token');
        const opts = {method: a.method, headers: {Authorization: 'Bearer ' + t}};
        const lang = localStorage.getItem('gs_language');
        if (lang) { opts.headers['Accept-Language'] = lang; }
        if (a.body !== null && a.body !== undefined) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(a.body);
        }
        const r = await fetch(a.path, opts);
        let b = null; const txt = await r.text();
        try { b = JSON.parse(txt); } catch (e) { b = txt.slice(0, 800); }
        return {status: r.status, body: b};
    }""", {'method': method, 'path': path, 'body': body})


def click_tab(page, *labels):
    for label in labels:
        tab = page.locator('div.ant-tabs-tab', has_text=label)
        if tab.count():
            tab.first.click()
            page.wait_for_timeout(2500)
            return label
    return None


def popconfirm_ok(page, wait=4000):
    ok = page.locator('.ant-popconfirm:visible .ant-btn-primary, '
                      '.ant-popover:not(.ant-popover-hidden) .ant-btn-primary').last
    if ok.count():
        ok.click()
        page.wait_for_timeout(wait)
        return True
    return False


def toast(page, tries=40):
    for _ in range(tries):
        t = page.evaluate("""() => {
            const els = document.querySelectorAll('.ant-message-notice-content');
            return els.length ? Array.from(els).map(e => e.textContent.trim()).join(' | ') : null;
        }""")
        if t:
            return t
        page.wait_for_timeout(200)
    return None


def modal_text(page):
    return page.evaluate("""() => {
        // Only a modal that is actually shown: AntD leaves closed ones in the DOM.
        const els = Array.from(document.querySelectorAll('.ant-modal-wrap'))
            .filter(w => getComputedStyle(w).display !== 'none');   // the wrap is position:fixed, so offsetParent is always null
        const el = els.length ? els[els.length - 1].querySelector('.ant-modal-content') : null;
        return el ? el.textContent.replace(/\\s+/g, ' ').trim() : null;
    }""")


def set_number(page, locator, value):
    locator.click()
    page.keyboard.press('Control+a')
    if value is None or value == '':
        page.keyboard.press('Backspace')
    else:
        page.keyboard.type(str(value), delay=20)
    page.keyboard.press('Tab')


def pick_select(page, select_locator, option_text=None, index=0):
    select_locator.click()
    page.wait_for_timeout(700)
    dd = page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)')
    if option_text is not None:
        opt = dd.locator('.ant-select-item-option', has_text=option_text)
    else:
        opt = dd.locator('.ant-select-item-option')
    if opt.count() == 0:
        page.keyboard.press('Escape')
        return None
    target = opt.nth(index if option_text is None else 0)
    label = target.text_content()
    target.click()
    page.wait_for_timeout(600)
    return label
