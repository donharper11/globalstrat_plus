/**
 * The shape each section is SENT in, and the shape it is READ BACK in.
 *
 * 2026-09-21: staff allocation and compliance investment were sent as a dict
 * keyed by pool / by market code. Their serializers take a list of rows, so
 * even with a route to accept them the payload would have been refused -- and
 * compliance was read back as `draft.compliance_investments[code]` from what
 * the server returns as a list, so a stored value would have shown as 0.
 *
 * The backend half is core/tests/test_silent_section_saves.py, which drives
 * exactly the rows these functions build through the real route.
 */
import fs from 'fs';
import path from 'path';
import {
  allocationRows, allocationTotals, effectiveAllocation, rebalanceAfterEdit,
  followHeadcount, complianceRows, complianceByCode, staffingPayload,
} from './sectionPayloads';
import { DECISION_SECTIONS } from '../api/decisionSections';

const MARKETS = [
  { code: 'HM', market_id: 11 },
  { code: 'EU', market_id: 12 },
];

describe('staff allocation', () => {
  test('is sent as one row per pool, markets apart from headquarters', () => {
    expect(allocationRows({
      rd: { hq: 40, EU: 10 },
      commercial: { hq: 25, EU: 5, HM: 0 },
      operations: {},
    })).toEqual([
      { talent_pool: 'rd', hq_count: 40, market_allocation: { EU: 10 } },
      { talent_pool: 'commercial', hq_count: 25, market_allocation: { EU: 5 } },
    ]);
  });

  test('a pool nobody has allocated is not sent at all', () => {
    // No row means "everyone at headquarters" to the engine. Sending a row of
    // zeros would be refused: it does not total the headcount.
    expect(allocationRows({ rd: {}, commercial: {}, operations: {} })).toEqual([]);
  });

  test('an untouched pool is shown with everyone at headquarters', () => {
    expect(effectiveAllocation({}, 50)).toEqual({ hq: 50 });
    expect(effectiveAllocation(undefined, 30)).toEqual({ hq: 30 });
    expect(effectiveAllocation({ hq: 40, EU: 10 }, 50)).toEqual({ hq: 40, EU: 10 });
  });

  test('moving staff into a market takes them from headquarters', () => {
    // The server requires the total to equal the headcount, so a screen that
    // only ever adds would be refused on its first keystroke.
    expect(rebalanceAfterEdit({ hq: 50, EU: 10 }, 'EU', 50))
      .toEqual({ hq: 40, EU: 10 });
    // Headquarters cannot go below zero; the total is then visibly over.
    expect(rebalanceAfterEdit({ hq: 0, EU: 60 }, 'EU', 50))
      .toEqual({ hq: 0, EU: 60 });
    // Editing headquarters itself is left exactly as typed.
    expect(rebalanceAfterEdit({ hq: 30, EU: 10 }, 'hq', 50))
      .toEqual({ hq: 30, EU: 10 });
  });

  test('a headcount change is absorbed at headquarters', () => {
    expect(followHeadcount({ hq: 40, EU: 10 }, 50, 60)).toEqual({ hq: 50, EU: 10 });
    expect(followHeadcount({ hq: 40, EU: 10 }, 50, 12)).toEqual({ hq: 2, EU: 10 });
    expect(followHeadcount({ hq: 5, EU: 45 }, 50, 20)).toEqual({ hq: 0, EU: 45 });
    // A pool with no allocation has nothing to follow.
    expect(followHeadcount({}, 50, 60)).toEqual({});
  });

  test('totals are per pool', () => {
    expect(allocationTotals({ rd: { hq: 40, EU: 10 }, commercial: {} }))
      .toEqual({ rd: 50, commercial: 0, operations: 0 });
  });
});

describe('staffing and allocation travel together', () => {
  const talent = {
    rd: { headcount: 50, salary_level: 3, training_budget: 0, current_level: 3 },
    commercial: { headcount: 30, salary_level: 3, training_budget: 0 },
    operations: { headcount: 40, salary_level: 4, training_budget: 250000 },
  };

  test('one request carries both, to the staffing section', () => {
    expect(staffingPayload(talent, { rd: { hq: 40, EU: 10 } }, true)).toEqual({
      talent: {
        rd_headcount: 50, rd_salary_level: 3, rd_training_budget: 0,
        commercial_headcount: 30, commercial_salary_level: 3,
        commercial_training_budget: 0,
        operations_headcount: 40, operations_salary_level: 4,
        operations_training_budget: 250000,
      },
      talent_allocations: [
        { talent_pool: 'rd', hq_count: 40, market_allocation: { EU: 10 } },
      ],
    });
  });

  test('allocations are left out when the page never loaded them', () => {
    // Sending [] would delete rows the page has not seen.
    expect(staffingPayload(talent, {}, false)).not.toHaveProperty('talent_allocations');
  });
});

describe('compliance investment', () => {
  test('is sent as rows naming the market by id', () => {
    expect(complianceRows({ HM: 0, EU: 1500000 }, MARKETS)).toEqual([
      { market: 12, investment_amount: 1500000 },
    ]);
  });

  test('a market the page does not know is never sent', () => {
    expect(complianceRows({ ZZ: 5 }, MARKETS)).toEqual([]);
  });

  test('is read back from the rows the server returns', () => {
    expect(complianceByCode(
      [{ id: 9, market: 12, investment_amount: '1500000.00' }], MARKETS,
    )).toEqual({ HM: 0, EU: 1500000 });
  });

  test('reads back as zeros when nothing is stored', () => {
    expect(complianceByCode(undefined, MARKETS)).toEqual({ HM: 0, EU: 0 });
    expect(complianceByCode([], MARKETS)).toEqual({ HM: 0, EU: 0 });
  });

  test('what is sent reads back as what was typed', () => {
    const typed = { HM: 250000, EU: 1500000 };
    const stored = complianceRows(typed, MARKETS)
      .map((row, i) => ({ id: i, ...row, investment_amount: `${row.investment_amount}.00` }));
    expect(complianceByCode(stored, MARKETS)).toEqual(typed);
  });
});

/**
 * The defect in one line: a page saved to a section name the server had never
 * heard of. Every section a page names must be one the server accepts;
 * `test_silent_section_saves.SectionNamesAgreeTests` holds the list below
 * equal to the server's own `_TYPE_MAP`.
 */
describe('every section a page saves to is one the server accepts', () => {
  const pagesDir = __dirname;
  const pages = fs.readdirSync(pagesDir)
    .filter(name => /\.js$/.test(name) && !/\.test\.js$/.test(name));

  const sectionsNamedIn = (code) => {
    const found = [];
    const call = /\b(?:autoSave|patchDecision)\(([^)]*?)\)/gs;
    let match;
    while ((match = call.exec(code)) !== null) {
      const literals = match[1].match(/'([a-z][a-z_-]*)'/g) || [];
      // patchDecision(gameId, teamId, round, 'section', data) and
      // autoSave('section', data): the first quoted word is the section.
      if (literals.length) found.push(literals[0].slice(1, -1));
    }
    return found;
  };

  test('the scan sees the sections it should', () => {
    const code = fs.readFileSync(path.join(pagesDir, 'MarketStrategyPage.js'), 'utf8');
    expect(sectionsNamedIn(code)).toEqual(expect.arrayContaining([
      'market-entry', 'plants', 'partnerships', 'compliance-investments',
    ]));
  });

  test.each(pages)('%s', (name) => {
    const code = fs.readFileSync(path.join(pagesDir, name), 'utf8');
    const unknown = sectionsNamedIn(code)
      .filter(section => !DECISION_SECTIONS.includes(section));
    expect(unknown).toEqual([]);
  });
});
