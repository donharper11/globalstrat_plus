import enUS from 'antd/locale/en_US';
import zhCN from 'antd/locale/zh_CN';
import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn';

/**
 * The words antd itself supplies -- the OK / Cancel of every Popconfirm and
 * Modal, the date picker, table pagination, "No data" -- follow the interface
 * language. Without a `locale` on `ConfigProvider` they are English for
 * everyone, so a Chinese-language instructor confirmed "close this round" on
 * buttons reading OK and Cancel.
 */
const isChinese = (language) => String(language || '').toLowerCase().startsWith('zh');

export const antdLocaleFor = (language) => (isChinese(language) ? zhCN : enUS);

/** The date picker's month and weekday names come from dayjs, not antd. */
export const applyDateLocale = (language) => dayjs.locale(isChinese(language) ? 'zh-cn' : 'en');
