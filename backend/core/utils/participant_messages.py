"""Shared, bilingual wording for participant-facing validation messages.

Technical logs may name models and fields; messages returned from a student or
instructor API must not.  Keeping the wording here prevents the same rule from
being described differently by serializers and views.
"""
from core.utils.localization import get_user_language


FIELD_LABELS = {
    'rd_budget': {'en': 'R&D budget', 'zh-CN': '研发预算'},
    'marketing_budget': {'en': 'marketing budget', 'zh-CN': '营销预算'},
    'strategy_budget': {'en': 'strategy budget', 'zh-CN': '战略预算'},
    'environmental_investment': {'en': 'environmental investment', 'zh-CN': '环境投入'},
    'social_investment': {'en': 'social investment', 'zh-CN': '社会投入'},
    'initial_investment': {'en': 'initial investment', 'zh-CN': '初始投入'},
    'annual_investment': {'en': 'annual investment', 'zh-CN': '年度投入'},
    'capacity_units': {'en': 'production capacity', 'zh-CN': '产能'},
    'contract_mfg_volume': {'en': 'contract-manufacturing volume', 'zh-CN': '委外生产数量'},
    'committed_cost': {'en': 'committed development cost', 'zh-CN': '承诺的开发成本'},
    'rd_headcount': {'en': 'R&D headcount', 'zh-CN': '研发人数'},
    'commercial_headcount': {'en': 'commercial headcount', 'zh-CN': '商业团队人数'},
    'operations_headcount': {'en': 'operations headcount', 'zh-CN': '运营团队人数'},
    'rd_training_budget': {'en': 'R&D training budget', 'zh-CN': '研发培训预算'},
    'commercial_training_budget': {'en': 'commercial training budget', 'zh-CN': '商业培训预算'},
    'operations_training_budget': {'en': 'operations training budget', 'zh-CN': '运营培训预算'},
    'channel_digital_pct': {'en': 'digital-channel allocation', 'zh-CN': '数字渠道比例'},
    'channel_traditional_pct': {'en': 'traditional-channel allocation', 'zh-CN': '传统渠道比例'},
    'channel_trade_pct': {'en': 'trade-channel allocation', 'zh-CN': '贸易渠道比例'},
    'distribution_investment': {'en': 'distribution investment', 'zh-CN': '分销投入'},
    'sales_team_count': {'en': 'sales-team size', 'zh-CN': '销售团队人数'},
    'calculated_cost': {'en': 'R&D cost', 'zh-CN': '研发成本'},
    'target_level': {'en': 'target capability level', 'zh-CN': '目标能力水平'},
    'volume_commitment_units': {'en': 'sourcing volume commitment', 'zh-CN': '采购承诺数量'},
    'retail_price': {'en': 'unit price', 'zh-CN': '单价'},
    'promotion_budget': {'en': 'promotion budget', 'zh-CN': '促销预算'},
    'production_volume': {'en': 'production volume', 'zh-CN': '生产数量'},
    'demand_estimate': {'en': 'demand estimate', 'zh-CN': '需求预测'},
    'amount': {'en': 'investment amount', 'zh-CN': '投入金额'},
    'new_debt': {'en': 'new borrowing', 'zh-CN': '新增借款'},
    'debt_repayment': {'en': 'debt repayment', 'zh-CN': '偿还债务'},
    'new_equity': {'en': 'new equity funding', 'zh-CN': '新增股权融资'},
    'dividend_per_share': {'en': 'dividend per share', 'zh-CN': '每股股利'},
    'allocation_amount': {'en': 'research allocation', 'zh-CN': '研究分配金额'},
    # Research report names, so a refusal says "the segment report" rather than
    # the report type the URL happens to use.
    'segments': {'en': 'segment', 'zh-CN': '细分市场'},
    'products': {'en': 'product', 'zh-CN': '产品'},
    'markets': {'en': 'market', 'zh-CN': '市场'},
    'channels': {'en': 'channel', 'zh-CN': '渠道'},
    'stakeholders': {'en': 'stakeholder', 'zh-CN': '利益相关者'},
    'analyst_query': {'en': 'analyst query', 'zh-CN': '分析师问询'},
    'investment_amount': {'en': 'compliance investment', 'zh-CN': '合规投入'},
}


MESSAGES = {
    'non_negative': {
        'en': '{field} cannot be negative. Enter zero or a positive value.',
        'zh-CN': '{field}不能为负数。请输入零或正数。',
    },
    'positive_price': {
        'en': 'Unit price must be greater than zero. Enter a positive amount.',
        'zh-CN': '单价必须大于零。请输入正数金额。',
    },
    # Stage 5 price band. Wording chosen once here; which message applies to
    # which state is decided in core/services/price_band.py, so no surface can
    # describe the band differently by picking a different sentence.
    'price_band_alert': {
        'en': 'The price of {submitted} for {product} in {market} is outside this round’s allowed range of {minimum} to {maximum}. Your entry has been saved. If it is still outside the range when the round closes, it will be adjusted to the nearest allowed price.',
        'zh-CN': '{market} 中 {product} 的价格 {submitted} 超出本回合允许的价格区间 {minimum} 至 {maximum}。您的输入已保存。若回合截止时仍超出该区间，价格将调整为最接近的允许价格。',
    },
    'price_blank_alert': {
        'en': 'No price is set for {product} in {market}. If it is still blank when the round closes, it will be priced at {floor}, the lowest price allowed this round. You may price it anywhere between {minimum} and {maximum}.',
        'zh-CN': '{market} 中 {product} 尚未设置价格。若回合截止时仍为空，将按本回合允许的最低价 {floor} 定价。您可在 {minimum} 至 {maximum} 之间自行定价。',
    },
    'price_band_adjusted': {
        'en': '{product} in {market}: you entered {submitted}, which was outside the allowed range of {minimum} to {maximum} for this round. It was adjusted to {applied} when the round closed.',
        'zh-CN': '{market} 中的 {product}：您输入的价格为 {submitted}，超出本回合允许的区间 {minimum} 至 {maximum}。回合截止时已调整为 {applied}。',
    },
    'price_not_offered': {
        'en': '{product} in {market}: no unit price was set and there was no previous price to fall back on, so it was not offered for sale this round and sold nothing. Set a unit price to put it back on the market.',
        'zh-CN': '{market} 中的 {product}：未设置单价，且没有可参考的上期价格，因此本回合未上市销售，销量为零。请设置单价，使其重新上市。',
    },
    'price_blank_applied': {
        'en': '{product} in {market}: no price was entered, so it was priced at {applied} when the round closed — the lowest price allowed this round, whose range was {minimum} to {maximum}.',
        'zh-CN': '{market} 中的 {product}：未输入价格，回合截止时已按本回合允许的最低价 {applied} 定价（本回合允许区间为 {minimum} 至 {maximum}）。',
    },
    'target_markets_required': {
        'en': 'Choose at least one target market before creating the product.',
        'zh-CN': '创建产品前，请至少选择一个目标市场。',
    },
    'target_markets_invalid': {
        'en': 'Choose target markets from the available market list.',
        'zh-CN': '请从可用市场列表中选择目标市场。',
    },
    'campaign_features_required': {
        'en': 'Choose one to three campaign focus features.',
        'zh-CN': '请选择一到三个营销活动重点功能。',
    },
    'campaign_features_invalid': {
        'en': 'Choose campaign focus features from the available feature list.',
        'zh-CN': '请从可用功能列表中选择营销活动重点功能。',
    },
    'one_rd_investment_per_feature': {
        'en': 'Choose each platform feature only once for this round.',
        'zh-CN': '本回合每项平台功能只能选择一次。',
    },
    'product_name_repeated': {
        'en': 'Each new product needs a different name. {names} appears more than once.',
        'zh-CN': '每个新产品都需要不同的名称。{names}重复出现。',
    },
    'product_name_taken': {
        'en': 'Your team already has a product named {names}. Choose a different name.',
        'zh-CN': '您的团队已有名为 {names} 的产品。请选择其他名称。',
    },
    'rd_investment_retired': {
        'en': 'Feature-level R&D investment is no longer available. Develop a new platform and move the product to it to improve the product.',
        'zh-CN': '功能级研发投入现已不可用。请开发新的平台，并将产品迁移到该平台以改进产品。',
    },
    'scenario_price_mismatch': {
        'en': 'Row {row}: the scenario price is {price}. Remove the submitted price or change it to the scenario price.',
        'zh-CN': '第 {row} 行：情景设定的价格为 {price}。请删除提交的价格，或将其改为情景价格。',
    },
    'feature_unavailable': {
        'en': '{feature} is not available on the selected platform. Upgrade to a newer generation to unlock it.',
        'zh-CN': '所选平台尚不支持 {feature}。请升级到更新的平台代际以解锁该功能。',
    },
    'platform_feature_limit': {
        'en': 'A platform can have at most {maximum} selected features. It currently has {current}. Remove a feature before adding another.',
        'zh-CN': '每个平台最多可选择 {maximum} 项功能。目前已有 {current} 项。请先移除一项功能。',
    },
    'round_feature_limit': {
        'en': 'You can invest in at most {maximum} features this round. Remove an investment before adding another.',
        'zh-CN': '本回合最多可投入 {maximum} 项功能。请先移除一项投入。',
    },
    'channel_total': {
        'en': 'Digital, traditional, and trade channel allocations must total 100%. They currently total {total}%.',
        'zh-CN': '数字、传统和贸易渠道的分配总和必须为 100%。当前总和为 {total}%。',
    },
    'talent_decision_required': {
        'en': 'Set the team staffing decision before allocating staff.',
        'zh-CN': '分配员工前，请先设置团队人员决策。',
    },
    'talent_allocation_total': {
        'en': 'Allocated staff ({allocated}) must equal the selected team headcount ({headcount}).',
        'zh-CN': '已分配员工数（{allocated}）必须等于选定的团队人数（{headcount}）。',
    },
    'talent_market_inactive': {
        'en': 'You can allocate staff only to an active market. Choose an active market or set the allocation to zero.',
        'zh-CN': '只能向已进入的活跃市场分配员工。请选择活跃市场，或将分配设为零。',
    },
    'talent_hq_minimum': {
        'en': 'Keep at least {minimum} staff at headquarters (20% of the team headcount).',
        'zh-CN': '总部至少应保留 {minimum} 名员工（团队人数的 20%）。',
    },
    'compliance_maximum': {
        'en': 'Compliance investment cannot exceed $10M per market in one round.',
        'zh-CN': '每个市场每回合的合规投入不得超过 1,000 万美元。',
    },
    'round_closed': {
        'en': 'Round {round} is closed and no longer accepts decisions.',
        'zh-CN': '第 {round} 回合已关闭，不能再提交决策。',
    },
    'lifecycle_in_progress': {
        'en': 'This round is being processed. Refresh shortly to see the results.',
        'zh-CN': '本回合正在处理。请稍后刷新查看结果。',
    },
    'submission_locked': {
        'en': 'This submission is locked. Unlock it before making changes.',
        'zh-CN': '该提交已锁定。请先解锁，再进行修改。',
    },
    'unknown_decision_type': {
        'en': 'This decision section is not available. Refresh the page and try again.',
        'zh-CN': '此决策部分不可用。请刷新页面后重试。',
    },
    'submission_missing': {
        'en': 'Create and save a decision submission before locking it.',
        'zh-CN': '锁定前，请先创建并保存决策提交。',
    },
    'submission_already_locked': {
        'en': 'This submission is already locked.',
        'zh-CN': '该提交已经锁定。',
    },
    'validation_failed': {
        'en': 'Review and correct the listed decision items before locking.',
        'zh-CN': '请检查并更正列出的决策项目后再锁定。',
    },
    'budget_required': {
        'en': 'Set the budget allocation before locking.',
        'zh-CN': '锁定前，请先设置预算分配。',
    },
    'permission_denied': {
        'en': 'You do not have permission to change this team’s decisions.',
        'zh-CN': '您无权更改该团队的决策。',
    },
    'team_withdrawn': {
        'en': 'This team has been withdrawn from the competition and cannot submit decisions.',
        'zh-CN': '该团队已退出比赛，无法提交决策。',
    },
    'game_paused': {
        'en': 'Your instructor has paused the game. Changes cannot be made right now.',
        'zh-CN': '教师已暂停比赛。当前无法进行修改。',
    },
    'game_finished': {
        'en': 'This game has finished and no longer accepts decision changes.',
        'zh-CN': '该比赛已结束，不能再修改决策。',
    },
    'round_not_open': {
        'en': 'This round is not open for decision submissions.',
        'zh-CN': '本回合尚未开放决策提交。',
    },
    'round_not_accepting': {
        'en': 'Round {round} is {status} and no longer accepts decisions.',
        'zh-CN': '第 {round} 回合状态为“{status}”，不能再提交决策。',
    },
    'round_locked_by_instructor': {
        'en': 'Your instructor has locked decisions for this round.',
        'zh-CN': '教师已锁定本回合的决策。',
    },
    'round_deadline_passed': {
        'en': 'The deadline for this round has passed. Your decisions are locked.',
        'zh-CN': '本回合的截止时间已过。您的决策已锁定。',
    },
    'rd_budget_exceeded': {
        'en': 'R&D investments of {spent} exceed the R&D budget of {budget}. Reduce investments or increase the budget.',
        'zh-CN': '研发投入 {spent} 超过研发预算 {budget}。请减少投入或增加预算。',
    },
    'rd_platform_not_owned': {
        'en': 'An R&D investment uses a platform your team does not own. Choose one of your team’s platforms.',
        'zh-CN': '一项研发投入使用了不属于您团队的平台。请选择您团队的平台。',
    },
    'rd_platform_inactive': {
        'en': 'An R&D investment uses an inactive platform. Choose an active platform.',
        'zh-CN': '一项研发投入使用了未激活的平台。请选择激活的平台。',
    },
    'rd_feature_wrong_layer': {
        'en': 'An R&D investment selects a feature that is not a platform feature. Choose a platform feature.',
        'zh-CN': '一项研发投入选择了非平台功能。请选择平台功能。',
    },
    'rd_feature_unlicensable': {
        'en': 'The selected feature cannot be licensed. Choose another development method or feature.',
        'zh-CN': '所选功能不可授权。请选择其他开发方式或功能。',
    },
    'feature_at_ceiling': {
        'en': '{feature} is already at its highest available level on this platform.',
        'zh-CN': '{feature} 在该平台上已达到最高可用级别。',
    },
    'platform_wrong_scenario': {
        'en': 'The selected platform is not available in this game. Choose an available platform.',
        'zh-CN': '所选平台不适用于本场比赛。请选择可用平台。',
    },
    'platform_not_unlocked': {
        'en': '{platform} becomes available in round {round}. Choose an available platform or wait until then.',
        'zh-CN': '{platform} 将在第 {round} 回合开放。请选择可用平台，或等待该回合。',
    },
    'platform_already_owned': {
        'en': 'Your team already has {platform}. Choose a different platform.',
        'zh-CN': '您的团队已有 {platform}。请选择其他平台。',
    },
    'product_platform_not_owned': {
        'en': 'A new product uses a platform your team does not own. Choose one of your team’s platforms.',
        'zh-CN': '一个新产品使用了不属于您团队的平台。请选择您团队的平台。',
    },
    'product_platform_inactive': {
        'en': 'A new product uses an inactive platform. Choose an active platform.',
        'zh-CN': '一个新产品使用了未激活的平台。请选择激活的平台。',
    },
    'product_limit': {
        'en': 'This would exceed the maximum of {maximum} active products. Retire a product or remove this new product.',
        'zh-CN': '这将超过最多 {maximum} 个活跃产品的上限。请停产一个产品或移除这个新产品。',
    },
    'product_market_not_active': {
        'en': '{product} targets a market where your team has no active presence. Enter that market first or remove it from the product.',
        'zh-CN': '{product} 的目标市场中有您团队尚未进入的市场。请先进入该市场，或从产品中移除该市场。',
    },
    'product_not_owned': {
        'en': 'A product decision references a product your team does not own. Choose one of your team’s products.',
        'zh-CN': '一项产品决策引用了不属于您团队的产品。请选择您团队的产品。',
    },
    'product_not_active': {
        'en': '{product} is not active and cannot be retired or marketed. Choose an active product.',
        'zh-CN': '{product} 未处于活跃状态，无法停产或营销。请选择活跃产品。',
    },
    'marketing_channels_invalid': {
        'en': 'Marketing for {product} in {market} has channel allocations totaling {total}%. Set them to 100%.',
        'zh-CN': '{product} 在 {market} 的营销渠道分配总和为 {total}%。请调整为 100%。',
    },
    'marketing_price_invalid': {
        'en': 'Set a unit price above zero for {product} in {market}.',
        'zh-CN': '请为 {market} 中的 {product} 设置大于零的单价。',
    },
    'marketing_budget_exceeded': {
        'en': 'Marketing spend of {spent} exceeds the marketing budget of {budget}. Reduce spending or increase the budget.',
        'zh-CN': '营销支出 {spent} 超过营销预算 {budget}。请减少支出或增加预算。',
    },
    'market_already_entered': {
        'en': 'Your team is already active in {market}. Choose a different market or action.',
        'zh-CN': '您的团队已在 {market} 开展业务。请选择其他市场或行动。',
    },
    'market_not_active': {
        'en': 'Your team is not active in {market}. Enter the market before changing its mode or exiting.',
        'zh-CN': '您的团队尚未进入 {market}。请先进入该市场，再变更进入模式或退出。',
    },
    'entry_investment_low': {
        'en': 'Entry investment in {market} is below the minimum. Increase it from {submitted} to at least {minimum}.',
        'zh-CN': '{market} 的进入投资低于最低要求。请从 {submitted} 提高到至少 {minimum}。',
    },
    'product_portfolio_required': {
        'en': 'Set the product portfolio before locking.',
        'zh-CN': '锁定前，请先设置产品组合。',
    },
    'marketing_mix_required': {
        'en': 'Set the marketing mix for every active product-market combination before locking.',
        'zh-CN': '锁定前，请为每个活跃的产品—市场组合设置营销组合。',
    },
    'marketing_mix_needs_product': {
        'en': 'Create or activate a product-market combination before setting the marketing mix.',
        'zh-CN': '设置营销组合前，请先创建或激活一个产品—市场组合。',
    },
    'strategy_mix_required': {
        'en': 'Set at least one strategy decision before locking.',
        'zh-CN': '锁定前，请至少设置一项战略决策。',
    },
    'debt_repayment_exceeds_debt': {
        'en': 'Debt repayment of {repayment} exceeds outstanding debt of {debt}. Reduce the repayment.',
        'zh-CN': '偿还债务 {repayment} 超过未偿债务 {debt}。请减少还款额。',
    },
    'debt_ratio_exceeded': {
        'en': 'The projected debt-to-equity ratio of {ratio} exceeds the maximum of {maximum}. Adjust financing.',
        'zh-CN': '预计资产负债率 {ratio} 超过上限 {maximum}。请调整融资。',
    },
    'dividends_exceed_equity': {
        'en': 'Total dividends of {dividends} exceed projected equity. Reduce the dividend.',
        'zh-CN': '股利总额 {dividends} 超过预计股东权益。请降低每股股利。',
    },
    'cash_negative': {
        'en': 'Projected ending cash is {cash}. Reduce spending or raise financing before locking.',
        'zh-CN': '预计期末现金为 {cash}。锁定前请减少支出或增加融资。',
    },
    'committed_spend_exceeds_cash': {
        'en': 'Committed spend of {committed} exceeds available cash of {cash}. This includes {platform} of platform development.',
        'zh-CN': '承诺支出 {committed} 超过可用现金 {cash}，其中包括 {platform} 的平台开发支出。',
    },
    'rd_commitments_exceed_budget': {
        'en': 'R&D commitments of {committed} exceed the R&D budget of {budget}. Platform development counts against the R&D budget.',
        'zh-CN': '研发承诺 {committed} 超过研发预算 {budget}。平台开发计入研发预算。',
    },
    'mandatory_communication_required': {
        'en': 'Submit the required communication “{communication}” before locking.',
        'zh-CN': '锁定前，请提交必需的沟通任务“{communication}”。',
    },
    'scenario_price_unavailable': {
        'en': 'Row {row}: this decision cannot be priced from the current scenario. Choose an available option or ask your instructor to review the scenario setup.',
        'zh-CN': '第 {row} 行：当前情景无法为该决策定价。请选择可用选项，或请教师检查情景设置。',
    },
    'production_capacity_exceeded': {
        'en': 'Production volume of {volume} exceeds available plant capacity of {capacity} in {market}. Reduce production or choose another source.',
        'zh-CN': '{market} 的生产数量 {volume} 超过可用工厂产能 {capacity}。请减少生产量或选择其他来源。',
    },
    'production_capacity_with_contract_exceeded': {
        'en': 'Production volume of {volume} exceeds plant capacity of {capacity} plus contract-manufacturing capacity of {contract_capacity} in {market}. Reduce production or choose another source.',
        'zh-CN': '{market} 的生产数量 {volume} 超过工厂产能 {capacity} 加委外生产产能 {contract_capacity}。请减少生产量或选择其他来源。',
    },
    'platform_request_duplicate': {
        'en': 'Request the same platform only once in this submission. A team can develop one platform of each generation.',
        'zh-CN': '本次提交中同一平台只能请求一次。每个团队每个平台代际只能开发一个平台。',
    },
    'platform_already_held': {
        'en': 'Your team already has the selected platform. Retire it before rebuilding that generation.',
        'zh-CN': '您的团队已有所选平台。重新开发该平台代际前，请先将其停用。',
    },
    'platform_not_available': {
        'en': 'The selected platform is not available. Refresh the page and choose an available platform.',
        'zh-CN': '所选平台不可用。请刷新页面并选择可用平台。',
    },
    'platform_unlock_required': {
        'en': '{platform} becomes available in round {unlock_round}. It cannot be developed in round {round}.',
        'zh-CN': '{platform} 将在第 {unlock_round} 回合开放，不能在第 {round} 回合开发。',
    },
    'equity_exceeds_funding_need': {
        'en': 'New equity of {requested} exceeds the current-round funding shortfall of {maximum}. Reduce the equity raise; equity cannot create surplus cash or fund dividends.',
        'zh-CN': '新增股权融资 {requested} 超过本回合资金缺口 {maximum}。请减少股权融资；股权融资不能用于创造盈余现金或支付股利。',
    },
    'zero_budget_warning': {
        'en': '{field} is set to zero. Review this before locking.',
        'zh-CN': '{field} 已设为零。锁定前请确认。',
    },
    'research_purchase_exceeds_cash': {
        'en': 'Buying the {report} report costs {price}, which would take committed spend to {committed} against available cash of {cash}. Reduce committed spend or raise financing before buying it.',
        'zh-CN': '购买{report}报告需 {price}，将使承诺支出达到 {committed}，而可用现金为 {cash}。购买前请减少承诺支出或增加融资。',
    },
    'research_report_unknown': {
        'en': 'That research report is not available. Choose a report from the research catalogue.',
        'zh-CN': '该研究报告不可用。请从研究目录中选择报告。',
    },
    'research_price_changed': {
        'en': 'The {report} report costs {price}. Refresh the page and buy it at the current price.',
        'zh-CN': '{report}报告的价格为 {price}。请刷新页面并按当前价格购买。',
    },
    'research_purchase_after_lock': {
        'en': 'Your decisions for this round are locked, so no further research can be bought. Unlock the round to buy it.',
        'zh-CN': '您本回合的决策已锁定，无法再购买研究报告。如需购买，请先解锁本回合。',
    },
}


def language_for_request(request):
    """Return the supported language for a request, defaulting safely to EN."""
    return 'zh-CN' if get_user_language(request) == 'zh-CN' else 'en'


def participant_message(key, *, language='en', **values):
    """Render a reviewed participant-facing message in the requested language."""
    try:
        template = MESSAGES[key][language]
    except KeyError as error:
        raise KeyError(f'Unknown participant message {key!r}') from error
    return template.format(**values)


def field_label(field_name, language='en'):
    """Business label for a decision field; never expose its storage name."""
    labels = FIELD_LABELS.get(field_name)
    if labels is None:
        return field_name.replace('_', ' ')
    return labels.get(language, labels['en'])


def serializer_language(serializer_field):
    """Read the request language from a DRF field validator's serializer."""
    root = getattr(serializer_field, 'root', None)
    context = getattr(root, 'context', {}) or {}
    return language_for_request(context.get('request'))
