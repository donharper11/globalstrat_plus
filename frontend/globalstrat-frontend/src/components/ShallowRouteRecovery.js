import React from "react";
import { useLocation, useNavigate, Navigate } from "react-router-dom";
import { Result, Button, Spin } from "antd";
import { useGame } from "../contexts/GameContext";
import { useTranslation } from "react-i18next";

// GSP-R1-01: Shallow decision slugs a student might reach via direct URL entry
// or a dashboard shortcut. These must resolve into the active game/team nested
// route. Slugs + targets are verified against Sidebar.js nav (the source of truth):
//   decision slugs -> /games/:g/teams/:t/decisions/<slug>
//   forecast       -> /games/:g/teams/:t/forecast   (NOT under /decisions/)
const DECISION_SLUGS = [
  "sourcing", "logistics", "trade-finance", "inventory", "rd", "products",
  "marketing", "corporate-strategy", "market-strategy", "finance",
  "communications", "summary",
];

function resolveNestedTarget(pathname, gameId, teamId) {
  if (!gameId || !teamId) return null;
  const slug = pathname.replace(/^\/+/, "").replace(/\/+$/, "");
  const base = `/games/${gameId}/teams/${teamId}`;
  if (DECISION_SLUGS.includes(slug)) return `${base}/decisions/${slug}`;
  if (slug === "forecast") return `${base}/forecast`;
  return null;
}

// Catch-all for the student layout: never render a shell-only page.
// - A known shallow decision slug redirects into the active nested route.
// - Anything else shows an honest recovery screen with one click back into play.
export default function ShallowRouteRecovery() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { gameId, teamId, loading } = useGame();

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: "80px 0" }}>
        <Spin size="large" />
      </div>
    );
  }

  const target = resolveNestedTarget(pathname, gameId, teamId);
  if (target) return <Navigate to={target} replace />;

  return (
    <Result
      status="404"
      title={t('route_recovery.title')}
      subTitle={
        gameId && teamId
          ? t('route_recovery.active_help')
          : t('route_recovery.missing_help')
      }
      extra={
        <Button type="primary" onClick={() => navigate("/")}>
          {t('route_recovery.open_game')}
        </Button>
      }
    />
  );
}
