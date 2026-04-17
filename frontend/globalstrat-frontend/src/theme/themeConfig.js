/**
 * GlobalStrat Enterprise Theme — Sharp Geometric, Financial Platform Style
 * IBM Plex Sans, zero border-radius, left-border accents, no shadows
 */

const themeConfig = {
  token: {
    colorPrimary: '#1E40AF',
    colorPrimaryHover: '#1E3A8A',
    colorPrimaryActive: '#1E3A8A',
    colorPrimaryBg: '#DBEAFE',
    colorPrimaryBgHover: '#EFF6FF',

    fontFamily: "'Source Sans 3', 'IBM Plex Sans', system-ui, -apple-system, sans-serif",
    fontSize: 14,
    fontSizeHeading3: 24,
    fontSizeHeading4: 16,
    fontSizeSM: 12,
    fontSizeLG: 16,
    fontWeightStrong: 600,

    borderRadius: 6,
    borderRadiusSM: 4,
    borderRadiusLG: 6,
    borderRadiusXS: 3,

    colorBorder: '#E2E8F0',
    colorBorderSecondary: '#E2E8F0',

    colorBgContainer: '#FFFFFF',
    colorBgLayout: '#F1F5F9',
    colorBgElevated: '#FFFFFF',

    colorText: '#0F172A',
    colorTextSecondary: '#334155',
    colorTextTertiary: '#64748B',
    colorTextQuaternary: '#94A3B8',

    paddingLG: 20,
    marginLG: 20,

    // No shadows
    boxShadow: 'none',
    boxShadowSecondary: 'none',
  },
  components: {
    Menu: {
      darkItemBg: 'transparent',
      darkSubMenuItemBg: 'transparent',
      darkItemSelectedBg: '#1E293B',
      darkItemHoverBg: '#1E293B',
      darkItemColor: '#94A3B8',
      darkItemSelectedColor: '#E2E8F0',
      darkItemHoverColor: '#E2E8F0',
      itemHeight: 32,
      itemBorderRadius: 0,
    },
    Table: {
      headerBg: '#F8FAFC',
      headerColor: '#64748B',
      headerSplitColor: 'transparent',
      rowHoverBg: '#F8FAFC',
      borderColor: '#E2E8F0',
      cellPaddingBlock: 10,
      cellPaddingInline: 16,
      headerBorderRadius: 0,
      borderRadius: 0,
      borderRadiusLG: 0,
    },
    Card: {
      borderRadiusLG: 0,
      borderRadius: 0,
      paddingLG: 20,
    },
    Button: {
      borderRadius: 0,
      borderRadiusSM: 0,
      borderRadiusLG: 0,
      controlHeight: 36,
      fontWeight: 500,
    },
    Input: {
      borderRadius: 0,
      borderRadiusSM: 0,
      borderRadiusLG: 0,
    },
    InputNumber: {
      borderRadius: 0,
    },
    Select: {
      borderRadius: 0,
      borderRadiusSM: 0,
    },
    Tabs: {
      itemColor: '#64748B',
      itemSelectedColor: '#1E40AF',
      itemHoverColor: '#1E40AF',
      inkBarColor: '#1E40AF',
    },
    Tag: {
      borderRadiusSM: 0,
      borderRadius: 0,
    },
    Modal: {
      borderRadiusLG: 0,
      borderRadius: 0,
    },
    Drawer: {
      borderRadius: 0,
      borderRadiusLG: 0,
    },
    Progress: {
      defaultColor: '#1E40AF',
    },
    Statistic: {
      titleFontSize: 10,
      contentFontSize: 22,
    },
    Alert: {
      borderRadiusLG: 0,
      borderRadius: 0,
    },
    Badge: {
      borderRadiusSM: 0,
    },
    Collapse: {
      borderRadiusLG: 0,
    },
    Dropdown: {
      borderRadiusLG: 0,
      borderRadius: 0,
    },
    Popover: {
      borderRadiusLG: 0,
    },
    Tooltip: {
      borderRadius: 0,
    },
    Notification: {
      borderRadiusLG: 0,
    },
    Message: {
      borderRadiusLG: 0,
    },
    Pagination: {
      borderRadius: 0,
    },
    DatePicker: {
      borderRadius: 0,
    },
    Switch: {
      borderRadius: 0,
    },
  },
};

// Accent colors for left-border metric cards and section labels
export const ACCENT = {
  green: '#22C55E',
  blue: '#3B82F6',
  purple: '#8B5CF6',
  amber: '#F59E0B',
  red: '#EF4444',
  teal: '#06B6D4',
  navy: '#1E40AF',
  // Legacy aliases
  environmental: '#22C55E',
  financial: '#3B82F6',
  social: '#F59E0B',
  governance: '#8B5CF6',
  performance: '#06B6D4',
  expense: '#EF4444',
  growth: '#22C55E',
  rank: '#F59E0B',
  neutral: '#64748B',
};

// Chart palette
export const CHART_COLORS = ['#1E40AF', '#22C55E', '#F59E0B', '#8B5CF6', '#06B6D4', '#EF4444'];

// ESG colors
export const ESG = {
  e: '#22C55E',
  s: '#3B82F6',
  g: '#8B5CF6',
};

export default themeConfig;
