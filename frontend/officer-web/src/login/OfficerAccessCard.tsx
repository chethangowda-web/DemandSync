/** The right-hand authentication card: identification, portal directory, credentials, assurances. */
import { useState } from 'react';
import { lc, lfont } from './loginTheme';
import { GovernmentLockup } from './Wordmark';
import RoleSelector, { ROLES } from './RoleSelector';
import OfficerLoginForm from './OfficerLoginForm';
import SecurityFooter from './SecurityFooter';

export default function OfficerAccessCard() {
  const [role, setRole] = useState<string | null>(null);
  const chosen = ROLES.find(r => r.id === role) ?? null;

  return (
    <section className="ds-access" aria-labelledby="ds-access-heading">
      <div className="ds-access-inner">
        <div className="ds-rise" style={{ animationDelay: '0.1s' }}>
          <GovernmentLockup tone="light" size={36} />
        </div>

        <div className="ds-rise" style={{ animationDelay: '0.2s' }}>
          <h2 id="ds-access-heading" className="ds-access-title">Officer command access</h2>
          <p className="ds-access-sub">Secure access to PDS DemandSYNC operations</p>
        </div>

        <div className="ds-rise" style={{ animationDelay: '0.3s' }}>
          <div className="ds-section-head">
            <span className="ds-section-label">Your portal</span>
            <span className="ds-section-hint">Optional</span>
          </div>
          <RoleSelector value={role} onChange={setRole} />
          {/* Stated plainly, because the control looks like it grants access and does not. */}
          <p className="ds-role-note" aria-live="polite">
            {chosen
              ? <><strong style={{ color: lc.gov, fontWeight: 700 }}>{chosen.focus}.</strong> Access is granted from your officer record — you will be taken to the correct portal either way.</>
              : <>Access is determined by your officer record, not by this choice. Selecting a portal only confirms where you expect to land.</>}
          </p>
        </div>

        <div className="ds-rule ds-rise" style={{ animationDelay: '0.35s' }} aria-hidden="true" />

        <div className="ds-rise" style={{ animationDelay: '0.4s' }}>
          <div className="ds-section-head">
            <span className="ds-section-label">Login to continue</span>
          </div>
          <OfficerLoginForm />
        </div>

        <div className="ds-rise" style={{ animationDelay: '0.5s' }}>
          <SecurityFooter />
        </div>

        <footer className="ds-access-foot">
          <span style={{ font: `500 10px ${lfont.ui}`, color: lc.muted, letterSpacing: '0.04em' }}>
            PDS DemandSYNC · Department of Food &amp; Public Distribution · Government of India
          </span>
        </footer>
      </div>
    </section>
  );
}
