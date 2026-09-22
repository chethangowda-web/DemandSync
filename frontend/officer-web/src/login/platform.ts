/**
 * The two unauthenticated facts the sign-in screen is allowed to show.
 *
 * Everything on this screen that looks like a live figure is one of these, fetched through the normal
 * API client. Nothing is hardcoded and nothing is invented: when a call fails the hooks report
 * `unavailable` and the UI says so, because a sign-in screen that displays a confident fake number is
 * worse than one that displays none.
 *
 *   GET /health                      public liveness + a real database probe
 *   GET /api/v1/datasets/manifest    public dataset manifest (row counts, geography, provenance)
 *
 * The manifest is the only public source of platform scale; the authenticated counterpart
 * (/api/v1/system/db-status) is SYSTEM_ADMIN-only and deliberately not reachable from here.
 */
import { useEffect, useState } from 'react';
import { get } from '../api/client';

export type Health = { status: string; database: string };

export interface Manifest {
  dataset_name?: string;
  version?: string;
  synthetic?: boolean;
  generated_at?: string;
  data_quality_status?: string;
  row_counts?: Record<string, number>;
  operating_geography?: Record<string, { lat: number; lon: number }>;
}

export type Load<T> = { state: 'loading' } | { state: 'ready'; data: T } | { state: 'unavailable' };

function useEndpoint<T>(path: string, pollMs?: number): Load<T> {
  const [res, setRes] = useState<Load<T>>({ state: 'loading' });
  useEffect(() => {
    let live = true;
    const run = () => get<T>(path)
      .then(d => { if (live) setRes({ state: 'ready', data: d }); })
      .catch(() => { if (live) setRes({ state: 'unavailable' }); });
    run();
    if (!pollMs) return () => { live = false; };
    const id = window.setInterval(run, pollMs);
    return () => { live = false; window.clearInterval(id); };
  }, [path, pollMs]);
  return res;
}

/** Re-probed every 30s so the status lamp reflects the platform rather than page-load time. */
export const useHealth = () => useEndpoint<Health>('/health', 30_000);
export const useManifest = () => useEndpoint<Manifest>('/api/v1/datasets/manifest');

export interface PlatformFigure {
  /** Formatted for display, or null when the manifest did not carry this count. */
  value: string | null;
  label: string;
  caption: string;
}

const inIN = (n: number) => n.toLocaleString('en-IN');

/** Pulls the headline figures out of the manifest. Any count the manifest omits comes back null. */
export function figuresFrom(m: Manifest | null): PlatformFigure[] {
  const rc = m?.row_counts ?? {};
  const n = (k: string) => (typeof rc[k] === 'number' ? inIN(rc[k]) : null);
  const districts = m?.operating_geography ? Object.keys(m.operating_geography).length : null;
  return [
    { value: n('beneficiaries_master.csv'), label: 'Registered beneficiaries', caption: 'Entitlement holders on record' },
    { value: n('fps_master.csv'), label: 'Fair Price Shops', caption: 'Last-mile distribution network' },
    { value: districts === null ? null : inIN(districts), label: 'Districts operating', caption: 'Live allocation geography' },
  ];
}

/** Provenance line. States plainly whether the dataset backing these figures is synthetic. */
export function provenanceOf(m: Manifest | null): string | null {
  if (!m?.dataset_name) return null;
  const bits = [m.dataset_name, m.version && `v${m.version}`, m.data_quality_status,
    m.synthetic ? 'synthetic dataset' : null].filter(Boolean);
  return bits.join(' · ');
}
