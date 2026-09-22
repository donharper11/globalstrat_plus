import fs from 'fs';
import path from 'path';

import en from '../locales/en.json';
import zh from '../locales/zh-CN.json';
import {
  distanceLabel, plantStatusLabel, perRoundCharge, plantBuildLabel,
} from './marketStrategyLabels';

/**
 * W-CE-22. `t` is stubbed to print its key and values, so an assertion names
 * the catalogue key a value resolves to, and a second block checks that each
 * key exists in both languages.
 */
const t = (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key);
const fmt = (v) => `$${Number(v).toLocaleString()}`;

describe('cultural distance is a label, not the stored enum', () => {
  test.each([
    ['HOME', 'market_strategy.distance_home'],
    ['LOW', 'market_strategy.distance_low'],
    ['MEDIUM', 'market_strategy.distance_medium'],
    ['HIGH', 'market_strategy.distance_high'],
    ['VERY_HIGH', 'market_strategy.distance_very_high'],
    ['UNKNOWN', 'market_strategy.distance_unknown'],
  ])('%s -> %s', (level, key) => {
    expect(distanceLabel(level, t)).toBe(key);
  });

  test('an unrated market shows a dash, never "undefined"', () => {
    expect(distanceLabel(undefined, t)).toBe('—');
  });
});

describe('a plant status is a label', () => {
  test.each([
    ['operational', 'market_strategy.plant_operational'],
    ['under_construction', 'market_strategy.under_construction'],
    ['decommissioned', 'market_strategy.plant_decommissioned'],
  ])('%s -> %s', (status, key) => {
    expect(plantStatusLabel(status, t)).toBe(key);
  });
});

describe('a partnership is priced the way it is charged', () => {
  test('one figure, per round', () => {
    expect(perRoundCharge(2000000, t, fmt))
      .toBe('market_strategy.per_round_charge {"amount":"$2,000,000"}');
  });
});

describe('the plant cost is the authored one or is said to be missing', () => {
  test('an authored cost is shown with the authored build time and capacity', () => {
    const label = plantBuildLabel(
      { plant_build_cost: 12000000, plant_build_rounds: 2, plant_capacity_units: 80000 }, t, fmt);
    expect(label).toContain('$12,000,000');
    expect(label).toContain('market_strategy.build_plant_detail {"rounds":2,"units":80000}');
  });

  test('a missing cost is named as missing, and no figure is invented', () => {
    const label = plantBuildLabel(
      { plant_build_cost: null, plant_build_rounds: 2, plant_capacity_units: null }, t, fmt);
    expect(label).toContain('market_strategy.plant_cost_not_available');
    expect(label).not.toContain('$0');
    expect(label).not.toContain('50000');
    expect(label).toContain('market_strategy.round_setup {"rounds":2}');
  });
});

describe('the page and the catalogues', () => {
  const source = fs.readFileSync(path.join(__dirname, 'MarketStrategyPage.js'), 'utf8');
  const lookup = (catalogue, key) => key.split('.')
    .reduce((node, part) => (node == null ? node : node[part]), catalogue);

  test('every key the labels use exists in both languages', () => {
    const labels = fs.readFileSync(path.join(__dirname, 'marketStrategyLabels.js'), 'utf8');
    const keys = [...labels.matchAll(/t\('([\w.]+)'/g)].map((m) => m[1]);
    expect(keys.length).toBeGreaterThanOrEqual(10);
    keys.forEach((key) => {
      expect(typeof lookup(en, key)).toBe('string');
      expect(typeof lookup(zh, key)).toBe('string');
    });
  });

  test('the page no longer renders the enum, the token, a $0 cost or a "+ $0/round"', () => {
    expect(source).not.toMatch(/\{loc\?\.distance\?\.level \|\| '—'\}/);
    expect(source).not.toMatch(/\{plant\.status\}/);
    expect(source).not.toMatch(/fmt\(m\.plant_build_cost\)/);
    expect(source).not.toMatch(/recurring_cost_per_round/);
    expect(source).not.toMatch(/\}\/round\n/);
    expect(source).toMatch(/plantBuildLabel\(m, t, fmt\)/);
  });
});
