"""
CC-31H: News Ticker Endpoint.

Lightweight endpoint that aggregates ticker items from existing data sources:
currency movements, events, market conditions, deadline alerts, AI competitor
moves, and investor sentiment.
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team, Round
from core.models.scenario import (
    MarketDefinition, MarketConditionByRound,
    AICompetitorDefinition, AICompetitorBehavior,
)
from core.models.results import EventInstance
from core.models.decisions import DecisionSubmission
from core.utils.localization import get_localized_field, get_team_language


def _dec(v):
    if v is None:
        return 0
    return float(v)


_TICKER_TEMPLATES = {
    'en': {
        'fx_strengthen': '{currency} strengthened {pct:.1f}% against {home} — {market} revenue converts to more {home}',
        'fx_weaken': '{currency} weakened {pct:.1f}% against {home} — {market} revenue converts to fewer {home}',
        'fx_volatile': ' (unusual volatility)',
        'growth_up': '{market} growth accelerating — demand rising',
        'growth_down': '{market} growth slowing — demand cooling',
        'tariff_up': '{market} tariffs increased — import costs rising',
        'tariff_down': '{market} tariffs reduced — trade barriers easing',
        'deadline': 'Round {round} deadline: {days} {day_word} remaining — {submitted} of {total} teams submitted',
        'day': 'day',
        'days': 'days',
        'ai_aggressive': '{name} expanding aggressively — competition intensifying',
        'ai_defensive': '{name} consolidating position — fortifying existing markets',
        'ai_niche': '{name} targeting niche segments — specialized competition growing',
        'ai_other': '{name} adjusting strategy — adapting to market conditions',
        'investor_buy': 'Institutional investors increasing positions — sentiment bullish',
        'investor_sell': 'Institutional investors reducing positions — sentiment cautious',
        'alliance_strained': '{partner} relationship strained in {market} — satisfaction {pct}%',
        'alliance_renegotiating': '{partner} demanding renegotiation in {market} — benefits frozen at 50%',
        'alliance_dissolved': '{partner} terminated partnership in {market} — all benefits suspended',
        'gov_warning': 'Government warning in {market} — improve compliance or face restrictions',
        'gov_restricted': 'Operating restrictions active in {market} — sales capped',
        'gov_welcomed': 'Government welcomes your investment in {market}',
    },
    'zh-CN': {
        'fx_strengthen': '{currency} 兑 {home} 升值 {pct:.1f}% — {market}收入兑换增加',
        'fx_weaken': '{currency} 兑 {home} 贬值 {pct:.1f}% — {market}收入兑换减少',
        'fx_volatile': '（异常波动）',
        'growth_up': '{market}增长加速 — 需求上升',
        'growth_down': '{market}增长放缓 — 需求降温',
        'tariff_up': '{market}关税上调 — 进口成本上升',
        'tariff_down': '{market}关税下调 — 贸易壁垒减少',
        'deadline': '第{round}回合截止日期：剩余{days}{day_word} — {submitted}/{total}队伍已提交',
        'day': '天',
        'days': '天',
        'ai_aggressive': '{name}积极扩张 — 竞争加剧',
        'ai_defensive': '{name}巩固地位 — 加强现有市场',
        'ai_niche': '{name}瞄准细分市场 — 专业化竞争加剧',
        'ai_other': '{name}调整战略 — 适应市场条件',
        'investor_buy': '机构投资者增持 — 市场看涨',
        'investor_sell': '机构投资者减持 — 市场谨慎',
        'alliance_strained': '{partner}在{market}的关系紧张 — 满意度{pct}%',
        'alliance_renegotiating': '{partner}在{market}要求重新谈判 — 收益冻结在50%',
        'alliance_dissolved': '{partner}在{market}终止合作 — 所有收益暂停',
        'gov_warning': '{market}政府警告 — 改善合规性否则面临限制',
        'gov_restricted': '{market}运营限制生效 — 销售受限',
        'gov_welcomed': '政府欢迎您在{market}的投资',
    },
}


def _t(language, key, **kwargs):
    """Look up a ticker template by language and format with kwargs."""
    templates = _TICKER_TEMPLATES.get(language, _TICKER_TEMPLATES['en'])
    template = templates.get(key, _TICKER_TEMPLATES['en'].get(key, key))
    return template.format(**kwargs)


class TickerView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/ticker/"""

    def get(self, request, game_id, team_id):
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)
        current_round = game.current_round

        if current_round < 1:
            return Response({'round': current_round, 'items': []})

        items = []
        home_currency = team.home_market.currency_code if team.home_market else 'USD'
        from core.utils.localization import _lang_from_header
        language = _lang_from_header(request) or get_team_language(team)

        # ----- 1. CURRENCY MOVEMENTS -----
        scenario = game.scenario
        markets = MarketDefinition.objects.filter(scenario=scenario)

        for mkt in markets:
            # Skip home currency
            if team.home_market and mkt.id == team.home_market_id:
                continue

            cond = MarketConditionByRound.objects.filter(
                market=mkt, round_number=current_round,
            ).first()
            prev_cond = MarketConditionByRound.objects.filter(
                market=mkt, round_number=current_round - 1,
            ).first()

            fx_rate = float(mkt.exchange_rate_base) * (1 + float(cond.exchange_rate_modifier)) if cond else float(mkt.exchange_rate_base)
            prev_fx = float(mkt.exchange_rate_base) * (1 + float(prev_cond.exchange_rate_modifier)) if prev_cond else float(mkt.exchange_rate_base)

            if prev_fx <= 0:
                continue

            pct_change = ((fx_rate - prev_fx) / prev_fx) * 100

            if abs(pct_change) < 1.0:
                continue

            mkt_name = get_localized_field(mkt, 'name', language)
            if pct_change > 0:
                priority = 'low' if pct_change < 3 else 'medium'
                text = _t(language, 'fx_strengthen', currency=mkt.currency_code, pct=abs(pct_change), home=home_currency, market=mkt_name)
            else:
                priority = 'medium' if abs(pct_change) < 5 else 'high'
                text = _t(language, 'fx_weaken', currency=mkt.currency_code, pct=abs(pct_change), home=home_currency, market=mkt_name)

            if abs(pct_change) > 20:
                text += _t(language, 'fx_volatile')
                priority = 'high'

            items.append({
                'type': 'currency',
                'priority': priority,
                'icon': '\U0001f4b1',
                'text': text,
                'market': mkt.code,
            })

        # ----- 2. EVENTS THAT FIRED THIS ROUND -----
        events_qs = EventInstance.objects.filter(
            game=game, round_number=current_round,
        ).select_related('event_template', 'target_market')

        for ev in events_qs:
            tmpl = ev.event_template
            category_upper = (tmpl.category or '').upper()

            if category_upper in ('GEOPOLITICAL', 'SANCTIONS'):
                priority = 'high'
                icon = '\u26a1'
            elif tmpl.severity in ('high', 'critical'):
                priority = 'high'
                icon = '\u26a1'
            else:
                priority = 'medium'
                icon = '\U0001f4cb'

            headline = ev.narrative[:80] if ev.narrative else get_localized_field(tmpl, 'description_template', language)[:80]
            text = f'{get_localized_field(tmpl, "name", language)} \u2014 {headline}'

            items.append({
                'type': 'event',
                'priority': priority,
                'icon': icon,
                'text': text,
                'market': ev.target_market.code if ev.target_market else None,
            })

        # ----- 3. MARKET CONDITION CHANGES -----
        for mkt in markets:
            cond = MarketConditionByRound.objects.filter(
                market=mkt, round_number=current_round,
            ).first()
            prev_cond = MarketConditionByRound.objects.filter(
                market=mkt, round_number=current_round - 1,
            ).first()

            if not cond or not prev_cond:
                continue

            cur_growth = float(mkt.base_growth_rate) + float(cond.growth_rate_modifier)
            prev_growth = float(mkt.base_growth_rate) + float(prev_cond.growth_rate_modifier)
            growth_delta = cur_growth - prev_growth

            mkt_disp_name = get_localized_field(mkt, 'name', language)
            if abs(growth_delta) >= 0.01:
                if growth_delta > 0:
                    text = _t(language, 'growth_up', market=mkt_disp_name)
                    icon = '\U0001f4c8'
                else:
                    text = _t(language, 'growth_down', market=mkt_disp_name)
                    icon = '\U0001f4c9'
                items.append({
                    'type': 'market',
                    'priority': 'medium',
                    'icon': icon,
                    'text': text,
                    'market': mkt.code,
                })

            cur_tariff = float(mkt.tariff_rate) + float(cond.tariff_rate_modifier)
            prev_tariff = float(mkt.tariff_rate) + float(prev_cond.tariff_rate_modifier)
            tariff_delta = cur_tariff - prev_tariff

            if abs(tariff_delta) >= 0.01:
                if tariff_delta > 0:
                    text = _t(language, 'tariff_up', market=mkt_disp_name)
                    icon = '\U0001f4c8'
                else:
                    text = _t(language, 'tariff_down', market=mkt_disp_name)
                    icon = '\U0001f4c9'
                items.append({
                    'type': 'market',
                    'priority': 'medium',
                    'icon': icon,
                    'text': text,
                    'market': mkt.code,
                })

        # ----- 4. GAME ALERTS (deadline / submissions) -----
        current_rnd = Round.objects.filter(
            game=game, round_number=current_round,
        ).first()

        if current_rnd and current_rnd.status == 'open' and current_rnd.deadline:
            days_remaining = (current_rnd.deadline - timezone.now()).days
            if days_remaining <= 3:
                submitted = DecisionSubmission.objects.filter(
                    round=current_rnd, status='locked',
                ).count()
                total = game.teams.count()
                day_word = _t(language, 'day') if days_remaining == 1 else _t(language, 'days')
                items.append({
                    'type': 'alert',
                    'priority': 'high' if days_remaining <= 1 else 'medium',
                    'icon': '\u23f0',
                    'text': _t(language, 'deadline', round=current_round, days=days_remaining, day_word=day_word, submitted=submitted, total=total),
                    'market': None,
                })

        # ----- 5. COMPETITIVE INTELLIGENCE (AI competitor moves) -----
        ai_comps = AICompetitorDefinition.objects.filter(
            scenario=scenario,
        ).prefetch_related('behavior')

        for ai in ai_comps:
            behavior = AICompetitorBehavior.objects.filter(ai_competitor=ai).first()
            if not behavior:
                continue

            ai_name = get_localized_field(ai, 'name', language)
            strategy_key = {
                'aggressive': 'ai_aggressive',
                'defensive': 'ai_defensive',
                'niche': 'ai_niche',
            }.get(behavior.strategy_type, 'ai_other')
            headline = _t(language, strategy_key, name=ai_name)

            items.append({
                'type': 'competitive',
                'priority': 'medium',
                'icon': '\U0001f3e2',
                'text': headline,
                'market': None,
            })

        # ----- 6. INVESTOR SENTIMENT -----
        try:
            from core.models.cc26_models import AIInvestorHolding
            holdings = AIInvestorHolding.objects.filter(
                game=game, team=team, round_number=current_round,
            ).select_related('fund')

            if holdings.exists():
                buy_count = holdings.filter(action='buy').count()
                sell_count = holdings.filter(action='sell').count()

                if buy_count > sell_count:
                    items.append({
                        'type': 'investor',
                        'priority': 'medium',
                        'icon': '\U0001f4ca',
                        'text': _t(language, 'investor_buy'),
                        'market': None,
                    })
                elif sell_count > buy_count:
                    items.append({
                        'type': 'investor',
                        'priority': 'medium',
                        'icon': '\U0001f4ca',
                        'text': _t(language, 'investor_sell'),
                        'market': None,
                    })
        except ImportError:
            pass

        # ----- 7. ALLIANCE PARTNER EVENTS (CC-32D) -----
        try:
            from core.models.cc32d_models import TeamAllianceState
            alliances = TeamAllianceState.objects.filter(
                game=game, team=team,
            ).exclude(status='HEALTHY').select_related('partner_profile', 'market')

            for a in alliances:
                p = a.partner_profile
                p_name = get_localized_field(p, 'name', language)
                a_mkt_name = get_localized_field(a.market, 'name', language)
                if a.status == 'STRAINED':
                    items.append({
                        'type': 'alliance',
                        'priority': 'medium',
                        'icon': '\u26a0\ufe0f',
                        'text': _t(language, 'alliance_strained', partner=p_name, market=a_mkt_name, pct=int(float(a.satisfaction)*100)),
                        'market': a.market.code,
                    })
                elif a.status == 'RENEGOTIATING':
                    items.append({
                        'type': 'alliance',
                        'priority': 'high',
                        'icon': '\u26a0\ufe0f',
                        'text': _t(language, 'alliance_renegotiating', partner=p_name, market=a_mkt_name),
                        'market': a.market.code,
                    })
                elif a.status in ('DISSOLVING', 'DISSOLVED'):
                    items.append({
                        'type': 'alliance',
                        'priority': 'high',
                        'icon': '\u274c',
                        'text': _t(language, 'alliance_dissolved', partner=p_name, market=a_mkt_name),
                        'market': a.market.code,
                    })
        except Exception:
            pass

        # Section 8: Government actions (CC-32F)
        try:
            from core.models.cc32f_models import GovernmentSatisfaction, GovernmentAction
            # Government satisfaction alerts
            for gs in GovernmentSatisfaction.objects.filter(
                game=game, team=team,
            ).exclude(status='NEUTRAL').select_related('market'):
                gs_mkt_name = get_localized_field(gs.market, 'name', language)
                if gs.status == 'WARNING':
                    items.append({
                        'type': 'government',
                        'priority': 'high',
                        'icon': '\u26a0\ufe0f',
                        'text': _t(language, 'gov_warning', market=gs_mkt_name),
                        'market': gs.market.code,
                    })
                elif gs.status == 'RESTRICTED':
                    items.append({
                        'type': 'government',
                        'priority': 'high',
                        'icon': '\U0001f6ab',
                        'text': _t(language, 'gov_restricted', market=gs_mkt_name),
                        'market': gs.market.code,
                    })
                elif gs.status == 'WELCOMED':
                    items.append({
                        'type': 'government',
                        'priority': 'low',
                        'icon': '\U0001f3db\ufe0f',
                        'text': _t(language, 'gov_welcomed', market=gs_mkt_name),
                        'market': gs.market.code,
                    })
            # Recent government actions (market-wide, this round)
            for ga in GovernmentAction.objects.filter(
                game=game, round__round_number=current_round,
                target_team__isnull=True,
            ).select_related('market')[:3]:
                items.append({
                    'type': 'government',
                    'priority': 'medium',
                    'icon': '\U0001f4dc',
                    'text': ga.narrative or ga.action_type.replace('_', ' '),
                    'market': ga.market.code,
                })
        except Exception:
            pass

        # Sort: high first, then medium, then low
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        items.sort(key=lambda x: priority_order.get(x['priority'], 1))

        # Cap at 12 items to avoid scroll overload
        items = items[:12]

        return Response({
            'round': current_round,
            'items': items,
        })
