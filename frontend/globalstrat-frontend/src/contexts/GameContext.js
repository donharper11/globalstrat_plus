import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useAuth } from '../AuthContext';
import { getFinanceContext } from '../api/decisions';
import { getRounds } from '../api/auth';

const GameContext = createContext(null);

export const GameProvider = ({ children }) => {
  const { user } = useAuth();
  const [game, setGame] = useState(null);
  const [team, setTeam] = useState(null);
  const [currentRound, setCurrentRound] = useState(null);
  const [roundStatus, setRoundStatus] = useState(null);
  const [budgets, setBudgets] = useState(null);
  const [sidebarLabels, setSidebarLabels] = useState({});
  const [loading, setLoading] = useState(true);

  const gameId = user?.game_id;
  const teamId = user?.team_id;
  const scenarioId = user?.scenario_id;

  const refreshBudgets = useCallback(async () => {
    if (!gameId || !teamId) return;
    try {
      const res = await getFinanceContext(gameId, teamId);
      setBudgets(res.data?.budget_status || null);
    } catch { /* ignore */ }
  }, [gameId, teamId]);

  const refreshRoundInfo = useCallback(async () => {
    if (!gameId) return;
    try {
      const res = await getRounds(gameId);
      const rounds = res.data?.results || res.data || [];
      // Find the current active round — prefer 'open' first, then lowest pending/in_progress
      const sorted = [...rounds].sort((a, b) => a.round_number - b.round_number);
      const open = sorted.find(r => r.status === 'open');
      const active = open || sorted.find(r => ['pending', 'in_progress'].includes(r.status));
      const processed = rounds.filter(r => r.status === 'processed');
      if (active) {
        setCurrentRound(active.round_number);
        setRoundStatus(active.status);
      } else if (processed.length > 0) {
        const last = processed.sort((a, b) => b.round_number - a.round_number)[0];
        setCurrentRound(last.round_number);
        setRoundStatus('processed');
      } else if (rounds.length > 0) {
        setCurrentRound(rounds[0].round_number || 1);
        setRoundStatus(rounds[0].status || 'pending');
      } else {
        setCurrentRound(1);
        setRoundStatus('pending');
      }
    } catch {
      setCurrentRound(1);
      setRoundStatus('pending');
    }
  }, [gameId]);

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    setGame({ id: user.game_id, name: user.game_name });
    setTeam({ id: user.team_id, name: user.team_name });
    if (user.sidebar_labels) setSidebarLabels(user.sidebar_labels);
    Promise.all([refreshRoundInfo(), refreshBudgets()])
      .finally(() => setLoading(false));
  }, [user, refreshRoundInfo, refreshBudgets]);

  return (
    <GameContext.Provider value={{
      game, team, currentRound, roundStatus, budgets, loading,
      gameId, teamId, scenarioId, sidebarLabels,
      refreshBudgets, refreshRoundInfo,
    }}>
      {children}
    </GameContext.Provider>
  );
};

export const useGame = () => {
  const ctx = useContext(GameContext);
  if (!ctx) throw new Error('useGame must be used within GameProvider');
  return ctx;
};
