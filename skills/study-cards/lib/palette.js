// Built-in render theme for all study-cards PNG output (plans, stats, tables).
const PALETTE = {
  light: {
    bg: '#FAFAFA',
    cardBg: 'white',
    accent: '#1565C0',
    title: '#0D47A1',
    subtitle: '#37474F',
    text: '#263238',
    muted: '#607D8B',
    good: '#2E7D32',
    warn: '#E65100',
    bad: '#C62828',
    shadow: '0 4px 18px rgba(0,0,0,0.08)',
    border: '#B0BEC5',
    headerBg: '#E3F2FD',
    zebra: '#FAFAFA',
  },
  dark: {
    bg: '#0E1116',
    cardBg: '#1A1F26',
    accent: '#90CAF9',
    title: '#E3F2FD',
    subtitle: '#B0BEC5',
    text: '#ECEFF1',
    muted: '#78909C',
    good: '#81C784',
    warn: '#FFB74D',
    bad: '#EF5350',
    shadow: '0 4px 18px rgba(0,0,0,0.5)',
    border: '#3A4452',
    headerBg: '#15243B',
    zebra: '#141A22',
  },
};

/** Single style for golden-hour: dark theme from study-cards palette. */
const DEFAULT_THEME = 'dark';

module.exports = { PALETTE, DEFAULT_THEME };
