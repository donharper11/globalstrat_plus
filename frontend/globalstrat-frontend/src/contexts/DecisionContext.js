import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { useGame } from './GameContext';
import { useAuth } from '../AuthContext';
import { getDecisions, saveDecisions } from '../api/decisions';

const DecisionContext = createContext(null);

export const DecisionProvider = ({ children }) => {
  const { gameId, teamId, currentRound, refreshBudgets } = useGame();
  const { user } = useAuth();
  const isDemo = user?.is_demo;
  const [draft, setDraft] = useState({});
  const [isDirty, setIsDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);
  const [locked, setLocked] = useState(false);
  const [loadingDraft, setLoadingDraft] = useState(true);
  const autoSaveTimer = useRef(null);

  // Load existing draft on mount or round change
  const loadDraft = useCallback(async () => {
    if (!gameId || !teamId || !currentRound) { setLoadingDraft(false); return; }
    setLoadingDraft(true);
    try {
      const res = await getDecisions(gameId, teamId, currentRound);
      setDraft(res.data || {});
      setLocked(isDemo || res.data?.status === 'locked');
    } catch {
      setDraft({});
      setLocked(false);
    } finally {
      setLoadingDraft(false);
    }
  }, [gameId, teamId, currentRound]);

  useEffect(() => { loadDraft(); }, [loadDraft]);

  // Auto-save every 30s if dirty
  useEffect(() => {
    if (isDirty && !locked) {
      autoSaveTimer.current = setTimeout(() => {
        saveDraft();
      }, 30000);
    }
    return () => clearTimeout(autoSaveTimer.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDirty, draft]);

  const saveDraft = useCallback(async () => {
    if (!gameId || !teamId || !currentRound || locked) return;
    setSaving(true);
    try {
      await saveDecisions(gameId, teamId, currentRound, draft);
      setIsDirty(false);
      setLastSaved(new Date());
      refreshBudgets();
    } catch (err) {
      console.error('Auto-save failed:', err);
    } finally {
      setSaving(false);
    }
  }, [gameId, teamId, currentRound, draft, locked, refreshBudgets]);

  const updateDraft = useCallback((section, data) => {
    setDraft(prev => ({ ...prev, [section]: data }));
    setIsDirty(true);
  }, []);

  return (
    <DecisionContext.Provider value={{
      draft, isDirty, saving, lastSaved, locked, loadingDraft,
      updateDraft, saveDraft, loadDraft, setLocked,
    }}>
      {children}
    </DecisionContext.Provider>
  );
};

export const useDecisions = () => {
  const ctx = useContext(DecisionContext);
  if (!ctx) throw new Error('useDecisions must be used within DecisionProvider');
  return ctx;
};
