from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views.decisions import (
    DecisionSubmissionView, DecisionPartialUpdateView,
    DecisionLockView, DecisionUnlockView,
    DecisionSummaryView,
    RDContextView, ProductContextView, MarketingContextView,
    StrategyContextView, FinanceContextView, TalentContextView,
)
from .views.results_api import (
    RoundResultsView, LeaderboardView, LeaderboardHistoryView,
    CompetitorIntelView, InstructorDashboardView,
    InstructorAdvanceRoundView, InstructorInjectEventView,
    InstructorExtendDeadlineView, InstructorResearchQueriesView,
    InstructorEventTemplatesView, InstructorTeamBriefingsView,
    InstructorTeamDecisionsView,
)
from .views.scorecard import BalancedScorecardView
from .views.research_reports import ResearchReportsView
from .views.instructor_alerts import (
    InstructorAlertsView, InstructorAlertAcknowledgeView,
    InstructorAlertSummaryView, TeamChangesView,
)
from .views.cc15_views import (
    IndustryNewsView, ResearchQueriesListView,
    FrameworkAnalysisView, FrameworkAnalysisHistoryView, EntryMatrixDataView,
    FinancialReportsHistoryView,
    ForecastView, ForecastScenarioView,
)
from .views.strategic_impact import StrategicImpactView
from .views.investor_relations import InvestorRelationsView
from core.views.briefing import LatestBriefingView, RoundBriefingView, BriefingReadView
from core.views.cc31_views import (
    TalentAllocationContextView, ComplianceContextView, MarketLocalizationView,
)
from core.views.cc31h_views import TickerView
from core.views.cc31j_views import GovernanceContextView
from core.views.cc32a_views import (
    CommunicationAssignmentsView, CommunicationDraftView,
    CommunicationSubmitView, CommunicationHistoryView,
    InstructorCommunicationsView,
)
from core.views.cc32b_views import OrgStructureContextView
from core.views.cc32c_views import TaxStructureContextView
from core.views.cc32d_views import AllianceStateView
from core.views.cc32f_views import GovernmentRelationsView
from core.views.cc32h_views import RoundStatusView
from core.views.team_config import (
    InstructorTeamConfigView, InstructorRandomizeHomeMarketsView,
)
from core.views.scenario_views import (
    ScenarioListView, ScenarioDetailView, GameListView, GameCreateView,
    GameTeamsView, GameActivateView, GamePauseView, GameResumeView, GameResetView,
    GameArchiveView, GameDeleteView,
)
from core.views.sc_views import (
    SourcingView, LogisticsView, TradeFinanceView, InventoryView,
    ScenarioSuppliersView, ScenarioLanesView,
    ScenarioTradeFinanceInstrumentsView, ScenarioComplianceRegimesView,
    ResilienceScoreView, HedgePositionsView, SCEventsView,
)

from core.views.onboarding import OnboardingDataView, OnboardingCompleteView

from .views import (
    # Core
    TeamViewSet, UserViewSet, RoundViewSet,
    SimulationStateViewSet, SimulationSettingsViewSet,
    SimulationParametersViewSet, DashboardViewSet,
    # Round deadline management
    RoundLockView, RoundUnlockView, RoundExtendView,
    RoundScheduleSetView, BulkScheduleView,
    DecisionStatusView, SendReminderView,
    # Programs (placeholder — will become platforms/products in CC-2)
    ProgramViewSet, ProgramTypeViewSet,
    ProgramPortfolioViewSet, ProgramFeatureViewSet,
    DecisionViewSet,
    # Scoring
    ScoreTypeViewSet, ScoreViewSet,
    LeaderboardViewSet, LeaderboardMetricViewSet,
    TeamPerformanceViewSet,
    # Financials
    IncomeStatementViewSet, BalanceSheetViewSet, CashFlowViewSet,
    TeamResourcesViewSet,
    FinancialRevenueViewSet, FinancialExpenseViewSet,
    NewSalesByRoundViewSet,
    # Events
    TriggeredEventViewSet,
    FireEventsViewSet,
    # Instructor
    InstructorActionViewSet, InstructorEvaluationViewSet,
    InstructorNoteViewSet, InstructorFeedbackTemplateViewSet,
    InstructorScenarioCustomizationViewSet,
    # Gamification
    AchievementViewSet, GamificationBadgeViewSet,
    PlayerProgressViewSet, TeamAchievementViewSet,
    TeamBadgeViewSet, QicoinView,
    # Messaging
    MessageViewSet, MessageResponseViewSet,
    MessageThreadViewSet,
    NotificationLogViewSet, TeamNotificationViewSet,
    # Persona Engine
    PersonaReplyView, PersonaConsultView, PersonaListView,
    ThreadMessagesView, ConsultationUsageView,
    # Resources (Textbook KB)
    ResourceSearchView, ResourceContentView,
    # Auth
    LoginView, CurrentUserView, LanguagePreferenceView,
    # Events & RAG (CC-7)
    ActiveEventsView, EventHistoryView, ResearchQueryView,
    # Course Management
    CourseViewSet, SectionViewSet,
    RosterViewSet, TeamManagementView, SimulationControlView,
    RoundScheduleView, GameRoundScheduleView,
    # Grading
    GradingRubricViewSet, GradingRubricCategoryViewSet,
    GradingComponentMappingViewSet, TeamGradeViewSet,
    StudentGradeAdjustmentViewSet,
    SeedRubricView, CalculateGradesView, OverrideGradeView,
    StudentGradesView, ComponentLabelsView,
    ExportTeamGradesCsvView, ExportStudentGradesCsvView,
)

router = DefaultRouter()

# ---- Course Management ----
router.register(r'courses', CourseViewSet, basename='courses')
router.register(r'sections', SectionViewSet, basename='sections')

# ---- Core ----
router.register(r'teams', TeamViewSet, basename='teams')
router.register(r'users', UserViewSet, basename='users')
router.register(r'rounds', RoundViewSet, basename='rounds')
router.register(r'simulation-state', SimulationStateViewSet, basename='simulation-state')
router.register(r'simulation-settings', SimulationSettingsViewSet, basename='simulation-settings')
router.register(r'simulation-parameters', SimulationParametersViewSet, basename='simulation-parameters')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

# ---- Programs (placeholder — platforms/products in CC-2) ----
router.register(r'programs', ProgramViewSet, basename='programs')
router.register(r'program-types', ProgramTypeViewSet, basename='program-types')
router.register(r'program-portfolios', ProgramPortfolioViewSet, basename='program-portfolios')
router.register(r'program-features', ProgramFeatureViewSet, basename='program-features')
router.register(r'decisions', DecisionViewSet, basename='decisions')

# ---- Scoring ----
router.register(r'score-types', ScoreTypeViewSet, basename='score-types')
router.register(r'scores', ScoreViewSet, basename='scores')
router.register(r'leaderboard', LeaderboardViewSet, basename='leaderboard')
router.register(r'leaderboard-metrics', LeaderboardMetricViewSet, basename='leaderboard-metrics')
router.register(r'team-performance', TeamPerformanceViewSet, basename='team-performance')

# ---- Financials ----
router.register(r'income-statements', IncomeStatementViewSet, basename='income-statements')
router.register(r'balance-sheets', BalanceSheetViewSet, basename='balance-sheets')
router.register(r'cash-flows', CashFlowViewSet, basename='cash-flows')
router.register(r'team-resources', TeamResourcesViewSet, basename='team-resources')
router.register(r'financial-revenue', FinancialRevenueViewSet, basename='financial-revenue')
router.register(r'financial-expenses', FinancialExpenseViewSet, basename='financial-expenses')
router.register(r'new-sales-by-round', NewSalesByRoundViewSet, basename='new-sales-by-round')

# ---- Events ----
router.register(r'triggered-events', TriggeredEventViewSet, basename='triggered-events')
router.register(r'fire-events', FireEventsViewSet, basename='fire-events')

# ---- Instructor ----
router.register(r'instructor-actions', InstructorActionViewSet, basename='instructor-actions')
router.register(r'instructor-evaluations', InstructorEvaluationViewSet, basename='instructor-evaluations')
router.register(r'instructor-notes', InstructorNoteViewSet, basename='instructor-notes')
router.register(r'instructor-feedback-templates', InstructorFeedbackTemplateViewSet, basename='instructor-feedback-templates')
router.register(r'instructor-scenario-customizations', InstructorScenarioCustomizationViewSet, basename='instructor-scenario-customizations')

# ---- Gamification ----
router.register(r'achievements', AchievementViewSet, basename='achievements')
router.register(r'gamification-badges', GamificationBadgeViewSet, basename='gamification-badges')
router.register(r'player-progress', PlayerProgressViewSet, basename='player-progress')
router.register(r'team-achievements', TeamAchievementViewSet, basename='team-achievements')
router.register(r'team-badges', TeamBadgeViewSet, basename='team-badges')

# ---- Messaging ----
router.register(r'messages', MessageViewSet, basename='messages')
router.register(r'message-responses', MessageResponseViewSet, basename='message-responses')
router.register(r'message-threads', MessageThreadViewSet, basename='message-threads')
router.register(r'notification-logs', NotificationLogViewSet, basename='notification-logs')
router.register(r'team-notifications', TeamNotificationViewSet, basename='team-notifications')

# ---- Grading ----
router.register(r'grading-rubrics', GradingRubricViewSet, basename='grading-rubrics')
router.register(r'grading-categories', GradingRubricCategoryViewSet, basename='grading-categories')
router.register(r'grading-components', GradingComponentMappingViewSet, basename='grading-components')
router.register(r'team-grades', TeamGradeViewSet, basename='team-grades')
router.register(r'student-grade-adjustments', StudentGradeAdjustmentViewSet, basename='student-grade-adjustments')

urlpatterns = [
    path('', include(router.urls)),
    # ---- Auth ----
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/me/', CurrentUserView.as_view(), name='auth-me'),
    path('user/preferences/', LanguagePreferenceView.as_view(), name='user-preferences'),
    # ---- Onboarding ----
    path('onboarding/', OnboardingDataView.as_view(), name='onboarding-data'),
    path('onboarding/complete/', OnboardingCompleteView.as_view(), name='onboarding-complete'),
    # ---- QICOIN ----
    path('qicoin/', QicoinView.as_view(), name='qicoin'),
    # ---- Persona Engine ----
    path('persona/reply/', PersonaReplyView.as_view(), name='persona-reply'),
    path('persona/consult/', PersonaConsultView.as_view(), name='persona-consult'),
    path('persona/list/', PersonaListView.as_view(), name='persona-list'),
    path('persona/thread/<int:thread_root_id>/', ThreadMessagesView.as_view(), name='persona-thread'),
    path('persona/usage/', ConsultationUsageView.as_view(), name='persona-usage'),
    # ---- Resources (Textbook KB) ----
    path('resources/search/', ResourceSearchView.as_view(), name='resources-search'),
    path('resources/content/', ResourceContentView.as_view(), name='resources-content'),
    # ---- Course / Section / Roster / Team / Instance Management ----
    path('roster/', RosterViewSet.as_view(), name='roster'),
    path('team-management/', TeamManagementView.as_view(), name='team-management'),
    path('simulation-control/', SimulationControlView.as_view(), name='simulation-control'),
    path('round-schedule/', RoundScheduleView.as_view(), name='round-schedule'),
    # ---- Round Deadline Management ----
    path('rounds/<int:round_id>/lock/', RoundLockView.as_view(), name='round-lock'),
    path('rounds/<int:round_id>/unlock/', RoundUnlockView.as_view(), name='round-unlock'),
    path('rounds/<int:round_id>/extend/', RoundExtendView.as_view(), name='round-extend'),
    path('rounds/<int:round_id>/schedule/', RoundScheduleSetView.as_view(), name='round-schedule-set'),
    path('rounds/<int:round_id>/decision-status/', DecisionStatusView.as_view(), name='round-decision-status'),
    path('rounds/<int:round_id>/send-reminder/', SendReminderView.as_view(), name='round-send-reminder'),
    path('rounds/current/my-status/', DecisionStatusView.as_view(), name='my-decision-status'),
    path('instances/<int:instance_id>/bulk-schedule/', BulkScheduleView.as_view(), name='bulk-schedule'),
    # ---- Grading ----
    path('grades/seed-rubric/', SeedRubricView.as_view(), name='grades-seed-rubric'),
    path('grades/calculate/', CalculateGradesView.as_view(), name='grades-calculate'),
    path('grades/override/', OverrideGradeView.as_view(), name='grades-override'),
    path('grades/students/', StudentGradesView.as_view(), name='grades-students'),
    path('grades/component-labels/', ComponentLabelsView.as_view(), name='grades-component-labels'),
    path('grades/export/teams/', ExportTeamGradesCsvView.as_view(), name='grades-export-teams'),
    path('grades/export/students/', ExportStudentGradesCsvView.as_view(), name='grades-export-students'),
    # ---- Decision Submission APIs (CC-04) ----
    # NOTE: lock/, unlock/, summary/ must be before <str:decision_type>/
    path('games/<int:game_id>/teams/<int:team_id>/decisions/round/<int:round_number>/lock/',
         DecisionLockView.as_view(), name='decision-lock'),
    path('games/<int:game_id>/teams/<int:team_id>/decisions/round/<int:round_number>/unlock/',
         DecisionUnlockView.as_view(), name='decision-unlock'),
    path('games/<int:game_id>/teams/<int:team_id>/decisions/round/<int:round_number>/summary/',
         DecisionSummaryView.as_view(), name='decision-summary'),
    path('games/<int:game_id>/teams/<int:team_id>/decisions/round/<int:round_number>/<str:decision_type>/',
         DecisionPartialUpdateView.as_view(), name='decision-partial'),
    path('games/<int:game_id>/teams/<int:team_id>/decisions/round/<int:round_number>/',
         DecisionSubmissionView.as_view(), name='decision-submission'),
    # ---- Context Endpoints (CC-04) ----
    path('games/<int:game_id>/teams/<int:team_id>/context/rd/',
         RDContextView.as_view(), name='context-rd'),
    path('games/<int:game_id>/teams/<int:team_id>/context/products/',
         ProductContextView.as_view(), name='context-products'),
    path('games/<int:game_id>/teams/<int:team_id>/context/marketing/',
         MarketingContextView.as_view(), name='context-marketing'),
    path('games/<int:game_id>/teams/<int:team_id>/context/strategy/',
         StrategyContextView.as_view(), name='context-strategy'),
    path('games/<int:game_id>/teams/<int:team_id>/context/finance/',
         FinanceContextView.as_view(), name='context-finance'),
    # ---- CC-16: Talent Context ----
    path('games/<int:game_id>/teams/<int:team_id>/context/talent/',
         TalentContextView.as_view(), name='context-talent'),
    # ---- CC-16 Part B: Balanced Scorecard ----
    path('games/<int:game_id>/teams/<int:team_id>/dashboard/scorecard/',
         BalancedScorecardView.as_view(), name='dashboard-scorecard'),
    # ---- Events & RAG (CC-07) ----
    path('games/<int:game_id>/teams/<int:team_id>/events/active/',
         ActiveEventsView.as_view(), name='events-active'),
    path('games/<int:game_id>/teams/<int:team_id>/events/history/',
         EventHistoryView.as_view(), name='events-history'),
    path('games/<int:game_id>/teams/<int:team_id>/research/query/',
         ResearchQueryView.as_view(), name='research-query'),
    # ---- Results & Leaderboard (CC-10) ----
    path('games/<int:game_id>/teams/<int:team_id>/results/round/<int:round_number>/',
         RoundResultsView.as_view(), name='round-results'),
    path('games/<int:game_id>/teams/<int:team_id>/competitors/round/<int:round_number>/',
         CompetitorIntelView.as_view(), name='competitor-intel'),
    path('games/<int:game_id>/leaderboard/round/<int:round_number>/',
         LeaderboardView.as_view(), name='leaderboard-round'),
    path('games/<int:game_id>/leaderboard/history/',
         LeaderboardHistoryView.as_view(), name='leaderboard-history'),
    # ---- Instructor (CC-10) ----
    path('games/<int:game_id>/instructor/dashboard/',
         InstructorDashboardView.as_view(), name='instructor-dashboard'),
    path('games/<int:game_id>/instructor/advance-round/',
         InstructorAdvanceRoundView.as_view(), name='instructor-advance'),
    path('games/<int:game_id>/instructor/inject-event/',
         InstructorInjectEventView.as_view(), name='instructor-inject-event'),
    path('games/<int:game_id>/instructor/extend-deadline/',
         InstructorExtendDeadlineView.as_view(), name='instructor-extend'),
    path('games/<int:game_id>/instructor/research-queries/',
         InstructorResearchQueriesView.as_view(), name='instructor-queries'),
    path('games/<int:game_id>/instructor/event-templates/',
         InstructorEventTemplatesView.as_view(), name='instructor-event-templates'),
    path('games/<int:game_id>/instructor/briefings/',
         InstructorTeamBriefingsView.as_view(), name='instructor-briefings'),
    path('games/<int:game_id>/instructor/teams/<int:team_id>/decisions/',
         InstructorTeamDecisionsView.as_view(), name='instructor-team-decisions'),
    # ---- CC-15: New Feature Pages ----
    path('games/<int:game_id>/teams/<int:team_id>/news/round/<int:round_number>/',
         IndustryNewsView.as_view(), name='industry-news'),
    path('games/<int:game_id>/teams/<int:team_id>/research/queries/',
         ResearchQueriesListView.as_view(), name='research-queries-list'),
    path('games/<int:game_id>/teams/<int:team_id>/tools/analysis/',
         FrameworkAnalysisView.as_view(), name='framework-analysis'),
    path('games/<int:game_id>/teams/<int:team_id>/tools/analysis/history/',
         FrameworkAnalysisHistoryView.as_view(), name='framework-analysis-history'),
    path('games/<int:game_id>/teams/<int:team_id>/tools/entry-matrix-data/',
         EntryMatrixDataView.as_view(), name='entry-matrix-data'),
    path('games/<int:game_id>/teams/<int:team_id>/financial-reports/history/',
         FinancialReportsHistoryView.as_view(), name='financial-reports-history'),
    path('games/<int:game_id>/teams/<int:team_id>/forecast/',
         ForecastView.as_view(), name='forecast'),
    path('games/<int:game_id>/teams/<int:team_id>/forecast/scenarios/',
         ForecastScenarioView.as_view(), name='forecast-scenarios'),
    # ---- CC-21: Instructor Alerts & Team Changes ----
    path('games/<int:game_id>/instructor/alerts/',
         InstructorAlertsView.as_view(), name='instructor-alerts'),
    path('games/<int:game_id>/instructor/alerts/<int:alert_id>/acknowledge/',
         InstructorAlertAcknowledgeView.as_view(), name='instructor-alert-ack'),
    path('games/<int:game_id>/instructor/alerts/summary/',
         InstructorAlertSummaryView.as_view(), name='instructor-alert-summary'),
    path('games/<int:game_id>/teams/<int:team_id>/changes/',
         TeamChangesView.as_view(), name='team-changes'),
    # ---- CC-19: Research Reports ----
    path('games/<int:game_id>/teams/<int:team_id>/research/reports/<str:report_type>/',
         ResearchReportsView.as_view(), name='research-reports'),
    # ---- CC-24: Strategic Investment Impact ----
    path('games/<int:game_id>/teams/<int:team_id>/financial-reports/strategic-impact/',
         StrategicImpactView.as_view(), name='strategic-impact'),
    # ---- CC-26: Investor Relations ----
    path('games/<int:game_id>/teams/<int:team_id>/investor-relations/',
         InvestorRelationsView.as_view(), name='investor-relations'),
    # ---- CC-27: Strategic Briefing ----
    path('games/<int:game_id>/teams/<int:team_id>/briefing/latest/',
         LatestBriefingView.as_view(), name='briefing-latest'),
    path('games/<int:game_id>/teams/<int:team_id>/briefing/round/<int:round_number>/',
         RoundBriefingView.as_view(), name='briefing-round'),
    path('games/<int:game_id>/teams/<int:team_id>/briefing/<int:briefing_id>/read/',
         BriefingReadView.as_view(), name='briefing-read'),
    # ---- CC-31: Team Configuration (Home Market Assignment) ----
    path('games/<int:game_id>/instructor/team-config/',
         InstructorTeamConfigView.as_view(), name='instructor-team-config'),
    path('games/<int:game_id>/instructor/randomize-home-markets/',
         InstructorRandomizeHomeMarketsView.as_view(), name='instructor-randomize-home-markets'),
    # ---- CC-31A: Origin-Trust Framework ----
    path('games/<int:game_id>/teams/<int:team_id>/context/talent-allocation/',
         TalentAllocationContextView.as_view(), name='context-talent-allocation'),
    path('games/<int:game_id>/teams/<int:team_id>/context/compliance/',
         ComplianceContextView.as_view(), name='context-compliance'),
    path('games/<int:game_id>/teams/<int:team_id>/markets/<str:market_code>/localization/',
         MarketLocalizationView.as_view(), name='market-localization'),
    # ---- CC-31H: News Ticker ----
    path('games/<int:game_id>/teams/<int:team_id>/ticker/',
         TickerView.as_view(), name='news-ticker'),
    # ---- CC-31J: Governance Commitments ----
    path('games/<int:game_id>/teams/<int:team_id>/context/governance/',
         GovernanceContextView.as_view(), name='context-governance'),
    # ---- CC-32A: Stakeholder Communications ----
    path('games/<int:game_id>/teams/<int:team_id>/communications/assignments/',
         CommunicationAssignmentsView.as_view(), name='comm-assignments'),
    path('games/<int:game_id>/teams/<int:team_id>/communications/<int:assignment_id>/draft/',
         CommunicationDraftView.as_view(), name='comm-draft'),
    path('games/<int:game_id>/teams/<int:team_id>/communications/<int:assignment_id>/submit/',
         CommunicationSubmitView.as_view(), name='comm-submit'),
    path('games/<int:game_id>/teams/<int:team_id>/communications/history/',
         CommunicationHistoryView.as_view(), name='comm-history'),
    path('games/<int:game_id>/instructor/communications/<int:round_number>/',
         InstructorCommunicationsView.as_view(), name='instructor-communications'),
    # ---- CC-32B: Organizational Design ----
    path('games/<int:game_id>/teams/<int:team_id>/context/org-structure/',
         OrgStructureContextView.as_view(), name='context-org-structure'),
    # ---- CC-32C: Tax Structure ----
    path('games/<int:game_id>/teams/<int:team_id>/context/tax-structure/',
         TaxStructureContextView.as_view(), name='context-tax-structure'),
    # ---- CC-32D: AI Alliance Partners ----
    path('games/<int:game_id>/teams/<int:team_id>/alliances/',
         AllianceStateView.as_view(), name='alliance-state'),

    # ---- CC-32F: AI Government Relations ----
    path('games/<int:game_id>/teams/<int:team_id>/government-relations/',
         GovernmentRelationsView.as_view(), name='government-relations'),

    # ---- CC-32H: Round Processing Status ----
    path('games/<int:game_id>/round-status/',
         RoundStatusView.as_view(), name='round-status'),

    # ---- CC-33: Scenario Selection & Game Creation ----
    path('scenarios/', ScenarioListView.as_view(), name='scenario-list'),
    path('scenarios/<int:scenario_id>/', ScenarioDetailView.as_view(), name='scenario-detail'),
    path('games/', GameListView.as_view(), name='game-list'),
    path('games/create/', GameCreateView.as_view(), name='game-create'),
    path('games/<int:game_id>/teams/', GameTeamsView.as_view(), name='game-teams'),
    path('games/<int:game_id>/activate/', GameActivateView.as_view(), name='game-activate'),
    path('games/<int:game_id>/pause/', GamePauseView.as_view(), name='game-pause'),
    path('games/<int:game_id>/resume/', GameResumeView.as_view(), name='game-resume'),
    path('games/<int:game_id>/reset/', GameResetView.as_view(), name='game-reset'),
    path('games/<int:game_id>/archive/', GameArchiveView.as_view(), name='game-archive'),
    path('games/<int:game_id>/delete/', GameDeleteView.as_view(), name='game-delete'),
    path('games/<int:game_id>/round-schedule/', GameRoundScheduleView.as_view(), name='game-round-schedule'),

    # ---- CC-04: Supply Chain Decision Endpoints ----
    path('games/<int:game_id>/teams/<int:team_id>/sc/round/<int:round_number>/sourcing/',
         SourcingView.as_view(), name='sc-sourcing'),
    path('games/<int:game_id>/teams/<int:team_id>/sc/round/<int:round_number>/logistics/',
         LogisticsView.as_view(), name='sc-logistics'),
    path('games/<int:game_id>/teams/<int:team_id>/sc/round/<int:round_number>/trade-finance/',
         TradeFinanceView.as_view(), name='sc-trade-finance'),
    path('games/<int:game_id>/teams/<int:team_id>/sc/round/<int:round_number>/inventory/',
         InventoryView.as_view(), name='sc-inventory'),

    # ---- CC-04: Supply Chain Scenario Content ----
    path('scenarios/<int:scenario_id>/suppliers/',
         ScenarioSuppliersView.as_view(), name='sc-suppliers'),
    path('scenarios/<int:scenario_id>/lanes/',
         ScenarioLanesView.as_view(), name='sc-lanes'),
    path('scenarios/<int:scenario_id>/trade-finance-instruments/',
         ScenarioTradeFinanceInstrumentsView.as_view(), name='sc-trade-finance-instruments'),
    path('scenarios/<int:scenario_id>/compliance-regimes/',
         ScenarioComplianceRegimesView.as_view(), name='sc-compliance-regimes'),

    # ---- CC-04: Supply Chain State Retrieval ----
    path('games/<int:game_id>/teams/<int:team_id>/sc/round/<int:round_number>/resilience-score/',
         ResilienceScoreView.as_view(), name='sc-resilience-score'),
    path('games/<int:game_id>/teams/<int:team_id>/sc/hedge-positions/',
         HedgePositionsView.as_view(), name='sc-hedge-positions'),
    path('games/<int:game_id>/teams/<int:team_id>/sc/round/<int:round_number>/sc-events/',
         SCEventsView.as_view(), name='sc-events'),
]
