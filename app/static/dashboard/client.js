// @ts-check
/** @typedef {import('./contracts').Twin} Twin */
/** @typedef {import('./contracts').SourceStatus} SourceStatus */
/** @typedef {import('./contracts').PersistenceStatus} PersistenceStatus */
/** @typedef {import('./contracts').Observation} Observation */
/** @typedef {import('./contracts').MachineEvent} MachineEvent */
/** @typedef {import('./contracts').KpiResult} KpiResult */
/** @typedef {import('./contracts').Assessment} Assessment */
/** @typedef {import('./contracts').Selection} Selection */
/** @typedef {import('./contracts').WindowQuery} WindowQuery */

const base = typeof __API_BASE__ === 'undefined' ? '' : __API_BASE__;
export class ApiError extends Error {
  /** @param {number} status @param {string} detail */
  constructor(status, detail) { super(`HTTP ${status}: ${detail}`); this.status = status; }
}
/** @template T @param {string} path @param {AbortSignal} [signal] @returns {Promise<T>} */
async function request(path, signal) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener('abort', abort, {once: true});
  if (signal?.aborted) abort();
  const timer = setTimeout(abort, 10000);
  try {
    const response = await fetch(base + path, {method: 'GET', cache: 'no-store', signal: controller.signal});
    const body = await response.json().catch(() => null);
    if (!response.ok) throw new ApiError(response.status,
      typeof body?.detail === 'string' ? body.detail : response.status === 422 ? 'Invalid query. Check identifiers and timezone-aware timestamps.' : 'Request failed');
    if (body === null) throw new Error('The API returned no JSON data');
    return body;
  } catch (error) {
    if (controller.signal.aborted && !signal?.aborted) throw new Error('Request timed out after 10 seconds');
    throw error;
  } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort); }
}
/** @param {Selection} selection @param {string} kind @param {Record<string,string>} params */
export function queryPath(selection, kind, params) {
  return `/api/twins/${encodeURIComponent(selection.asset)}/${kind}?${new URLSearchParams({...params,run_id:selection.run})}`;
}
export const api = {
  /** @param {AbortSignal} [signal] @returns {Promise<Twin[]>} */
  twins: signal => request('/api/twins', signal),
  /** @param {string} id @param {AbortSignal} [signal] @returns {Promise<Twin>} */
  twin: (id, signal) => request(`/api/twins/${encodeURIComponent(id)}`, signal),
  /** @param {AbortSignal} [signal] @returns {Promise<SourceStatus>} */
  source: signal => request('/api/source-status', signal),
  /** @param {AbortSignal} [signal] @returns {Promise<PersistenceStatus>} */
  persistence: signal => request('/api/persistence-status', signal),
  /** @param {AbortSignal} [signal] @returns {Promise<{status:string;service:string}>} */
  liveness: signal => request('/health', signal),
  /** @param {Selection} s @param {'telemetry'|'history'} kind @param {number} after @param {AbortSignal} [signal] @returns {Promise<(Observation|MachineEvent)[]>} */
  history: (s, kind, after, signal) => request(queryPath(s, kind, {limit:'200',after_id:String(after)}), signal),
  /** @param {WindowQuery} q @param {AbortSignal} [signal] @returns {Promise<KpiResult>} */
  kpis: (q, signal) => request(queryPath(q, 'kpis', {source:q.source,start:q.start,end:q.end}), signal),
  /** @param {WindowQuery} q @param {string} generated @param {AbortSignal} [signal] @returns {Promise<Assessment>} */
  health: (q, generated, signal) => request(queryPath(q, 'health-assessment',
    {source:q.source,start:q.start,end:q.end,assessment_generated_at:generated}), signal),
};
