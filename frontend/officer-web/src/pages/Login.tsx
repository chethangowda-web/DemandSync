/**
 * The /login route.
 *
 * The screen itself lives in src/login/ as a set of composable pieces (brand panel, network
 * visualisation, role directory, credential form). This module stays put so the route in App.tsx
 * and anything else importing `pages/Login` keeps working.
 */
export { default } from '../login/OfficerLoginPage';
