"""Author the 34 label-map keys into both catalogues.

Anchors on the TWO-SPACE-indent block openers, which are top level. The
`"common"` and `"dashboard"` blocks that also appear later in each file sit at
four spaces, nested inside `"sc"` -- they are `sc.common` and `sc.dashboard`,
different key paths rather than shadowed duplicates, so nothing is discarded at
parse time and this anchor cannot hit the wrong block. Both facts are asserted
below rather than trusted: the anchor must be unique, and after writing, every
one of the 34 keys must be present in the PARSED catalogue.
"""
import json
import pathlib

LOC = pathlib.Path('/home/ubuntu/projects/globalstrat+/.claude/worktrees'
                   '/agent-ad31a78c64885fc47/frontend/globalstrat-frontend'
                   '/src/locales')

# StatusBadge labels. `active`/`in_progress`/`locked` already exist and are the
# style reference. `open`/`pending`/`processed` are round statuses, so they use
# the same participant vocabulary the backend's ROUND_STATUS_LABELS uses, to
# keep one wording for one concept across the two sides.
COMMON_EN = [
    ('developing', 'Developing'), ('retired', 'Retired'),
    ('distress', 'Distress'), ('budget_tier', 'Budget'),
    ('mainstream', 'Mainstream'), ('premium', 'Premium'),
    ('ultra_premium', 'Ultra Premium'), ('open', 'Open'),
    ('pending', 'Not yet open'), ('processed', 'Processed'),
    ('operational', 'Operational'),
]
COMMON_ZH = [
    ('developing', '开发中'), ('retired', '已停产'),
    ('distress', '财务困境'), ('budget_tier', '经济型'),
    ('mainstream', '主流型'), ('premium', '高端型'),
    ('ultra_premium', '超高端型'), ('open', '已开放'),
    ('pending', '尚未开放'), ('processed', '已结算'),
    ('operational', '运营中'),
]

LOGIN_EN = [('team_%d' % i, 'Team %d' % i) for i in range(1, 6)]
LOGIN_ZH = [('team_%d' % i, '团队 %d' % i) for i in range(1, 6)]

TOOLS_EN = [
    ('force_new_entrants', 'Threat of New Entrants'),
    ('force_supplier_power', 'Supplier Power'),
    ('force_buyer_power', 'Buyer Power'),
    ('force_substitutes', 'Threat of Substitutes'),
    ('force_rivalry', 'Competitive Rivalry'),
    ('pestle_political', 'Political'), ('pestle_economic', 'Economic'),
    ('pestle_social', 'Social'), ('pestle_technological', 'Technological'),
    ('pestle_legal', 'Legal'), ('pestle_environmental', 'Environmental'),
    ('entry_market_size', 'Market Size'), ('entry_growth', 'Growth Rate'),
    ('entry_cost', 'Entry Cost'), ('entry_tariff', 'Tariff Rate'),
    ('entry_regulatory', 'Regulatory Difficulty'),
    ('entry_competitive', 'Competitive Intensity'),
    ('entry_currency_risk', 'Currency Risk'),
]
TOOLS_ZH = [
    ('force_new_entrants', '新进入者威胁'),
    ('force_supplier_power', '供应商议价能力'),
    ('force_buyer_power', '买方议价能力'),
    ('force_substitutes', '替代品威胁'),
    ('force_rivalry', '现有竞争者竞争'),
    ('pestle_political', '政治'), ('pestle_economic', '经济'),
    ('pestle_social', '社会'), ('pestle_technological', '技术'),
    ('pestle_legal', '法律'), ('pestle_environmental', '环境'),
    ('entry_market_size', '市场规模'), ('entry_growth', '增长率'),
    ('entry_cost', '进入成本'), ('entry_tariff', '关税税率'),
    ('entry_regulatory', '监管难度'),
    ('entry_competitive', '竞争强度'),
    ('entry_currency_risk', '汇率风险'),
]

# Each anchor carries a LEADING NEWLINE, which makes it line-anchored.
# Without it, `  "common": {` is a substring of the nested `    "common": {`
# (four spaces) and matches BOTH -- the first run asserted 2 and refused,
# which would otherwise have written eleven keys into `sc.common`. Exactly the
# substring artifact that makes `common.save` appear to match
# `common.save_draft`.
PLAN = {
    'en.json': [('\n  "common": {', COMMON_EN), ('\n  "login": {', LOGIN_EN),
                ('\n  "strategy_tools": {', TOOLS_EN)],
    'zh-CN.json': [('\n  "common": {', COMMON_ZH), ('\n  "login": {', LOGIN_ZH),
                   ('\n  "strategy_tools": {', TOOLS_ZH)],
}


def main():
    for name, inserts in PLAN.items():
        path = LOC / name
        text = path.read_text(encoding='utf-8')
        for anchor, pairs in inserts:
            count = text.count(anchor)
            assert count == 1, (name, anchor, count)
            body = '\n'.join('    "%s": "%s",' % kv for kv in pairs)
            text = text.replace(anchor, anchor + '\n' + body)
        path.write_text(text, encoding='utf-8')
        print('patched %-11s +%d keys'
              % (name, sum(len(p) for _, p in inserts)))

    for name in ('en.json', 'zh-CN.json'):
        data = json.loads((LOC / name).read_text(encoding='utf-8'))
        missing = []
        for namespace, pairs in (('common', COMMON_EN), ('login', LOGIN_EN),
                                 ('strategy_tools', TOOLS_EN)):
            for key, _value in pairs:
                if key not in data.get(namespace, {}):
                    missing.append('%s.%s' % (namespace, key))
        print('%-11s valid JSON | all 34 present after parse: %s'
              % (name, 'YES' if not missing else 'NO %s' % missing))
        print('            sc.common untouched and still distinct: %d keys'
              % len(data.get('sc', {}).get('common', {})))


if __name__ == '__main__':
    main()
