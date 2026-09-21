import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rosterUploadOutcome, announceRosterUpload } from './rosterUploadOutcome';
import en from '../locales/en.json';
import zh from '../locales/zh-CN.json';

/**
 * D6 of 2026-09-21. `POST /api/roster/ {action: 'upload'}` answers 201 with a
 * per-row `errors` list, because a roster can be partly refused. The dashboard
 * read only `created`, so "Created 3 students" was announced while the section
 * cap refused seven rows and nothing said so -- V2-104 again, on the roster.
 */

const FULL_EN = 'This section is full. It seats 20 students (4 teams of up to 5). '
  + 'Remove a student, or raise the section limits, before enrolling another.';
const FULL_ZH = '本班级名额已满，可容纳 20 名学生（4 个团队，每队最多 5 人）。'
  + '请先移除一名学生，或提高班级上限，再添加新学生。';
const NO_ID_ZH = '该行既没有学号也没有邮箱，因此未据此创建学生。';

describe('rosterUploadOutcome', () => {
  test('a partly refused upload reports both halves accurately', () => {
    const outcome = rosterUploadOutcome({
      created: 3,
      updated: 1,
      errors: [
        { row: 6, error: FULL_ZH, code: 'section_full' },
        { row: 7, error: NO_ID_ZH, code: 'roster_row_needs_identity' },
      ],
    });
    expect(outcome).toEqual({
      kind: 'partial',
      created: 3,
      existing: 1,
      accepted: 4,
      refusals: [{ row: 6, text: FULL_ZH }, { row: 7, text: NO_ID_ZH }],
    });
  });

  test('a wholly refused upload is a refusal, whatever the 201 said', () => {
    const outcome = rosterUploadOutcome(
      { created: 0, updated: 0, errors: [{ row: 2, error: FULL_EN }] });
    expect(outcome.kind).toBe('refused');
    expect(outcome.accepted).toBe(0);
  });

  test('a clean upload counts what the server wrote, split new from existing', () => {
    expect(rosterUploadOutcome({ created: 5, updated: 2, errors: [] })).toEqual({
      kind: 'uploaded', created: 5, existing: 2, accepted: 7, refusals: [],
    });
    // A re-upload of the same roster creates nobody and is still accepted.
    expect(rosterUploadOutcome({ created: 0, updated: 7, errors: [] }).kind)
      .toBe('uploaded');
  });

  test('a response that confirms nothing is not reported as a success', () => {
    for (const data of [undefined, null, {}, { errors: [] }, '<html>',
      { created: 0, updated: 0, errors: [] }, { created: '3' }]) {
      expect(rosterUploadOutcome(data).kind).toBe('unconfirmed');
    }
  });

  test('a refused row with no usable reason or row number is still counted', () => {
    const outcome = rosterUploadOutcome(
      { created: 1, errors: [{ row: 'x' }, { row: 4, error: '' }, null] });
    expect(outcome.kind).toBe('partial');
    expect(outcome.refusals).toEqual([
      { row: null, text: null }, { row: 4, text: null }, { row: null, text: null },
    ]);
  });
});

describe('announceRosterUpload', () => {
  const ui = (fileName) => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
    message: { success: jest.fn(), warning: jest.fn(), error: jest.fn() },
    Modal: { warning: jest.fn() },
    fileName,
  });

  test('a clean upload is a success for exactly what the server wrote', () => {
    const io = ui();
    announceRosterUpload(rosterUploadOutcome({ created: 5, errors: [] }), io);
    expect(io.message.success).toHaveBeenCalledWith(
      'instructor.roster_upload_added {"created":5}');
    expect(io.Modal.warning).not.toHaveBeenCalled();

    const again = ui();
    announceRosterUpload(
      rosterUploadOutcome({ created: 2, updated: 3, errors: [] }), again);
    expect(again.message.success).toHaveBeenCalledWith(
      'instructor.roster_upload_added_existing {"created":2,"existing":3}');
  });

  test('refused rows are never announced as a success', () => {
    const io = ui('roster.csv');
    const outcome = announceRosterUpload(rosterUploadOutcome({
      created: 3,
      updated: 0,
      errors: [{ row: 6, error: FULL_ZH }, { row: 7, error: NO_ID_ZH }],
    }), io);

    expect(outcome.kind).toBe('partial');
    expect(io.message.success).not.toHaveBeenCalled();
    expect(io.Modal.warning).toHaveBeenCalledTimes(1);
    const shown = io.Modal.warning.mock.calls[0][0];
    expect(shown.title).toBe(
      'instructor.roster_upload_partial {"accepted":3,"refused":2}');

    const { getByTestId } = render(shown.content);
    const body = getByTestId('roster-upload-refusals');
    // The server's sentences, verbatim, each with its row.
    expect(body).toHaveTextContent(FULL_ZH);
    expect(body).toHaveTextContent(NO_ID_ZH);
    expect(body).toHaveTextContent('"row":6');
    expect(body).toHaveTextContent('"row":7');
    expect(body).toHaveTextContent('roster.csv');
  });

  test('a wholly refused upload says nothing was accepted', () => {
    const io = ui();
    announceRosterUpload(rosterUploadOutcome(
      { created: 0, errors: [{ row: 2, error: FULL_EN }] }), io);
    expect(io.message.success).not.toHaveBeenCalled();
    expect(io.Modal.warning.mock.calls[0][0].title).toBe(
      'instructor.roster_upload_none {"refused":1}');
  });

  test('a row the server gave no reason for says so rather than showing nothing', () => {
    const io = ui();
    announceRosterUpload(rosterUploadOutcome(
      { created: 1, errors: [{ row: 3 }] }), io);
    const { getByTestId } = render(io.Modal.warning.mock.calls[0][0].content);
    expect(getByTestId('roster-upload-refusals'))
      .toHaveTextContent('instructor.roster_upload_no_reason');
  });

  test('an unconfirmed upload is a warning, not a success', () => {
    const io = ui();
    announceRosterUpload(rosterUploadOutcome({}), io);
    expect(io.message.warning).toHaveBeenCalledWith(
      'instructor.roster_upload_unconfirmed');
    expect(io.message.success).not.toHaveBeenCalled();
  });
});

describe('the wording exists in both languages', () => {
  const KEYS = ['roster_upload_added', 'roster_upload_added_existing',
    'roster_upload_partial', 'roster_upload_none', 'roster_upload_unconfirmed',
    'roster_upload_row', 'roster_upload_file', 'roster_upload_no_reason',
    'roster_upload_accepted_detail', 'roster_upload_fix_note'];

  test.each(KEYS)('%s', (key) => {
    expect(en.instructor[key]).toEqual(expect.any(String));
    expect(zh.instructor[key]).toMatch(/[一-鿿]/);
    const holes = (text) => (text.match(/\{\{\w+\}\}/g) || []).sort();
    expect(holes(zh.instructor[key])).toEqual(holes(en.instructor[key]));
  });
});
