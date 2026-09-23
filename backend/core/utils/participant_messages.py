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
    # Every other number a student can write (2026-09-21), so that a refusal
    # of one always has a business name to use. zh-CN follows the label the
    # page itself shows for the input (`sc.*` and `corporate_strategy.*` in the
    # frontend catalogue). `test_numeric_refusal_language` fails when a
    # writable numeric decision field is missing from this table.
    'allocation_pct': {'en': 'supplier share', 'zh-CN': '供应商份额'},
    'mode_sea_pct': {'en': 'sea share of shipments', 'zh-CN': '海运比例'},
    'mode_air_pct': {'en': 'air share of shipments', 'zh-CN': '空运比例'},
    'mode_rail_pct': {'en': 'rail share of shipments', 'zh-CN': '铁路比例'},
    'mode_road_pct': {'en': 'road share of shipments', 'zh-CN': '公路比例'},
    'volume_commitment_teu': {'en': 'shipping volume commitment (TEU)', 'zh-CN': '承诺运量（TEU）'},
    'insurance_coverage_pct': {'en': 'insurance percentage', 'zh-CN': '保险比例'},
    'reverse_logistics_capacity_pct': {'en': 'returns capacity', 'zh-CN': '退货处理能力'},
    'coverage_pct': {'en': 'export-credit coverage', 'zh-CN': '出口信用保险覆盖比例'},
    'hedge_ratio': {'en': 'hedge ratio', 'zh-CN': '对冲比例'},
    'tenor_days': {'en': 'hedge tenor in days', 'zh-CN': '对冲期限（天）'},
    'buffer_days': {'en': 'inventory buffer in days', 'zh-CN': '库存缓冲天数'},
    'safety_stock_trigger_pct': {'en': 'reorder point', 'zh-CN': '补货触发点'},
    'hq_count': {'en': 'headquarters staff', 'zh-CN': '总部人数'},
    'market_allocation': {'en': 'staff assigned to a market', 'zh-CN': '派驻市场的人数'},
}


# ---------------------------------------------------------------------------
# GSP-CRV2-12 (V2-069.1) — round status, as a participant reads it
# ---------------------------------------------------------------------------
# `Round.STATUS_CHOICES` stores English tokens. Interpolating one straight into
# a translated sentence produced 第 N 回合状态为“closed” for a Chinese
# participant: a Chinese frame around an English storage token. The label is
# translated here so the sentence is wholly in one language, and so the four
# authored statuses are named in one place rather than at each interpolation.
ROUND_STATUS_LABELS = {
    'pending': {'en': 'not yet open', 'zh-CN': '尚未开放'},
    'open': {'en': 'open', 'zh-CN': '已开放'},
    'closed': {'en': 'closed', 'zh-CN': '已关闭'},
    'processed': {'en': 'processed', 'zh-CN': '已结算'},
}


MESSAGES = {
    'non_negative': {
        'en': '{field} cannot be negative. Enter zero or a positive value.',
        'zh-CN': '{field}不能为负数。请输入零或正数。',
    },
    # Django REST Framework's own numeric refusals, re-said (2026-09-21). Which
    # DRF error code maps to which of these is decided once, in
    # core/utils/numeric_refusals.py. None states the limit itself: the
    # response carries DRF's code and sentence but not the number, and reading
    # it back out of the English sentence is what this replaces.
    'number_too_large': {
        'en': '{field} is larger than the simulation can record. Enter a smaller number.',
        'zh-CN': '{field}超出了系统可记录的上限。请输入较小的数值。',
    },
    'number_too_small': {
        'en': '{field} is below the lowest value allowed. Enter a larger number.',
        'zh-CN': '{field}低于允许的最小值。请输入较大的数值。',
    },
    'number_too_many_decimals': {
        'en': '{field} has more decimal places than can be recorded. Round it and try again.',
        'zh-CN': '{field}的小数位数过多。请四舍五入后重试。',
    },
    'number_required': {
        'en': '{field} must be a number.',
        'zh-CN': '{field}必须是数字。',
    },
    'whole_number_required': {
        'en': '{field} must be a whole number.',
        'zh-CN': '{field}必须是整数。',
    },
    # Stands in for {field} above when a field has no business label yet, so a
    # storage name is never what fills the gap.
    'this_number': {
        'en': 'This number',
        'zh-CN': '该数值',
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
    # -----------------------------------------------------------------------
    # R35 (2026-09-17) — the demoted team is told on its own results screen
    # -----------------------------------------------------------------------
    # Under R32 the standings place a commercially inactive firm below every
    # firm that competed, whatever its score, so a team can hold a HIGHER
    # performance index than the team above it and still finish below it. R34
    # recorded that firing as an audit event; these are the sentences the team
    # itself reads. Which one applies is decided in
    # `core/engine/leaderboard.py::demotion_notice`, beside the payload that
    # decides it, so no surface can describe the rule differently by picking a
    # different sentence.
    #
    # Two keys rather than one, because R34's payload is deliberately honest
    # about what the guard cost: `outscored_a_firm_ranked_above` is false when
    # the firm would have finished last regardless. That firm is still told the
    # rule and still told it fired — it is simply not told it lost a place it
    # never held.
    #
    # Both sentences say the index itself was not reduced. That is R32's whole
    # point: the standing moved, the carried score did not. A team told only
    # "you were placed last" would reasonably read it as a scoring penalty,
    # which is precisely the control R32 removed.
    'inactivity_demotion': {
        'en': 'Your firm sold nothing in round {round}, so it did not compete this round. A firm that does not compete is placed below every firm that did, whatever its score — so your firm was ranked {rank} in this round’s standings, carrying a performance index of {index}. The index itself was not reduced; only the placing. Sell in at least one market next round to be ranked on your score again.',
        'zh-CN': '第 {round} 回合贵公司没有任何销售，因此本回合未参与竞争。未参与竞争的公司无论得分高低，都会排在所有参与竞争的公司之后——因此贵公司本回合排名第 {rank} 位，绩效指数为 {index}。绩效指数本身并未被扣减，受影响的只是排名。下一回合请至少在一个市场实现销售，即可重新按得分排名。',
    },
    'inactivity_demotion_outscored': {
        'en': 'Your firm sold nothing in round {round}, so it did not compete this round. A firm that does not compete is placed below every firm that did, whatever its score — so your firm was ranked {rank} in this round’s standings with a performance index of {index}, below firms whose index was lower than yours. The index itself was not reduced; only the placing. Sell in at least one market next round to be ranked on your score again.',
        'zh-CN': '第 {round} 回合贵公司没有任何销售，因此本回合未参与竞争。未参与竞争的公司无论得分高低，都会排在所有参与竞争的公司之后——因此贵公司本回合排名第 {rank} 位，绩效指数为 {index}，低于绩效指数不及贵公司的其他公司。绩效指数本身并未被扣减，受影响的只是排名。下一回合请至少在一个市场实现销售，即可重新按得分排名。',
    },
    # -----------------------------------------------------------------------
    # W-CE3-15 — the same rule, on the screen the standings are read from
    # -----------------------------------------------------------------------
    # The two sentences above are addressed to the demoted team on its own
    # results screen. The leaderboard is read by every team and by the
    # instructor, and it is where the inversion is actually *seen*: the top
    # score sitting in fourth place. These are the third-person half -- a row
    # marker and the rule under the table -- so the standings never contradict
    # the numbers beside them with nothing to explain it.
    #
    # They say no more than the leaderboard already publishes: the row's own
    # revenue is on the same line. No rival's score is named (R35's standard).
    # W-CE3-10. `views/scorecard.py` hard-coded the English literal 'None'
    # as the capability perspective's platform name for a team that holds no
    # platform, so a Chinese dashboard read `None`. It is a stated absence,
    # not a storage value, so it is a sentence like any other.
    'platform_none_held': {
        'en': 'None',
        'zh-CN': '无',
    },
    'inactivity_rank_marker': {
        'en': 'Did not compete',
        'zh-CN': '未参与竞争',
    },
    'inactivity_rank_rule': {
        'en': 'A company that sold nothing in a round did not compete in it, and is placed below every company that did, whatever its score. The performance index itself is not reduced; only the placing.',
        'zh-CN': '某一回合没有任何销售的公司，即为该回合未参与竞争，无论得分高低，都会排在所有参与竞争的公司之后。绩效指数本身并未被扣减，受影响的只是排名。',
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
    'marketing_row_refused': {
        'en': '{product} in {market}: {reason}',
        'zh-CN': '{product}（{market}）：{reason}',
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
    # W-CE2-01: two plants started by one team in one market in one round
    # share the hashed `team_plant` section's natural key and make the round
    # unsnapshotable, so the collision is refused where it would be created.
    'plant_already_queued': {
        'en': 'Your company has already queued a plant in {market}. One plant per market in a round.',
        'zh-CN': '贵公司本回合已在{market}安排建设工厂。每个市场每回合只能建设一座工厂。',
    },
    'plant_and_acquired_plant': {
        'en': 'The acquisition of {target} already brings a plant in {market}, so a plant build there cannot be queued as well. Withdraw one of the two.',
        'zh-CN': '收购{target}已在{market}带来一座工厂，因此不能同时安排在该市场建设工厂。请撤回其中一项。',
    },
    'compliance_market_inactive': {
        'en': 'You can invest in compliance only in a market your company operates in. Remove the other market and try again.',
        'zh-CN': '只能在公司已进入的市场进行合规投入。请移除其他市场后重试。',
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
        'en': 'An instructor is changing this round right now, so nothing was saved. Your entries are unchanged, and your edit will be sent again in a moment.',
        'zh-CN': '教师正在调整本回合，因此未保存任何内容。您的输入未被更改，稍后将自动重新提交。',
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
        'zh-CN': '该团队已退出游戏，无法提交决策。',
    },
    'game_paused': {
        'en': 'Your instructor has paused the game. Changes cannot be made right now.',
        'zh-CN': '教师已暂停游戏。当前无法进行修改。',
    },
    'game_finished': {
        'en': 'This game has finished and no longer accepts decision changes.',
        'zh-CN': '该游戏已结束，不能再修改决策。',
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
        'zh-CN': '所选平台不适用于本游戏。请选择可用平台。',
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
    # The two refusals a student can meet after pressing Ask on the analyst
    # tab. Neither may carry anything the server raised: the reason an outage
    # happened goes to the log, not to a participant.
    'analyst_query_limit_reached': {
        'en': 'Your team has used all {maximum} analyst questions for this round, so this question was not asked and nothing was charged. You can ask again next round.',
        'zh-CN': '您的团队本回合的 {maximum} 次分析师查询机会已用完，因此本次问题未提交，也未产生费用。下一回合可继续提问。',
    },
    'analyst_unavailable': {
        'en': 'The research analyst is unavailable right now, so your question was not answered and nothing was charged. Try again in a few minutes; if it keeps happening, tell your instructor.',
        'zh-CN': '分析师服务暂时不可用，因此您的问题未得到回答，也未产生费用。请几分钟后重试；如问题持续出现，请告知教师。',
    },
    # The rest of what the analyst route can say. `analyst_no_relevant_research`
    # is not a refusal: it is what the analyst says when the search finds
    # nothing. R42: that costs nothing and uses no question, and it says so.
    'analyst_question_required': {
        'en': 'Type a question for the analyst before pressing Ask. Nothing was asked and nothing was charged.',
        'zh-CN': '请先输入要向分析师提出的问题，再点击提问。本次未提交问题，也未产生费用。',
    },
    'analyst_not_enabled': {
        'en': 'The research analyst is not part of this game, so your question was not asked and nothing was charged.',
        'zh-CN': '本游戏未开放分析师服务，因此您的问题未提交，也未产生费用。',
    },
    'analyst_game_or_team_not_found': {
        'en': 'This game or team could not be found, so your question was not asked and nothing was charged. Reload the page; if it keeps happening, tell your instructor.',
        'zh-CN': '未找到该游戏或团队，因此您的问题未提交，也未产生费用。请刷新页面；如问题持续出现，请告知教师。',
    },
    'analyst_no_relevant_research': {
        'en': 'The analyst found no relevant research for this question. Try broader terms, or ask about a specific market, entry strategy or competitor. Nothing was charged, and this question does not count toward your team\'s questions for the round.',
        'zh-CN': '分析师未找到与该问题相关的研究资料。请尝试使用更宽泛的措辞，或就具体市场、进入策略或竞争对手提问。本次提问未收费，也不计入您团队本回合的提问次数。',
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
    # -----------------------------------------------------------------------
    # GSP-CRV2-12 — the Decision Summary checklist (V2-069.3)
    # -----------------------------------------------------------------------
    # The Summary view returned storage names and English-only advice. The
    # frontend renders `lock_blockers` and each category's warnings verbatim —
    # SummaryPage.js passes them through without `t()` — so the wording a
    # participant reads is decided here and nowhere else.
    'instructor_access_required': {
        'en': 'This area is open to instructors only.',
        'zh-CN': '此区域仅向教师开放。',
    },
    'permission_denied_read': {
        'en': 'You do not have permission to view this team’s decisions.',
        'zh-CN': '您无权查看该团队的决策。',
    },
    'summary_no_submission': {
        'en': 'No decisions have been started for this round. Open any decision area to begin.',
        'zh-CN': '本回合尚未开始任何决策。请打开任一决策页面开始填写。',
    },
    'summary_rd_none': {
        'en': 'No R&D investment is planned this round. Open R&D Investment to add one.',
        'zh-CN': '本回合尚未安排研发投入。请打开“研发投入”页面添加。',
    },
    'summary_marketing_incomplete': {
        'en': '{count} product-market combination(s) still need a marketing mix. Open Marketing Mix to complete them.',
        'zh-CN': '还有 {count} 个产品—市场组合尚未设置营销组合。请打开“营销组合”页面完成设置。',
    },
    'summary_market_without_products': {
        'en': 'Your team is active in {market} but has no products assigned there. Open Product Portfolio and add {market} as a target market.',
        'zh-CN': '您的团队已在 {market} 开展业务，但尚未在该市场投放产品。请打开“产品组合”页面，将 {market} 添加为目标市场。',
    },
    'summary_market_without_marketing': {
        'en': 'Your team has products in {market} but no marketing mix set there. Open Marketing Mix to set unit price, production volume and promotion.',
        'zh-CN': '您的团队在 {market} 已有产品，但尚未设置营销组合。请打开“营销组合”页面设置单价、生产数量和促销。',
    },
    'summary_entering_without_products': {
        'en': 'Your team is entering {market} this round but has no products assigned there yet. Open Product Portfolio and add {market} as a target market.',
        'zh-CN': '您的团队将在本回合进入 {market}，但尚未在该市场投放产品。请打开“产品组合”页面，将 {market} 添加为目标市场。',
    },
    # The platform-generation prerequisite rows on the R&D page. RDPage.js
    # renders `{requirement} — {detail}` verbatim, so these are participant
    # copy despite arriving as structured data. "Gen 2" became "Generation 2":
    # the abbreviation is the schema's, not the business's.
    'rd_prereq_round': {
        'en': 'Round {round} or later',
        'zh-CN': '第 {round} 回合或之后',
    },
    'rd_prereq_round_detail': {
        'en': 'Current round: {current}',
        'zh-CN': '当前回合：{current}',
    },
    'rd_prereq_generation': {
        'en': 'Generation {generation} must be active',
        'zh-CN': '第 {generation} 代平台必须处于活跃状态',
    },
    'rd_prereq_generation_active': {
        'en': 'Active',
        'zh-CN': '已激活',
    },
    'rd_prereq_generation_missing': {
        'en': 'Not yet developed',
        'zh-CN': '尚未开发',
    },
    'rd_prereq_features': {
        'en': 'At least {count} features at level {level} or higher',
        'zh-CN': '至少 {count} 项功能达到 {level} 级或以上',
    },
    'rd_prereq_features_detail': {
        'en': '{qualifying} of {count} features qualify',
        'zh-CN': '{count} 项中已有 {qualifying} 项符合',
    },
    'summary_financing_none': {
        'en': 'No financing changes this round. No action is required.',
        'zh-CN': '本回合没有融资变动，无需操作。',
    },
    # The supply-chain sections of the Summary (W-CE-13, 2026-09-22): the lock
    # never required them, and the checklist said 'Open Sourcing to complete
    # this requirement'.
    'summary_section_optional': {
        'en': 'Optional this round. Locking your decisions does not require it.',
        'zh-CN': '本回合为可选项，锁定决策时无需完成。',
    },
    # -----------------------------------------------------------------------
    # W-CE-16 (2026-09-22) -- sentences that reached a Chinese student in
    # English because they were f-strings in a view.
    # -----------------------------------------------------------------------
    # The dashboard's Strategic Signals (views/scorecard.py).
    'signal_rd_low': {
        'en': 'R&D investment is {pct}% of revenue. Competitors may be outpacing your innovation.',
        'zh-CN': '研发投入仅占收入的 {pct}%。竞争对手的创新可能正在超越您。',
    },
    'signal_tech_low': {
        'en': 'Technology capability at {pct}%. A next-generation platform is available for development.',
        'zh-CN': '技术能力为 {pct}%。新一代平台已可开发。',
    },
    'signal_satisfaction_low': {
        'en': 'Customer satisfaction is below average. Review Market Research to identify underperforming segments.',
        'zh-CN': '客户满意度低于平均水平。请查看市场研究，找出表现不佳的细分市场。',
    },
    'signal_single_market': {
        'en': 'Operating in {entered} of {total} markets. International expansion could unlock growth.',
        'zh-CN': '目前仅在 {total} 个市场中的 {entered} 个开展业务。国际扩张可能带来增长。',
    },
    'signal_leverage': {
        'en': 'Debt-to-equity ratio at {ratio}. Conservative investors may be concerned.',
        'zh-CN': '资产负债率为 {ratio}。保守型投资者可能会感到担忧。',
    },
    # Why an acquisition target cannot be bought yet (the M&A card).
    'ma_available_from_round': {
        'en': 'Available from Round {round}',
        'zh-CN': '第 {round} 回合起可用',
    },
    'ma_requires_presence': {
        'en': 'Requires presence in {market}',
        'zh-CN': '需要先进入{market}',
    },
    'ma_already_acquired': {
        'en': 'Already acquired by {team}',
        'zh-CN': '已被{team}收购',
    },
    # How this round's R&D budget was arrived at (the R&D page header).
    'rd_budget_source': {
        'en': '20% of previous round net profit ({profit}) + base allocation ({base})',
        'zh-CN': '上一回合净利润的 20%（{profit}）+ 基础拨款（{base}）',
    },
    # The research reports' rating words (views/research_reports.py). The view
    # reasons in codes and renders the word here, so a Chinese reader gets
    # the word and the page keeps colouring by the code.
    'research_importance_critical': {'en': 'Critical', 'zh-CN': '关键'},
    'research_importance_high': {'en': 'High', 'zh-CN': '高'},
    'research_importance_moderate': {'en': 'Moderate', 'zh-CN': '中等'},
    'research_importance_low': {'en': 'Low', 'zh-CN': '低'},
    'research_fit_strong': {'en': 'Strong', 'zh-CN': '强'},
    'research_fit_moderate': {'en': 'Moderate', 'zh-CN': '中等'},
    'research_fit_weak': {'en': 'Weak', 'zh-CN': '弱'},
    'research_fit_very_weak': {'en': 'Very Weak', 'zh-CN': '很弱'},
    'research_growth_fastest': {'en': 'Fastest', 'zh-CN': '最快'},
    'research_growth_fast': {'en': 'Fast', 'zh-CN': '快速'},
    'research_growth_moderate': {'en': 'Moderate growth', 'zh-CN': '温和增长'},
    'research_growth_slow': {'en': 'Slow growth', 'zh-CN': '缓慢增长'},
    'research_growth_moderate_short': {'en': 'Moderate', 'zh-CN': '温和'},
    'research_growth_slow_short': {'en': 'Slow', 'zh-CN': '缓慢'},
    'research_price_very_high': {'en': 'Very High', 'zh-CN': '很高'},
    'research_price_high': {'en': 'High', 'zh-CN': '高'},
    'research_price_moderate': {'en': 'Moderate', 'zh-CN': '中等'},
    'research_price_low': {'en': 'Low', 'zh-CN': '低'},
    'research_channel_fit_excellent': {'en': 'Excellent', 'zh-CN': '极佳'},
    'research_channel_fit_good': {'en': 'Good', 'zh-CN': '良好'},
    'research_channel_fit_moderate': {'en': 'Moderate', 'zh-CN': '中等'},
    'research_channel_fit_poor': {'en': 'Poor', 'zh-CN': '较差'},
    'research_channel_mass_retail': {'en': 'Mass Retail', 'zh-CN': '大众零售'},
    'research_channel_selective_retail': {'en': 'Selective Retail', 'zh-CN': '精选零售'},
    'research_channel_exclusive_retail': {'en': 'Exclusive Retail', 'zh-CN': '独家零售'},
    'research_channel_direct_online': {'en': 'Direct Online', 'zh-CN': '直销在线'},
    'research_channel_hybrid': {'en': 'Hybrid', 'zh-CN': '混合渠道'},
    'research_all_markets': {'en': 'All Markets', 'zh-CN': '所有市场'},
    'research_global': {'en': 'Global', 'zh-CN': '全球'},
    # -----------------------------------------------------------------------
    # W-CE2-07 — the Strategic Scorecard's sentences (2026-09-23)
    # -----------------------------------------------------------------------
    # English byte-identical to the f-strings `engine/coherence.py` stored, so
    # the row a replay compares is unchanged. `core/services/coherence_feedback`
    # picks the key; a test asserts the English still matches.
    'coherence_leverage_conservative': {
        'en': 'Conservative leverage. Strong financial position.',
        'zh-CN': '杠杆水平保守。财务状况稳健。',
    },
    'coherence_leverage_moderate': {
        'en': 'Moderate leverage. Manageable but watch debt growth.',
        'zh-CN': '杠杆水平适中。尚在可控范围，但需关注债务增长。',
    },
    'coherence_leverage_high': {
        'en': 'High leverage. Risk of financial distress.',
        'zh-CN': '杠杆水平过高。存在财务困境风险。',
    },
    'coherence_budget_no_baseline': {
        'en': 'No operating budget baseline (first round).',
        'zh-CN': '尚无经营预算基准（首个回合）。',
    },
    'coherence_budget_within': {
        'en': 'Spending within operating budget. Good fiscal discipline.',
        'zh-CN': '支出未超出经营预算。财务纪律良好。',
    },
    'coherence_budget_slightly_over': {
        'en': 'Slightly over budget ({over}). Minor overspend.',
        'zh-CN': '略微超出预算（{over}）。属小幅超支。',
    },
    'coherence_budget_over': {
        'en': 'Over budget by {over}. Spending discipline is weak.',
        'zh-CN': '超出预算 {over}。支出纪律薄弱。',
    },
    'coherence_budget_significantly_over': {
        'en': 'Significantly over budget ({over}). Reckless spending erodes '
              'stakeholder confidence.',
        'zh-CN': '显著超出预算（{over}）。无节制的支出会削弱利益相关者的信心。',
    },
    'coherence_budget_massively_over': {
        'en': 'Massively over budget ({over}). No spending discipline.',
        'zh-CN': '大幅超出预算（{over}）。毫无支出纪律。',
    },
    'coherence_governance_tax_clear': {
        'en': 'No governance-tax conflict detected.',
        'zh-CN': '未发现治理与税务之间的冲突。',
    },
    'coherence_governance_tax_conflict': {
        'en': 'Anti-corruption commitment conflicts with aggressive tax '
              'optimization. Stakeholders view this as hypocritical — '
              'coherence heavily penalized.',
        'zh-CN': '反腐败承诺与激进的税务筹划相互冲突。利益相关者视之为言行不一，'
                 '战略协同性因此被大幅扣分。',
    },
    'coherence_governance_tax_aggressive': {
        'en': 'Aggressive tax optimization without governance commitments — '
              'raises moderate stakeholder concerns.',
        'zh-CN': '激进的税务筹划缺乏相应的治理承诺——引发利益相关者的中度关切。',
    },
    # W-CE2-06: `game_creation` names every team's starting platform
    # "<team> Base Platform" in English and stores it. The stored name is left
    # alone -- this is how the generated default reads to a Chinese student.
    'platform_base_name': {'en': '{team} Base Platform',
                           'zh-CN': '{team}基础平台'},
    'research_no_competitor': {'en': 'None', 'zh-CN': '无'},
    'research_opportunity_growing_uncaptured': {
        'en': 'Growing segment you’re not capturing. Investigate fit gaps.',
        'zh-CN': '该细分市场正在增长，但您尚未获取份额。请排查契合度差距。',
    },
    'research_opportunity_lead_eroding': {
        'en': 'Your lead may be eroding. Check competitor moves.',
        'zh-CN': '您的领先地位可能正在削弱。请关注竞争对手动向。',
    },
    'research_opportunity_underserved': {
        'en': 'Large underserved segment. First-mover advantage available.',
        'zh-CN': '大型且服务不足的细分市场，具备先发优势。',
    },
    'research_opportunity_high_margin_mismatch': {
        'en': 'High-margin segment. Your capabilities may not match their expectations.',
        'zh-CN': '高利润细分市场，但您的能力可能不符合其期望。',
    },
    'research_opportunity_price_competition': {
        'en': 'Dominated by price competition. Margins thin.',
        'zh-CN': '价格竞争激烈，利润率微薄。',
    },
    'research_opportunity_protect_expand': {
        'en': 'Growing segment where you have strong fit. Protect and expand.',
        'zh-CN': '您在该增长细分市场契合度高。请巩固并扩大。',
    },
    # The same rule as `equity_exceeds_funding_need`, in the detailed form the
    # engine already recorded. The English rendering is byte-identical to the
    # sentence `funding_need.describe` built before CRV2-12, so the refusal an
    # instructor can reproduce from an engine record did not change; only a
    # Chinese rendering was added beside it.
    'equity_exceeds_funding_need_detail': {
        'en': '{team}: equity raise of {requested} exceeds the funding shortfall of {maximum} (eligible uses {eligible} less available funding {available}: opening cash {opening} plus new debt {debt}). Equity may finance a genuine current-round shortfall; it may not create surplus cash or fund dividends.',
        'zh-CN': '{team}：新增股权融资 {requested} 超过资金缺口 {maximum}（合格用途 {eligible} 减去可用资金 {available}：期初现金 {opening} 加新增借款 {debt}）。股权融资只能用于弥补本回合真实的资金缺口，不能用于创造盈余现金或支付股利。',
    },
    # -- Refusals outside the decision forms (the 2026-09-21 remainder) -------
    # Login, communications, organisation structure, onboarding, advisors and
    # the legacy team routes refused in English only, several by naming a
    # storage field. A sentence here never names one: where the page, not the
    # student, left something out, the student is told to reload, which is the
    # only thing they can do about it.
    'login_username_required': {
        'en': 'Username is required.',
        'zh-CN': '请输入用户名。',
    },
    'login_password_required': {
        'en': 'Password is required.',
        'zh-CN': '请输入密码。',
    },
    'login_invalid': {
        'en': 'Invalid username or password.',
        'zh-CN': '用户名或密码不正确。',
    },
    'login_no_password': {
        'en': 'No password is set for this account. Please ask your instructor to reset it.',
        'zh-CN': '该账号尚未设置密码。请联系教师为您重置密码。',
    },
    'login_no_team': {
        'en': 'Your account has not been assigned to a team yet. Please contact your instructor.',
        'zh-CN': '您的账号尚未分配到团队。请联系教师。',
    },
    'account_not_found': {
        'en': 'Your account could not be found. Sign in again.',
        'zh-CN': '未找到您的账号。请重新登录。',
    },
    'language_unsupported': {
        'en': 'That language is not available. Choose English or Chinese.',
        'zh-CN': '不支持该语言。请选择英文或中文。',
    },
    'request_incomplete': {
        'en': 'The page sent an incomplete request, so nothing was done. Reload the page and try again.',
        'zh-CN': '页面发送的请求不完整，因此未执行任何操作。请刷新页面后重试。',
    },
    'game_not_found': {
        'en': 'This game could not be found. Reload the page and try again.',
        'zh-CN': '未找到该游戏。请刷新页面后重试。',
    },
    'team_not_found': {
        'en': 'This team could not be found. Reload the page and try again.',
        'zh-CN': '未找到该团队。请刷新页面后重试。',
    },
    'game_or_team_not_found': {
        'en': 'This game or team could not be found. Reload the page and try again.',
        'zh-CN': '未找到该游戏或团队。请刷新页面后重试。',
    },
    'instructor_write_required': {
        'en': 'Only an instructor can make this change.',
        'zh-CN': '只有教师可以进行此更改。',
    },
    'team_access_denied': {
        'en': 'You do not have access to this team.',
        'zh-CN': '您无权访问该团队。',
    },
    'no_active_round': {
        'en': 'This game has no round in progress yet.',
        'zh-CN': '该游戏目前没有进行中的回合。',
    },
    'decisions_locked': {
        'en': 'Decisions are locked for this round.',
        'zh-CN': '本回合的决策已锁定。',
    },
    'communication_already_submitted': {
        'en': 'This communication has already been submitted and cannot be submitted again.',
        'zh-CN': '该沟通已提交，不能再次提交。',
    },
    'communication_empty': {
        'en': 'Write the communication before submitting it.',
        'zh-CN': '请先撰写沟通内容，然后再提交。',
    },
    'communication_over_word_limit': {
        'en': 'This communication is over the word limit. The maximum is {limit} words and yours has {count}.',
        'zh-CN': '该沟通超出字数上限。上限为 {limit} 词，您的内容为 {count} 词。',
    },
    'org_structure_not_found': {
        'en': 'That structure is not available in this game. Reload the page and choose again.',
        'zh-CN': '该架构在本游戏中不可用。请刷新页面后重新选择。',
    },
    'org_structure_same': {
        'en': 'Your team already uses this structure.',
        'zh-CN': '您的团队已在使用该架构。',
    },
    'org_structure_transition_active': {
        'en': 'Your team is still in transition to its current structure, so it cannot switch again yet.',
        'zh-CN': '您的团队仍处于向当前架构过渡的阶段，暂时无法再次切换。',
    },
    'org_structure_unaffordable': {
        'en': 'Insufficient cash. This switch would take committed spend to {committed}, against {cash} of cash.',
        'zh-CN': '现金不足。此次切换会使承诺支出达到 {committed}，而可用现金为 {cash}。',
    },
    'framework_required': {
        'en': 'Choose a framework before saving the analysis.',
        'zh-CN': '请先选择分析框架，然后再保存。',
    },
    'analysis_saved': {
        'en': 'Analysis saved.',
        'zh-CN': '分析已保存。',
    },
    'forecast_scenario_saved': {
        'en': 'Scenario saved.',
        'zh-CN': '情景已保存。',
    },
    'forecast_no_round': {
        'en': 'No round found.',
        'zh-CN': '未找到回合。',
    },
    'forecast_no_draft': {
        'en': 'No draft decisions yet.',
        'zh-CN': '尚无决策草稿。',
    },
    'enrollment_not_found': {
        'en': 'No active enrollment was found for your account. Please contact your instructor.',
        'zh-CN': '未找到您的有效注册记录。请联系教师。',
    },
    'persona_reply_required': {
        'en': 'Type your reply before sending it.',
        'zh-CN': '请先输入回复内容，然后再发送。',
    },
    'persona_question_required': {
        'en': 'Type your question before sending it.',
        'zh-CN': '请先输入问题，然后再发送。',
    },
    'persona_message_not_found': {
        'en': 'That message could not be found. Reload the page and try again.',
        'zh-CN': '未找到该消息。请刷新页面后重试。',
    },
    'persona_message_wrong_team': {
        'en': 'That message does not belong to your team.',
        'zh-CN': '该消息不属于您的团队。',
    },
    'persona_reply_limit': {
        'en': 'This conversation has reached its maximum of {maximum} replies.',
        'zh-CN': '本次对话已达到 {maximum} 条回复的上限。',
    },
    'persona_consultation_limit': {
        'en': 'Your team has used all {maximum} advisor consultations for this round.',
        'zh-CN': '您的团队已用完本回合的 {maximum} 次顾问咨询。',
    },
    'persona_thread_unknown': {
        'en': 'The advisor for this conversation could not be identified, so your reply was not sent.',
        'zh-CN': '无法确定本次对话的顾问，因此您的回复未发送。',
    },
    'persona_unavailable': {
        'en': 'The advisor is temporarily unavailable. Try again shortly.',
        'zh-CN': '顾问暂时无法回复。请稍后重试。',
    },
    'persona_invalid': {
        'en': 'That advisor is not available. Choose an advisor from the list.',
        'zh-CN': '该顾问不可用。请从列表中选择一位顾问。',
    },
    'platform_without_team': {
        'en': 'This platform does not belong to a team, so its development cannot be accelerated.',
        'zh-CN': '该平台不属于任何团队，因此无法加速其开发。',
    },
    'platform_in_development': {
        'en': 'Platform "{platform}" is still in development. {remaining} round(s) remaining.',
        'zh-CN': '平台“{platform}”仍在开发中，还需 {remaining} 个回合。',
    },
    'platform_not_developing': {
        'en': 'Platform is not in development.',
        'zh-CN': '该平台不在开发中。',
    },
    'platform_already_ready': {
        'en': 'Platform is already ready.',
        'zh-CN': '该平台已开发完成。',
    },
    'acceleration_unaffordable': {
        'en': 'Insufficient budget. Need {cost}, have {remaining}.',
        'zh-CN': '预算不足。需要 {cost}，可用 {remaining}。',
    },
    'program_cap_reached': {
        'en': 'Program cap reached ({active}/{maximum}). Deactivate a program before adding another.',
        'zh-CN': '已达到项目数量上限（{active}/{maximum}）。请先停用一个项目，然后再添加。',
    },
    'program_budget_overage': {
        'en': 'This will exceed your Program budget by {overage}. The overage will be financed as a loan at {rate} interest per round.',
        'zh-CN': '这将使项目预算超支 {overage}。超支部分将通过贷款解决，每回合利率为 {rate}。',
    },
    'resource_query_required': {
        'en': 'Type what you are looking for before searching.',
        'zh-CN': '请先输入要查找的内容，然后再搜索。',
    },
    # The governance page's standing notices about the team's own position.
    # They are not refusals, but they are sentences a student reads, and they
    # were English f-strings in the view. `{pools}` and `{markets}` are lists
    # joined in the sentence's own language.
    'governance_notice_pay_transparency': {
        'en': 'Your {pools} salary is Below Market. Pay transparency is exposing the gap — turnover increased +5%. Raise salaries to Market Rate or above to resolve.',
        'zh-CN': '您的{pools}薪酬低于市场水平。薪酬透明使这一差距暴露出来——离职率上升 5%。请将薪酬提高到市场水平或以上以解决此问题。',
    },
    'governance_notice_anti_corruption': {
        'en': 'You have JV partnerships in {markets}. Anti-corruption monitoring adds $100K/round per JV market.',
        'zh-CN': '您在{markets}设有合资企业。反腐败监控会使每个合资市场每回合增加 $100K 的成本。',
    },
    'governance_notice_supply_chain_audit': {
        'en': 'You use contract manufacturing in {markets}. Audit may expose labor concerns (15% probability per round).',
        'zh-CN': '您在{markets}使用代工生产。审计可能暴露劳工问题（每回合 15% 的概率）。',
    },
    'governance_notice_greenwashing': {
        'en': 'Total ESG investment is only {total}. Reporting without substance is seen as greenwashing. Increase environmental/social investment above $1M or remove this commitment.',
        'zh-CN': '目前 ESG 总投入仅为 {total}。缺乏实质内容的报告会被视为“漂绿”。请将环境/社会投入提高到 $1M 以上，或取消此项承诺。',
    },
    'talent_pool_rd': {
        'en': 'R&D',
        'zh-CN': '研发',
    },
    'talent_pool_commercial': {
        'en': 'Commercial',
        'zh-CN': '商务',
    },
    'talent_pool_operations': {
        'en': 'Operations',
        'zh-CN': '运营',
    },
    'list_separator': {
        'en': ', ',
        'zh-CN': '、',
    },
}


def language_for_request(request):
    """Return the supported language for a request, defaulting safely to EN.

    Guarded: login and the scope middleware refuse before any user is known,
    and a refusal must never become a 500 because its language could not be
    read.
    """
    try:
        return 'zh-CN' if get_user_language(request) == 'zh-CN' else 'en'
    except Exception:
        return 'en'


# Values a service attaches to a refusal so the view can re-render it in the
# request's language. Never sent to the client.
_REFUSAL_VALUES = '_refusal_values'


def participant_refusal(request, key, *, field='error', **values):
    """The response body for a participant-facing refusal: sentence + code."""
    return {
        field: participant_message(
            key, language=language_for_request(request), **values),
        'code': key,
    }


def service_refusal(key, **values):
    """A refusal raised below the view, where no request (so no language) is known.

    It carries the English sentence, so a caller that is not a view still reads
    something sensible, and the key and values `localise_refusal` needs.
    """
    return {'error': participant_message(key, language='en', **values),
            'code': key, _REFUSAL_VALUES: values}


def localise_refusal(request, result):
    """Re-render a `service_refusal` in the request's language, in place."""
    values = result.pop(_REFUSAL_VALUES, None)
    if values is not None and result.get('code') in MESSAGES:
        result['error'] = participant_message(
            result['code'], language=language_for_request(request), **values)
    return result


SUPPORTED_LANGUAGES = ('en', 'zh-CN')


def language_for_team(team, request):
    """The language a team is spoken to in (R43, 2026-09-21).

    The team's language governs what a route says to a student -- answers and
    refusals alike -- so one screen never speaks two languages. It is the
    language of the team's first active enrolment that states one, which is
    what `get_team_language` has always meant. The request's language is the
    fallback only where the team states none, or states one the catalogue has
    no entry for: an unsupported value must never raise out of a refusal.
    """
    from core.models.course import Enrollment
    from django.db import transaction
    try:
        with transaction.atomic():
            stated = (Enrollment.objects
                      .filter(team_id=team.id, is_active=True)
                      .exclude(language='').order_by('pk')
                      .values_list('language', flat=True).first())
    except Exception:
        stated = None
    return stated if stated in SUPPORTED_LANGUAGES else language_for_request(request)


def language_for_participant(team, request):
    """The language of the one student a sentence is addressed to (W-CE2-05).

    R43 ruled that the team's language governs what a student is told, so one
    screen never speaks two languages. It did not settle *whose* language the
    team's is when members differ, and `language_for_team` answers "the first
    active enrolment's" -- which leaves the choice unreachable for every member
    but the first. In the second walkthrough a Chinese-reading student whose
    team-mate had enrolled first was answered in English however often they
    chose 中文.

    So a sentence addressed to **one** student -- a refusal, the answer to that
    student's own action -- follows that student's own stated language where
    the request identifies them. A sentence written once for the **whole team**
    (stored narrative prose, round briefings, persona messages) keeps
    `language_for_team`.

    What is read is the student's own *enrolment*, which the in-game switch and
    the sign-in record through `PUT /api/user/preferences/`; the request's
    header still does not govern, as R43 decided. Where the request identifies
    no student, where that student has no active enrolment on this team, or
    where they state no supported language, this is exactly
    `language_for_team` -- so when a team's members agree, nothing changes.
    """
    from core.models.course import Enrollment
    from django.db import transaction
    user = getattr(request, 'user', None)
    user_id = getattr(user, 'id', None) or getattr(user, 'user_id', None)
    if user_id is not None:
        try:
            # Savepoint for the same reason `language_for_team` takes one: a
            # query failure must not poison the caller's transaction, and a
            # refusal must never become a 500 over its own language.
            with transaction.atomic():
                stated = (Enrollment.objects
                          .filter(user_id=user_id, team_id=team.id,
                                  is_active=True)
                          .exclude(language='').order_by('pk')
                          .values_list('language', flat=True).first())
        except Exception:
            stated = None
        if stated in SUPPORTED_LANGUAGES:
            return stated
    return language_for_team(team, request)


# The English suffix `game_creation` gives every team's starting platform.
# Named here so the writer and the reader cannot drift apart (W-CE2-06).
BASE_PLATFORM_SUFFIX_EN = 'Base Platform'


def market_label(market, language='en'):
    """A market's name as a participant reads it, or the all-markets label.

    `results_api` printed the literal 'Global' for an event with no target
    market, on a Chinese screen as well as an English one (W-CE2-06).
    """
    from core.utils.localization import get_localized_field
    if market is None:
        return participant_message('research_global', language=language)
    return get_localized_field(market, 'name', language)


def platform_display_name(team_platform, language='en', *, team_name=None):
    """A team platform's name as a participant reads it.

    A name the team chose is the team's own and is never translated. The name
    `game_creation` generates for the starting platform is not the team's: it
    is English text the platform wrote, and it reached a Chinese Products
    table as "… Base Platform" (W-CE2-06). Only that generated default is
    rendered; nothing stored changes, so no game needs migrating.

    `team_name` is passed by callers that already hold the team, so reading it
    costs no extra query per product row.
    """
    from core.utils.localization import get_localized_field
    name = (getattr(team_platform, 'name', '') or '').strip()
    generation = getattr(team_platform, 'platform_generation', None)
    if not name:
        return get_localized_field(generation, 'name', language) if generation else ''
    if team_name is None:
        team = getattr(team_platform, 'team', None)
        team_name = getattr(team, 'name', None)
    if team_name and name == f'{team_name} {BASE_PLATFORM_SUFFIX_EN}':
        return participant_message(
            'platform_base_name', language=language, team=team_name)
    return name


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


def round_status_label(status, language='en'):
    """A round's status as a participant reads it, never the stored token.

    An unknown status falls back to the stored value rather than raising: a
    status this catalogue has not been taught is a wording gap, and refusing
    the request over it would turn a language defect into an outage. The
    static check `backend/scripts/check-participant-strings` fails the build
    when `Round.STATUS_CHOICES` gains a value that is not labelled here, so the
    fallback cannot quietly become the normal path.
    """
    labels = ROUND_STATUS_LABELS.get(status)
    if labels is None:
        return status
    return labels.get(language, labels['en'])


def serializer_language(serializer_field):
    """Read the request language from a DRF field validator's serializer."""
    root = getattr(serializer_field, 'root', None)
    context = getattr(root, 'context', {}) or {}
    return language_for_request(context.get('request'))
