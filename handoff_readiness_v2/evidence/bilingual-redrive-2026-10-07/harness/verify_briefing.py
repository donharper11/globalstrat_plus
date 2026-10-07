"""W-CE3-11: the Strategic Briefing a player meets after signing in.

    verify_briefing.py <lang> <team-index> <member-index>

The modal is shown once per person per round, so this driver takes the member
to sign in as: a member who has not yet opened the round gets the briefing,
one who has does not. It records the whole modal, checks that a Chinese
team's briefing is Chinese, and checks that no Markdown is printed raw --
`**...**` on a screen is the mark of prose written for a renderer that is not
there.
"""
import json
import pathlib
import re
import sys

from walk import (Recorder, modal_text, sign_in, sync_playwright)

SCRATCH = pathlib.Path(__file__).resolve().parent
LANG = sys.argv[1]
TEAM_IX = int(sys.argv[2])
MEMBER_IX = int(sys.argv[3]) if len(sys.argv) > 3 else 0
G = json.loads((SCRATCH / 'game.json').read_text())
team = G['teams'][TEAM_IX - 1]
members = [r for r in G['roster'] if r.get('team_id') == team['team_id']]
STUDENT = members[min(MEMBER_IX, len(members) - 1)]
R = Recorder('verify-briefing-t%d-m%d' % (TEAM_IX, MEMBER_IX), LANG)
R.observe('team', team.get('team_name'))
R.observe('student', STUDENT['username'])
HAN = re.compile(r'[一-鿿]')
MARKDOWN = re.compile(r'\*\*[^*]+\*\*|^#{1,6}\s|\[[^\]]+\]\([^)]+\)', re.M)
EN_SENTENCE = re.compile(r'\b[A-Za-z][a-z]{2,}(?:\s+[a-z]{2,}){1,}\b')
# The briefing modal's own title, so an onboarding page that happens to
# mention the briefing is not mistaken for it.
BRIEFING_TITLE = re.compile(r'Round\s*\d+\s*Strategic Briefing|第\s*\d+\s*回合战略简报')


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        R.instrument(page)
        page.on('dialog', lambda d: d.accept())
        ok = sign_in(page, '/login', STUDENT['username'], LANG,
                     password=STUDENT.get('student_id'), rec=R)
        R.step('%s signs in' % STUDENT['username'], 'pass' if ok else 'fail')
        if not ok:
            browser.close()
            return R.finish()
        page.wait_for_timeout(4000)
        # A member signing in for the first time meets the onboarding modal
        # before the briefing, so every modal in the queue is collected and
        # the briefing is picked out of them.
        seen = []
        text = ''
        for i in range(14):
            current = modal_text(page) or ''
            if not current:
                break
            seen.append(current)
            R.screen(page, 'v4-briefing-t%d-m%d-modal%d' % (TEAM_IX, MEMBER_IX, i))
            if BRIEFING_TITLE.search(current):
                text = current
                break
            b = page.locator('.ant-modal-wrap:visible .ant-modal-content button')
            if b.count():
                b.last.click()
                page.wait_for_timeout(1500)
            else:
                page.keyboard.press('Escape')
                page.wait_for_timeout(1000)
        R.observe('modals_in_order', [s[:400] for s in seen])
        R.observe('briefing_modal', text[:3000])
        if not text:
            R.step('the Strategic Briefing modal is offered', 'observed',
                   'no modal for this person in this round (it is shown once)')
            browser.close()
            return R.finish()
        han = len(HAN.findall(text))
        english = sorted({m.group(0).strip() for m in EN_SENTENCE.finditer(text)
                          if len(m.group(0).strip()) >= 9})
        if LANG.startswith('zh'):
            R.step('W-CE3-11 the Strategic Briefing is Chinese for a Chinese '
                   'team', 'pass' if han > 20 and not english else 'fail',
                   '%d Chinese characters; English left on the screen: %s'
                   % (han, json.dumps(english, ensure_ascii=False)[:600]))
        else:
            R.step('W-CE3-11 the Strategic Briefing is English for an English '
                   'team', 'pass' if han == 0 else 'fail',
                   '%d Chinese characters on an English screen' % han)
        raw = MARKDOWN.findall(text)
        R.observe('raw_markdown', raw)
        R.step('no Markdown is printed raw in the briefing',
               'pass' if not raw else 'fail',
               'printed verbatim: %s' % json.dumps(raw[:6], ensure_ascii=False))
        browser.close()
    return R.finish()


if __name__ == '__main__':
    raise SystemExit(main())
