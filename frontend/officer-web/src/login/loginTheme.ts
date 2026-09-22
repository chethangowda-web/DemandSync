/**
 * Tokens for the officer sign-in experience.
 *
 * The control centre (src/dso/theme.ts) is a light, dense, working surface. Sign-in is the opposite
 * moment: it is seen once, at arm's length, and has to establish that this is national infrastructure
 * before the officer reads a single word. So it runs on a deep navy command-centre ground rather than
 * the canvas grey used inside the app.
 *
 * Status colour is imported from the control-centre palette, not redefined, so "operational green"
 * means the same thing on this screen as on every screen after it.
 */
import { c } from '../dso/theme';

export const lc = {
  /** Command-centre ground. */
  abyss: '#04101D',
  navy: '#071A2F',
  navyMid: '#0B2540',
  gov: '#123B63',
  govLine: '#1B4D7E',
  hairline: 'rgba(148, 197, 255, 0.14)',
  hairlineSoft: 'rgba(148, 197, 255, 0.07)',

  /** Type on the dark ground. */
  onDark: '#F2F7FC',
  onDarkBody: '#AFC6DD',
  onDarkMuted: '#93AAC4',
  onDarkFaint: '#8299B3',

  /** Accents. Saffron is a highlight, never a surface. */
  saffron: '#FF9933',
  saffronSoft: 'rgba(255, 153, 51, 0.16)',
  sky: '#4DA3FF',
  skySoft: 'rgba(77, 163, 255, 0.14)',

  /** Light side (the access card). */
  paper: '#FFFFFF',
  paperSoft: '#F4F7FA',
  ink: '#0B1E33',
  body: '#3A5169',
  muted: '#56718A',
  line: '#DCE6F0',
  lineStrong: '#C3D4E5',

  /** Status, shared with the control centre. */
  live: '#16A34A',
  liveSoft: 'rgba(22, 163, 74, 0.14)',
  warn: c.warn,
  bad: c.bad,
  badBg: c.badBg,
  badLine: c.badLine,
} as const;

export const lfont = {
  ui: "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  mono: "'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace",
} as const;

/** Small uppercase eyebrow/label, dark-ground variant. */
export const eyebrow = {
  fontSize: 10.5,
  fontWeight: 700,
  letterSpacing: '0.16em',
  textTransform: 'uppercase',
} as const;
