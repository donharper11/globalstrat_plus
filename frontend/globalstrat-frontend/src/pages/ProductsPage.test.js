import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import fs from 'fs';
import path from 'path';
import ProductsPage from './ProductsPage';
import { getProductContext, patchDecision } from '../api/decisions';

/**
 * R48 item 9. Products are fixed once created. The page offered an edit
 * control on every existing product whose save sent `existing_product_id`,
 * which the serializer drops, so the server treated the edit as a new
 * product and refused it -- a control that could never succeed. The control
 * is gone; create and retire remain.
 *
 * `t` is stubbed to print its key, so the assertions name catalogue keys.
 */

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));
jest.mock('../api/decisions', () => ({
  getProductContext: jest.fn(),
  patchDecision: jest.fn(),
}));
jest.mock('../api/saveFailures', () => ({
  reportUnpublishedFailure: jest.fn(),
}));
const mockRefreshBudgets = jest.fn();
jest.mock('../contexts/GameContext', () => ({
  useGame: () => ({
    gameId: 1, teamId: 2, currentRound: 3, refreshBudgets: mockRefreshBudgets,
  }),
}));
const mockLoadDraft = jest.fn();
jest.mock('../contexts/DecisionContext', () => ({
  useDecisions: () => ({ draft: { product_retires: [] }, locked: false, loadDraft: mockLoadDraft }),
  describeRefusal: () => [],
}));

const existingProduct = {
  id: 41, name: 'Nexus Pro', positioning: 'mainstream', platform_id: 7,
  platform_name: 'Atlas', status: 'active', est_unit_cost: 120,
  feature_levels: [{ feature_code: 'battery', feature_name: 'Battery', current_level: 2.5 }],
  markets: [{ market_id: 1, market_name: 'Europe', is_active: true }],
  retail_prices: { 1: 300 },
};

const contextPayload = (overrides = {}) => ({
  data: {
    products: [existingProduct],
    active_platforms: [{ id: 7, name: 'Atlas' }],
    active_markets: [{ id: 1, name: 'Europe' }],
    max_products_total: 6,
    active_product_count: 1,
    ...overrides,
  },
});

beforeEach(() => {
  getProductContext.mockResolvedValue(contextPayload());
  patchDecision.mockResolvedValue({ data: {} });
});
afterEach(() => jest.clearAllMocks());

test('an existing product renders without an edit control', async () => {
  render(<ProductsPage />);
  expect(await screen.findByText('Nexus Pro')).toBeInTheDocument();

  // The two affordances the edit path had: the row hint and the tooltip'd
  // pencil. Neither exists now, in any state.
  expect(screen.queryByText('products_page.click_to_edit')).not.toBeInTheDocument();
  expect(screen.queryByText('products_page.edit_product')).not.toBeInTheDocument();
  expect(screen.queryByText('products_page.save_changes')).not.toBeInTheDocument();
  // What the row hint says instead.
  expect(screen.getByText('products_page.fixed_once_created')).toBeInTheDocument();
});

test('create and retire remain', async () => {
  render(<ProductsPage />);
  expect(await screen.findByText('Nexus Pro')).toBeInTheDocument();

  expect(screen.getByRole('button', { name: 'products_page.create_new_product' }))
    .toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'products_page.retire_product' }));

  // The retire modal offers the two retirements and no editable field.
  expect(await screen.findByText('products_page.retire_immediately')).toBeInTheDocument();
  expect(screen.getByText('products_page.retire_end_of_round')).toBeInTheDocument();
  expect(screen.queryByText('products_page.save_changes')).not.toBeInTheDocument();
  expect(screen.queryByText('products_page.product_name')).not.toBeInTheDocument();

  fireEvent.click(screen.getByText('products_page.retire_immediately'));
  await waitFor(() => expect(patchDecision).toHaveBeenCalledTimes(1));
  expect(patchDecision).toHaveBeenCalledWith(1, 2, 3, 'product-retires', {
    product_retires: [{ team_product: 41, timing: 'immediate' }],
  });
});

test('a retired product has no control at all', async () => {
  getProductContext.mockResolvedValue(contextPayload({
    products: [{ ...existingProduct, status: 'retired' }],
  }));
  render(<ProductsPage />);
  expect(await screen.findByText('Nexus Pro')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'products_page.retire_product' }))
    .not.toBeInTheDocument();
});

test('nothing on the page can send existing_product_id any more', () => {
  const source = fs.readFileSync(path.join(__dirname, 'ProductsPage.js'), 'utf8');
  expect(source).not.toMatch(/existing_product_id/);
  expect(source).not.toMatch(/handleEditSave|editForm/);
});
