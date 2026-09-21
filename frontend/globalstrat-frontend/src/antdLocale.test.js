import fs from 'fs';
import path from 'path';
import dayjs from 'dayjs';

import { antdLocaleFor, applyDateLocale } from './antdLocale';

describe('antd speaks the interface language', () => {
  test('Chinese for a Chinese-language reader, however the browser spells it', () => {
    expect(antdLocaleFor('zh-CN').locale).toBe('zh-cn');
    expect(antdLocaleFor('zh').locale).toBe('zh-cn');
    expect(antdLocaleFor('zh-CN').Popconfirm.okText).toBe('确定');
    expect(antdLocaleFor('zh-CN').Modal.cancelText).toBe('取消');
  });

  test('English otherwise, including when no language is known', () => {
    expect(antdLocaleFor('en').locale).toBe('en');
    expect(antdLocaleFor(undefined).locale).toBe('en');
    expect(antdLocaleFor('fr').Popconfirm.okText).toBe('OK');
  });

  test('the date picker follows', () => {
    applyDateLocale('zh-CN');
    expect(dayjs('2026-09-21').format('MMMM')).toBe('九月');
    applyDateLocale('en');
    expect(dayjs('2026-09-21').format('MMMM')).toBe('September');
  });

  test('App hands the locale to ConfigProvider', () => {
    const app = fs.readFileSync(path.join(__dirname, 'App.js'), 'utf8');
    expect(app).toMatch(/<ConfigProvider[^>]*\blocale=\{antdLocaleFor\(i18n\.language\)\}/);
    expect(app).toMatch(/applyDateLocale\(i18n\.language\)/);
  });
});
