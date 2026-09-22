import fs from 'fs';
import path from 'path';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import client from '../../api/client';
import GradeOverrideControl from './GradeOverrideControl';

/**
 * W-CE-12 (walkthrough of 2026-09-22). The grading override existed as an
 * API (`POST`/`DELETE /grades/override/`), as an export in
 * `api/instructor.js` and as columns on the TeamGrade row, and nothing on
 * the console called it. The Team Grades table now carries one control per
 * team.
 */

jest.mock('../../api/client', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() },
}));

// antd's message keeps one container in <body>; wiping the body between
// tests would leave later toasts rendering into a detached node.
afterEach(() => jest.clearAllMocks());

const t = (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key);

const CATEGORIES = [
  { category_id: 5, category_name: 'Performance', weight: 40, computed_score: 61.25,
    override_score: null, final_score: 61.25, comments: null },
  { category_id: 6, category_name: 'Coherence', weight: 30, computed_score: 70,
    override_score: 80, final_score: 80, comments: 'strong strategy narrative' },
];

describe('the console reaches the override API', () => {
  const pages = path.join(__dirname, '..', '..', 'pages');
  const dashboard = fs.readFileSync(path.join(pages, 'InstructorDashboard.js'), 'utf8');

  test('the Team Grades table carries the control', () => {
    expect(dashboard).toMatch(/<GradeOverrideControl\b/);
  });

  test('the wrappers post and delete the override the server expects', async () => {
    const { overrideGrade, clearGradeOverride } = await import('../../api/instructor');
    overrideGrade(3, 7, 5, 72.5, 'late memo, agreed with the team');
    clearGradeOverride(3, 7, 5);
    expect(client.post).toHaveBeenCalledWith('/grades/override/', {
      instance_id: 3, team_id: 7, category_id: 5, override_score: 72.5,
      comments: 'late memo, agreed with the team',
    });
    expect(client.delete).toHaveBeenCalledWith('/grades/override/', {
      data: { instance_id: 3, team_id: 7, category_id: 5 },
    });
  });
});

describe('GradeOverrideControl', () => {
  const setup = (onChanged = jest.fn()) => {
    render(
      <GradeOverrideControl t={t} instanceId={3} teamId={7} teamName="Aurora Devices"
        categories={CATEGORIES} onChanged={onChanged} />);
    fireEvent.click(screen.getByRole('button', { name: 'instructor.grade_override' }));
    return onChanged;
  };

  test('opens on the first category with its current score, and saves a new one', async () => {
    client.post.mockResolvedValue({ data: { override_score: '72.5' } });
    const onChanged = setup();

    expect(screen.getByText('instructor.grade_override_title {"team":"Aurora Devices"}')).toBeInTheDocument();
    const score = screen.getByRole('spinbutton', { name: 'instructor.grade_override_score' });
    expect(score).toHaveValue('61.25');
    expect(screen.getByText('instructor.grade_computed_was {"score":"61.3"}')).toBeInTheDocument();
    // No override on this category yet: nothing to clear.
    expect(screen.queryByRole('button', { name: 'instructor.grade_override_clear' })).toBeNull();

    fireEvent.change(score, { target: { value: '72.5' } });
    fireEvent.blur(score);
    fireEvent.change(screen.getByRole('textbox', { name: 'instructor.grade_override_comments' }),
      { target: { value: '  late memo, agreed with the team ' } });
    fireEvent.click(screen.getByRole('button', { name: 'instructor.grade_override_save' }));

    await waitFor(() => expect(client.post).toHaveBeenCalledWith('/grades/override/', {
      instance_id: 3, team_id: 7, category_id: 5, override_score: 72.5,
      comments: 'late memo, agreed with the team',
    }));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    await waitFor(() => expect(document.body.textContent).toContain(
      'instructor.grade_override_saved {"team":"Aurora Devices","category":"Performance"}'));
  });

  test('no score, nothing sent (the field itself clamps to 0–100)', () => {
    setup();
    const score = screen.getByRole('spinbutton', { name: 'instructor.grade_override_score' });
    expect(score).toHaveAttribute('aria-valuemax', '100');
    expect(score).toHaveAttribute('aria-valuemin', '0');
    fireEvent.change(score, { target: { value: '' } });
    expect(screen.getByRole('button', { name: 'instructor.grade_override_save' })).toBeDisabled();
    expect(client.post).not.toHaveBeenCalled();
  });

  test('a refusal is shown in the server’s words', async () => {
    client.post.mockRejectedValue({
      response: { status: 400, data: {
        code: 'grading_override_incomplete',
        error: '需要提供游戏、团队和覆盖分数。',
      } },
    });
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'instructor.grade_override_save' }));
    await waitFor(() => expect(document.body.textContent).toContain('需要提供游戏、团队和覆盖分数。'));
    expect(document.body.textContent).not.toContain('instructor.grade_override_failed');
  });
});
