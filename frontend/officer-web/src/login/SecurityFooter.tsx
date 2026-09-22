/** Security assurances shown under the form. Describes the mechanisms that actually exist. */
import { lc, lfont } from './loginTheme';

export default function SecurityFooter() {
  return (
    <div className="ds-security">
      <p className="ds-security-line">
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke={lc.gov} strokeWidth="1.7"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flexShrink: 0 }}>
          <rect x="4.5" y="10.5" width="15" height="9.5" rx="2" /><path d="M8 10.5V7.8a4 4 0 0 1 8 0v2.7" />
        </svg>
        <span>Encrypted government access</span>
      </p>
      <p style={{ font: `500 10.5px ${lfont.ui}`, color: lc.muted, margin: '5px 0 0', lineHeight: 1.5 }}>
        Your session is protected by token-based authentication. Sign-in attempts are recorded in the
        audit trail, and repeated failures temporarily lock the account.
      </p>
    </div>
  );
}
