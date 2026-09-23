/**
 * Dispatch workspace — stage 05 AUTHORIZE, and the release into tracking.
 *
 * Three distinct acts, deliberately kept separate and in order: validate each manifest's arithmetic,
 * seal it (SHA-256 + QR, immutable thereafter), then authorise the cycle. The authorisation gate is
 * never enabled unless every manifest is actually sealed.
 */
import { useState } from 'react';
import { useCycle } from '../DsoLayout';
import { Manifest, ManifestDetail, dso } from '../api';
import { c, font, kg, label, num, s } from '../theme';
import { Badge, DataUnavailable, Drawer, ErrorNote, Loading, Metric, MetricStrip, Panel, Region, useData } from '../ui';
import { StageRail } from '../components/Situation';
import { IntelSection } from '../../components/Intelligence';
import { intel } from '../../api/intelligence';
import { DecisionGate, ActionCard } from '../components/Gate';
import { ManifestCard, ManifestDetailView } from '../components/Manifest';

export default function DispatchPage() {
  const { cycle, summary, refresh } = useCycle();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<ManifestDetail | null>(null);

  const manQ = useData<Manifest[]>(() => (cycle ? dso.manifests(cycle).then(m => m.filter(x => x.manifest_id.startsWith('MFO-'))) : Promise.resolve([])), [cycle, summary?.state]);

  if (!cycle) return <Loading />;
  const list = manQ.data ?? [];
  const drafts = list.filter(m => m.manifest_status === 'DRAFT');
  const validated = list.filter(m => m.manifest_status === 'VALIDATED');
  const locked = list.filter(m => ['LOCKED', 'DISPATCHED', 'DELIVERED', 'RECONCILED'].includes(m.manifest_status));
  const unsealed = drafts.length + validated.length;

  const run = async (what: string, fn: () => Promise<unknown>) => {
    setBusy(what); setErr(null);
    try { await fn(); manQ.reload(); refresh(); } catch (e: any) { setErr(e?.message || String(e)); } finally { setBusy(null); }
  };

  const validateAll = () => run('validate', async () => { for (const m of drafts) await dso.validateManifest(m.manifest_id); });
  const lockAll = () => run('lock', async () => { for (const m of validated) await dso.lockManifest(m.manifest_id); });

  const canAuthorize = summary?.state === 'OPTIMIZED';
  const authorized = summary && ['AUTHORIZED', 'TRACKING', 'DELIVERING', 'RECONCILING', 'AUDITING', 'CLOSED'].includes(summary.state);

  return (
    <>
      <Panel title="Dispatch authorization" subtitle="Stage 05 · validate, seal, authorise, release">
        <StageRail state={summary?.state} />
        <IntelSection title="Dispatch risk" subtitle="Readiness before your authorisation — advisory only"
          fetch={() => intel.dsoRisks(cycle ?? undefined).then(r => r.risks.filter(a => a.type === 'DISPATCH_RISK'))}
          emptyWhy="No dispatch blockers detected in current records." />
      </Panel>

      {err && <ErrorNote error={err} />}

      <MetricStrip>
        <Metric name="Manifests" value={num(list.length)} hint={`${kg(summary?.manifests.total_kg)} planned`} />
        <Metric name="Draft" value={num(drafts.length)} t={drafts.length ? 'accent' : undefined} hint="Awaiting validation" />
        <Metric name="Validated" value={num(validated.length)} t={validated.length ? 'warn' : undefined} hint="Awaiting seal" />
        <Metric name="Sealed" value={num(locked.length)} t={locked.length ? 'ok' : undefined} hint="SHA-256 locked, immutable" />
      </MetricStrip>

      {list.length === 0 ? (
        <DataUnavailable what="No manifests to dispatch"
          why="Manifests are produced by route optimisation. Run stage 04 first." />
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: s(4) }}>
            <ActionCard title="1 · Validate manifests"
              body={<>Re-checks each manifest's arithmetic and that it still matches the live allocation it was built from. A manifest whose numbers no longer add up is refused rather than sealed.</>}
              action={drafts.length ? `Validate ${drafts.length} draft${drafts.length === 1 ? '' : 's'}` : 'Nothing to validate'}
              disabled={drafts.length === 0} busy={busy === 'validate'} onAction={validateAll} />

            <ActionCard title="2 · Seal manifests"
              body={<>Computes a SHA-256 over each manifest's canonical content and attaches a QR carrying that hash. Once sealed the content is immutable at the database level.</>}
              action={validated.length ? `Seal ${validated.length} manifest${validated.length === 1 ? '' : 's'}` : 'Nothing to seal'}
              disabled={validated.length === 0} busy={busy === 'lock'} onAction={lockAll} />
          </div>

          {!authorized ? (
            <DecisionGate
              title="3 · Authorize dispatch"
              intro="The final human decision before goods move. AI and the optimiser advise; only you authorise."
              checks={[
                { label: 'Demand locked and sealed', status: summary?.demand_lock.locked ? 'PASS' : 'FAIL' },
                { label: 'Routes optimised', status: list.length > 0 ? 'PASS' : 'FAIL' },
                { label: `All ${list.length} manifests sealed`, status: unsealed === 0 ? 'PASS' : 'FAIL',
                  detail: unsealed ? `${unsealed} not yet sealed` : undefined },
                { label: 'Cycle awaiting authorization', status: canAuthorize ? 'PASS' : 'FAIL',
                  detail: canAuthorize ? undefined : `state is ${summary?.state}` },
              ]}
              action="Authorize dispatch"
              busy={busy === 'authorize'}
              onAction={() => run('authorize', () => dso.authorize(cycle))}
            />
          ) : (
            <ActionCard title="4 · Release vehicles"
              body={summary?.state === 'AUTHORIZED'
                ? <>Dispatch is authorised. Releasing marks every sealed manifest DISPATCHED, moves its vehicle to IN_TRANSIT and begins tracking.</>
                : <>Vehicles for this cycle have already been released. The cycle is {summary?.state}.</>}
              action="Release for dispatch"
              disabled={summary?.state !== 'AUTHORIZED'}
              busy={busy === 'dispatch'}
              onAction={() => run('dispatch', () => dso.dispatch(cycle))} />
          )}

          <Panel title={`Manifests (${list.length})`}>
            <Region q={manQ}>
              {() => (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: s(4) }}>
                  {list.map(m => (
                    <ManifestCard key={m.manifest_id} m={m}
                      onOpen={async () => {
                        setErr(null);
                        try { setOpen(await dso.manifest(m.manifest_id)); } catch (e: any) { setErr(e?.message || String(e)); }
                      }}
                      actions={
                        m.manifest_status === 'DRAFT' ? (
                          <button onClick={() => run('one', () => dso.validateManifest(m.manifest_id))}
                            style={{ font: `600 12.5px ${font.ui}`, padding: '7px 14px', borderRadius: 5, border: 'none',
                              background: c.navy, color: '#fff', cursor: 'pointer' }}>Validate</button>
                        ) : m.manifest_status === 'VALIDATED' ? (
                          <button onClick={() => run('one', () => dso.lockManifest(m.manifest_id))}
                            style={{ font: `600 12.5px ${font.ui}`, padding: '7px 14px', borderRadius: 5, border: 'none',
                              background: c.navy, color: '#fff', cursor: 'pointer' }}>Seal & lock</button>
                        ) : null
                      } />
                  ))}
                </div>
              )}
            </Region>
          </Panel>
        </>
      )}

      <Drawer open={!!open} onClose={() => setOpen(null)} title={open?.manifest_id ?? ''}
        subtitle="Dispatch manifest" width={620}>
        {open && <ManifestDetailView detail={open} />}
      </Drawer>
    </>
  );
}
