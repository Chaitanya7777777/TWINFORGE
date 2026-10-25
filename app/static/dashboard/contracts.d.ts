export interface Quality { valid: boolean; fresh: boolean; source: string; reason: string | null }
export interface Twin {
  asset_id: string; asset_type: string; factory_id: string; line_id: string;
  state: string; current_job_id: string | null; active_fault: string | null; sequence: number;
  telemetry: {timestamp: string | null; values: Record<string, unknown> | null};
  health: {health_score: number; anomaly_score: number}; quality: Quality;
  relationships: {upstream: string | null; downstream: string | null};
}
export interface SourceStatus {
  source: string; connected: boolean; run_id: string | null;
  last_sync_at: string | null; last_sync_attempt_at: string | null; last_sync_error: string | null;
  consecutive_failures: number; sync_lag_seconds: number | null; stale_after_seconds: number;
}
export interface PersistenceStatus { enabled: boolean; last_persisted_at: string | null; last_error: string | null }
export interface Observation {
  id: number; source: string; run_id: string; asset_id: string; sequence: number;
  observed_at: string; source_timestamp: string | null; raw_source_timestamp: string | null;
  telemetry_values: Record<string, unknown> | null; valid: boolean; fresh: boolean;
  quality_source: string; reason: string | null;
}
export interface MachineEvent {
  id: number; source: string; run_id: string; asset_id: string; sequence: number;
  observed_at: string; kind: 'state_observed'|'state_changed'|'fault_observed'|'fault_started'|'fault_recovered';
  previous_value: string | null; value: string | null;
}
export interface Metric {value: number | null; unit: string; status: 'ok'|'estimated'|'unknown'|'not_applicable'; reason: string | null}
export interface KpiResult {
  contract_version: 'kpi.v1'; source: string; run_id: string; asset_id: string;
  start: string; end: string; window_seconds: number; max_gap_seconds: number;
  coverage: number; observation_count: number; completeness: 'complete'|'incomplete';
  reasons: string[]; metrics: Record<string, Metric>; downtime_reasons_seconds: Record<string, number> | null;
}
export interface EvidenceRef {kind: 'observation'|'event'; id: number; sequence: number; observed_at: string; source_timestamp: string | null}
export interface Indicator {status: 'observed'|'not_observed'|'unavailable'; value: string | boolean | number | null; reason: string; evidence: EvidenceRef[]}
export interface Assessment {
  contract_version: 'health.v1'; method: 'observed_condition_rules'; asset_id: string; source: string; run_id: string;
  assessment_generated_at: string; window_start: string; window_end: string; time_basis: 'receipt';
  latest_source_timestamp: string | null; latest_observed_at: string | null;
  availability: 'available'|'partial'|'unavailable'; reasons: string[];
  data_quality: {evidence_complete: boolean; observation_count: number; event_count: number;
    usable_observation_count: number; missing_source_timestamps: number; invalid_observations: number;
    stale_observations: number; missing_telemetry: number; sequence_gaps: number;
    sequence_reversals: number; nonincreasing_source_timestamps: number; findings: string[]};
  indicators: Record<string, Indicator>;
}
export interface Selection { asset: string; run: string; source: string }
export interface WindowQuery extends Selection { start: string; end: string }
export interface Route extends Selection {page: string; search: string; state: string; factory: string; line: string}
declare global { const __API_BASE__: string }
