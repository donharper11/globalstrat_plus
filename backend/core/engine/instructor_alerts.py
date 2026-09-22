"""
Instructor AI Assistant — Alert Generation Engine.
Generates coaching alerts after round processing and on decision lock.
"""
from decimal import Decimal

from core.models.cc21_models import InstructorAlert
from core.models.core import Game, Team
from core.models.results_financials import (
    RoundResultFinancials, RoundResultPerformanceIndex,
    RoundResultCoherence, RoundResultProductMarket,
)
from core.models.decisions import (
    DecisionSubmission, DecisionRDInvestment, DecisionMarketing,
    DecisionMarketEntry, DecisionBudgetAllocation,
)
from core.models.team_state import TeamMarketPresence
from core.engine.llm_runner import build_language_instruction
from core.utils.localization import get_instructor_language, get_localized_field

# Defensive imports for models that may not exist yet (CC-20 parallel)
try:
    from core.models.team_state import TeamAcquisition
except ImportError:
    TeamAcquisition = None

try:
    from core.models.decisions import DecisionESG
except ImportError:
    DecisionESG = None


def _create_alert(game, team, round_number, alert_type, severity, title, detail, teaching_note=''):
    return InstructorAlert(
        game=game, team=team, round_number=round_number,
        alert_type=alert_type, severity=severity,
        title=title, detail=detail, teaching_note=teaching_note,
    )


# The alert templates, in both languages (W-CE-16/17, 2026-09-22). The AI
# Coach tab showed these in English on a Chinese console: they were
# f-strings. Each alert is (title, detail, teaching note), rendered in the
# instructor's language -- the same the model path uses for teaching notes.
# English is byte-identical to what shipped.
_ALERT_TEXT = {
    'en': {
        'cash_crisis': (
            '{team} has only ${cash:,.0f} cash remaining',
            'At current burn rate, they may run out of cash within 1-2 rounds. '
            'Debt: ${debt:,.0f}, Net Income: ${net_income:,.0f}. '
            'Watch for distress spiral — teams in financial trouble often make desperate decisions.',
            'This is a teaching moment about cash management and financial planning. '
            'Ask the team: "What was your cash forecast? Did you account for all costs?"'),
        'leverage': (
            '{team} debt-to-equity ratio at {ratio:.2f}',
            'Total debt: ${debt:,.0f}, Equity: ${equity:,.0f}. '
            'Interest expense: ${interest:,.0f}/round. '
            'This level of leverage limits future borrowing capacity and increases risk.',
            'Discuss the trade-offs of debt vs equity financing. '
            'Reference: Modigliani-Miller theorem and real-world capital structure decisions.'),
        'revenue_decline': (
            '{team} revenue declined {pct:.1f}% this round',
            'Revenue: ${revenue:,.0f} (was ${previous:,.0f}). '
            'Check if this is due to pricing, production, market share loss, or currency effects.',
            'Revenue decline in a growing market suggests competitive pressure. '
            'Ask: "What changed in your competitive position? Did competitors improve or did you stand still?"'),
        'no_rd': (
            '{team} has not invested in R&D for {rounds} consecutive rounds',
            'Their technology capability is stagnating while competitors may be advancing. '
            'This will erode fit scores with technology-sensitive segments.',
            'Classic short-term thinking trap. Teams sacrifice long-term capability for short-term profits. '
            "Reference: The Innovator's Dilemma — established firms underinvest in innovation."),
        'single_market': (
            '{team} still operates in only {count} market (Round {round})',
            'Remaining in one market limits revenue growth potential '
            'and increases concentration risk.',
            'Discuss market entry timing. Reference: Uppsala model of internationalization — '
            'firms often delay foreign market entry due to uncertainty, but delay has costs.'),
        'coherence_high': (
            '{team} achieved a coherence score of {score:.0f}/100',
            'Their strategy is internally consistent. Pricing aligns with positioning, '
            'distribution matches segments, entry modes match risk profiles.',
            'Highlight this in debrief as an example of strategic alignment. '
            'What specific choices created this coherence?'),
        'index_drop': (
            '{team} performance index dropped {drop:.1f} points',
            'Index: {index:.2f} (was {previous:.2f}). Satisfaction score: {satisfaction:.3f}.',
            'A sharp index drop indicates multiple stakeholder groups are dissatisfied simultaneously. '
            'This team may be spreading too thin or making contradictory decisions.'),
        'acquisition': (
            '{team} acquired {target}',
            'Cost: ${cost:,.0f}. Integration will take {rounds} rounds.',
            'Good opportunity to discuss M&A strategy: was this acquisition value-creating? '
            'What synergies does the team expect? How will integration costs affect near-term performance?'),
        'market_entry': (
            '{team} entered {market} via {mode}',
            'Investment: ${investment:,.0f}. This market has {growth:.0f}% growth rate '
            'and {tariff:.0f}% tariff rate.',
            "Discuss entry mode choice. Was this the right fit for the market's risk profile? "
            "Reference: Dunning's OLI framework for entry mode selection."),
        'overproduction': (
            '{team} producing 2x+ last round sales for {product} in {market}',
            'Production: {volume:,} units. Last round sold: {sold:,}. '
            'This may result in significant unsold inventory.',
            ''),
        'unknown_mode': 'unknown mode',
    },
    'zh-CN': {
        'cash_crisis': (
            '{team} 的现金仅剩 ${cash:,.0f}',
            '按当前消耗速度，该团队可能在 1-2 个回合内耗尽现金。'
            '负债：${debt:,.0f}，净利润：${net_income:,.0f}。'
            '警惕困境螺旋——陷入财务困境的团队常会做出孤注一掷的决策。',
            '这是讲解现金管理与财务规划的教学时机。'
            '可以问该团队："你们的现金预测是多少？是否计入了所有成本？"'),
        'leverage': (
            '{team} 的资产负债率达到 {ratio:.2f}',
            '总负债：${debt:,.0f}，权益：${equity:,.0f}。'
            '利息支出：每回合 ${interest:,.0f}。'
            '这一杠杆水平会限制未来的借款能力并增加风险。',
            '讨论债务融资与股权融资的权衡。'
            '参考：莫迪利安尼-米勒定理及现实中的资本结构决策。'),
        'revenue_decline': (
            '{team} 本回合收入下降 {pct:.1f}%',
            '收入：${revenue:,.0f}（上回合为 ${previous:,.0f}）。'
            '请检查原因是定价、生产、市场份额流失还是汇率影响。',
            '在增长的市场中收入下降，说明存在竞争压力。'
            '可以问："你们的竞争地位发生了什么变化？是竞争对手进步了，还是你们停滞不前？"'),
        'no_rd': (
            '{team} 已连续 {rounds} 个回合未投入研发',
            '其技术能力停滞不前，而竞争对手可能正在进步。'
            '这将削弱其在技术敏感型细分市场中的契合度得分。',
            '典型的短视思维陷阱：团队为了短期利润牺牲长期能力。'
            '参考：《创新者的窘境》——成熟企业在创新上投入不足。'),
        'single_market': (
            '{team} 仍只在 {count} 个市场运营（第 {round} 回合）',
            '停留在单一市场会限制收入增长潜力，并增加集中度风险。',
            '讨论市场进入时机。参考：乌普萨拉国际化模型——'
            '企业常因不确定性而推迟进入海外市场，但推迟也有代价。'),
        'coherence_high': (
            '{team} 的战略一致性得分达到 {score:.0f}/100',
            '其战略内部一致：定价与定位相符，分销与细分市场匹配，进入模式与风险特征相称。',
            '在复盘中将此作为战略协同的范例加以强调。'
            '是哪些具体选择造就了这种一致性？'),
        'index_drop': (
            '{team} 的绩效指数下降了 {drop:.1f} 点',
            '指数：{index:.2f}（此前为 {previous:.2f}）。满意度得分：{satisfaction:.3f}。',
            '指数骤降表明多个利益相关者群体同时感到不满。'
            '该团队可能摊子铺得太开，或做出了相互矛盾的决策。'),
        'acquisition': (
            '{team} 收购了 {target}',
            '成本：${cost:,.0f}。整合需要 {rounds} 个回合。',
            '这是讨论并购战略的好机会：此次收购是否创造了价值？'
            '团队预期哪些协同效应？整合成本将如何影响近期业绩？'),
        'market_entry': (
            '{team} 通过{mode}进入了{market}',
            '投资：${investment:,.0f}。该市场增长率为 {growth:.0f}%，关税率为 {tariff:.0f}%。',
            '讨论进入模式的选择：它是否与该市场的风险特征相匹配？'
            '参考：邓宁的 OLI 框架（进入模式选择）。'),
        'overproduction': (
            '{team} 在{market}的 {product} 产量超过上回合销量的两倍',
            '生产：{volume:,} 台。上回合销量：{sold:,} 台。'
            '这可能导致大量库存积压。',
            ''),
        'unknown_mode': '未知模式',
    },
}


def _alert_text(language, key, **values):
    """(title, detail, teaching_note) for `key`, rendered with `values`."""
    table = _ALERT_TEXT.get(language, _ALERT_TEXT['en'])
    entry = table.get(key, _ALERT_TEXT['en'][key])
    if isinstance(entry, str):
        return entry.format(**values)
    return tuple(part.format(**values) for part in entry)


def _count_rounds_without_rd(team, current_round):
    """Count consecutive rounds (backward from current) with no R&D investment."""
    count = 0
    for rnd_num in range(current_round, -1, -1):
        has_rd = DecisionRDInvestment.objects.filter(
            submission__team=team,
            submission__round__round_number=rnd_num,
            amount__gt=0,
        ).exists()
        if has_rd:
            break
        count += 1
    return count


def generate_post_round_alerts(game, round_number):
    """
    Analyze all teams after a round is processed.
    Generate alerts for the instructor based on patterns.
    """
    teams = (Team.objects.filter(game=game, participation_status='active')).order_by('pk')
    alerts = []
    # The coach speaks the instructor's language (W-CE-17).
    language = get_instructor_language(game)

    for team in teams:
        financials = RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()
        prev_financials = RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=round_number - 1,
        ).first()
        performance = RoundResultPerformanceIndex.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()
        coherence = RoundResultCoherence.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()

        if not financials:
            continue

        # === FINANCIAL ALERTS ===

        # Cash crisis approaching
        if financials.cash_closing < 5_000_000:
            alerts.append(_create_alert(
                game, team, round_number, 'financial', 'critical',
                *_alert_text(language, 'cash_crisis', team=team.name,
                             cash=financials.cash_closing, debt=financials.total_debt,
                             net_income=financials.net_income)))

        # Excessive debt
        de_ratio = float(financials.debt_to_equity) if financials.debt_to_equity else 0
        if de_ratio > 1.5:
            alerts.append(_create_alert(
                game, team, round_number, 'financial', 'concern',
                *_alert_text(language, 'leverage', team=team.name, ratio=de_ratio,
                             debt=financials.total_debt, equity=financials.total_equity,
                             interest=financials.interest_expense)))

        # Revenue declining
        if prev_financials and prev_financials.total_revenue > 0:
            if financials.total_revenue < prev_financials.total_revenue * Decimal('0.90'):
                decline_pct = (1 - float(financials.total_revenue / prev_financials.total_revenue)) * 100
                alerts.append(_create_alert(
                    game, team, round_number, 'strategic', 'watch',
                    *_alert_text(language, 'revenue_decline', team=team.name, pct=decline_pct,
                                 revenue=financials.total_revenue,
                                 previous=prev_financials.total_revenue)))

        # === STRATEGIC ALERTS ===

        # No R&D investment for 2+ rounds
        rounds_without_rd = _count_rounds_without_rd(team, round_number)
        if rounds_without_rd >= 2:
            alerts.append(_create_alert(
                game, team, round_number, 'strategic', 'concern',
                *_alert_text(language, 'no_rd', team=team.name, rounds=rounds_without_rd)))

        # Only in home market after Round 3
        market_count = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).count()
        if round_number >= 3 and market_count <= 1:
            alerts.append(_create_alert(
                game, team, round_number, 'missed_opportunity', 'watch',
                *_alert_text(language, 'single_market', team=team.name,
                             count=market_count, round=round_number)))

        # High coherence score (positive)
        if coherence and float(coherence.blended_score) >= 80:
            alerts.append(_create_alert(
                game, team, round_number, 'notable_move', 'info',
                *_alert_text(language, 'coherence_high', team=team.name,
                             score=float(coherence.blended_score))))

        # Performance index dropped significantly
        if performance and float(performance.index_change) < -3:
            alerts.append(_create_alert(
                game, team, round_number, 'strategic', 'concern',
                *_alert_text(language, 'index_drop', team=team.name,
                             drop=abs(float(performance.index_change)),
                             index=float(performance.index_value),
                             previous=float(performance.index_value - performance.index_change),
                             satisfaction=float(performance.satisfaction_score))))

        # === TEACHING MOMENTS ===

        # First acquisition (defensive — TeamAcquisition may not exist)
        if TeamAcquisition is not None:
            try:
                new_acquisition = TeamAcquisition.objects.filter(
                    team=team, acquired_round=round_number,
                ).select_related('acquisition_target').first()
                if new_acquisition:
                    alerts.append(_create_alert(
                        game, team, round_number, 'notable_move', 'info',
                        *_alert_text(language, 'acquisition', team=team.name,
                                     target=new_acquisition.acquisition_target.target_name,
                                     cost=new_acquisition.total_cost_paid,
                                     rounds=new_acquisition.integration_rounds_remaining)))
            except Exception:
                pass  # Table may not exist yet

        # Entered new market
        new_entries = (DecisionMarketEntry.objects.filter(
            submission__team=team,
            submission__round__round_number=round_number,
            action='enter',
        ).select_related('market', 'entry_mode')).order_by('market__code', 'action')
        for entry in new_entries:
            market = entry.market
            mode_name = (get_localized_field(entry.entry_mode, 'name', language)
                         if entry.entry_mode else _alert_text(language, 'unknown_mode'))
            growth_rate = float(market.growth_rate_base) * 100 if hasattr(market, 'growth_rate_base') else 0
            tariff_rate = float(market.tariff_rate) * 100 if hasattr(market, 'tariff_rate') else 0
            alerts.append(_create_alert(
                game, team, round_number, 'notable_move', 'info',
                *_alert_text(language, 'market_entry', team=team.name,
                             market=get_localized_field(market, 'name', language),
                             mode=mode_name, investment=entry.initial_investment,
                             growth=growth_rate, tariff=tariff_rate)))

    # Save all alerts
    InstructorAlert.objects.bulk_create(alerts)
    return len(alerts)


def generate_pre_lock_alerts(game, team, submission):
    """
    Generate alerts when a team locks their decisions.
    Catches obvious mistakes before round processing.
    """
    alerts = []
    language = get_instructor_language(game)

    # Check: production volume far exceeds historical sales
    for mktg in DecisionMarketing.objects.filter(submission=submission).select_related(
            'team_product', 'market').order_by('team_product__name', 'market__code'):
        prev_result = RoundResultProductMarket.objects.filter(
            game=game, team=team,
            team_product=mktg.team_product, market=mktg.market,
            round_number=game.current_round - 1,
        ).first()
        if prev_result and prev_result.units_sold > 0:
            if mktg.production_volume > float(prev_result.units_sold) * 2:
                alerts.append(_create_alert(
                    game, team, game.current_round, 'financial', 'watch',
                    *_alert_text(language, 'overproduction', team=team.name,
                                 product=mktg.team_product.name,
                                 market=get_localized_field(mktg.market, 'name', language),
                                 volume=mktg.production_volume,
                                 sold=int(prev_result.units_sold))))

    InstructorAlert.objects.bulk_create(alerts)
    return alerts


def _get_strategy_context_for_alert(alert):
    """CC-35: Build strategy context for teaching note enhancement."""
    try:
        if alert.team and alert.game:
            from core.engine.strategy_advisory import build_strategy_context
            ctx = build_strategy_context(alert.team, alert.game)
            if ctx:
                return f'{ctx}\n\n'
    except Exception:
        pass
    return ''


def enhance_teaching_note_with_rag(alert):
    """
    Use the RAG layer to provide framework-grounded teaching suggestions.
    Called for 'concern' and 'critical' severity alerts.
    """
    if alert.severity not in ('concern', 'critical'):
        return

    try:
        from core.rag.embeddings import get_embedding
        from core.rag.client import search_articles
    except ImportError:
        return

    try:
        query = f"Teaching strategy for: {alert.title}"
        embedding = get_embedding(query)
        results = search_articles(embedding, limit=2)

        if not results:
            return

        from django.conf import settings
        from core.engine import llm_runner
        if not llm_runner.llm_configured():
            return

        context_text = '\n'.join([r['text'][:300] for r in results])

        # Teaching notes are instructor-facing — use instructor's language
        language = get_instructor_language(alert.game) if alert.game else 'en'
        lang_instruction = build_language_instruction(language)

        text = llm_runner.chat_completion(
            model=llm_runner.model_for_purpose('teaching_note'),
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are an experienced business strategy professor. '
                        'Given a student team situation and relevant research, '
                        'provide a concise teaching note (2-3 sentences) that the instructor '
                        'can use in class discussion. Reference specific frameworks or concepts. '
                        'Write as a peer note to the instructor, not as advice to students.'
                    ),
                },
                {
                    'role': 'user',
                    'content': (
                        f'Situation: {alert.title}\n'
                        f'Detail: {alert.detail}\n\n'
                        + _get_strategy_context_for_alert(alert)
                        + f'Relevant research:\n{context_text}'
                        + lang_instruction
                    ),
                },
            ],
            max_tokens=150,
            temperature=0.3,
        )

        if not text:
            return
        alert.teaching_note = (alert.teaching_note + '\n\n' + text).strip()
        alert.save()

    except Exception as e:
        print(f"RAG teaching note enhancement failed: {e}")
