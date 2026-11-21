/** API contracts mirror stardew_agent/server.py. Open evidence payloads stay unknown. */
export type JsonObject = Record<string, unknown>;
export type ExecutionMode = 'candidate_diagnostic' | 'released';
export interface Answer extends JsonObject {
  answer_text: string;
  status?: string;
  claim_evidence_refs?: string[];
  calculation_trace_refs?: string[];
}
export interface Upload {
  image_id: string;
  width: number;
  height: number;
}
export interface Region {
  region_id: string;
  image_id: string;
  bbox: [number, number, number, number];
}
export interface Task {
  task_id: string;
  revision: number;
  snapshot_id: string;
  execution_mode: ExecutionMode;
  inputs: JsonObject;
  status: string;
  created_at: string;
  answer?: Answer;
  missing_inputs?: string[];
  uploaded_images: Upload[];
  selected_regions: Region[];
  inventory_plan_copy: JsonObject;
  goal_coverage?: JsonObject;
}
export interface TaskDetail {
  task: Task;
  messages: { role: string; content: string | Answer }[];
  events: JsonObject[];
  running: boolean;
}
export interface Manifest {
  snapshot_id: string;
  counts?: Record<string, number>;
  [key: string]: unknown;
}
export interface Rule {
  rule_id: string;
  description: string;
  audit: { status: string };
  [key: string]: unknown;
}
export interface Bootstrap {
  csrf: string;
  snapshot: Manifest | null;
  released: JsonObject | null;
  knowledge_status: 'AVAILABLE' | 'MISSING';
  tasks: Task[];
  rules: Rule[];
}
export interface Entity {
  id: string;
  name: string;
  type: string;
  [key: string]: unknown;
}
export interface Relation extends JsonObject {
  id: string;
  subject: string;
  predicate: string;
  object: string;
  conditions?: unknown;
}
export interface GraphData {
  nodes: Entity[];
  edges: Relation[];
  snapshot_id: string;
  truncated: boolean;
}
export interface SearchEntity {
  entity_id: string;
  name: string;
  type?: string;
}
export interface RecordDetail {
  snapshot_id: string;
  record: JsonObject & { id: string };
  evidence: { id: string; quote: string; url: string; page_id: string; locator: string }[];
  assets: { id: string; width: number; height: number }[];
  alignments: JsonObject[];
  regions: JsonObject[];
  observations: JsonObject[];
}
export interface ReviewData {
  snapshot_id: string;
  total: number;
  offset: number;
  decisions_count: number;
  items: { record: JsonObject & { id: string }; decision?: { action: string; reason: string } }[];
  quality: JsonObject;
}
export interface MatchResult {
  region: Region;
  task_revision: number;
  match: { status: string; candidates: { entity_id: string; name: string; distance: number }[] };
}
