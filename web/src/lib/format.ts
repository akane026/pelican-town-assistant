import type { JsonObject, Task } from './types';

export const statusLabels: Record<string, string> = {
  READY: '准备就绪',
  RUNNING: '正在思考',
  NEEDS_INPUT: '待补充条件',
  COMPLETED: '已完成',
  DONE: '已完成',
  OK: '已完成',
  ERROR: '执行中断',
  MODEL_ERROR: '模型未就绪',
  CANCELLED: '已停止',
  PARTIAL_ANSWER: '部分完成',
  ANSWER_VALIDATION_FAILED: '待核验',
  BUDGET_STOP: '已达调用上限',
  candidate: '待审核',
  approved_human: '已审核',
  approve: '已通过',
  reject: '已拒绝',
  defer: '暂缓',
};
export const predicateLabels: Record<string, string> = {
  GROWS_IN: '适宜种植',
  GROWS_INTO: '种植获得',
  PROCESSED_INTO: '可加工为',
  PROCESSES_INTO: '可加工为',
  PRODUCES: '产出',
  REQUIRES: '所需物品',
  REQUIRED_FOR: '献祭所需',
  PART_OF: '属于',
  HAS_STAGE: '生长阶段',
  USES_EQUIPMENT: '使用设备',
  HAS_QUALITY: '物品品质',
};
export const typeLabels: Record<string, string> = {
  Crop: '作物',
  Seed: '种子',
  Season: '季节',
  Item: '物品',
  Bundle: '收集包',
  Product: '加工品',
  Equipment: '设备',
  CropStage: '生长阶段',
  ArtisanGood: '加工品',
};
export const readable = (value: unknown) =>
  typeof value === 'string' ? value : JSON.stringify(value ?? '—');
export const relationLabel = (predicate: string) =>
  predicateLabels[predicate.toUpperCase()] || predicate;
export const taskTitle = (task: Task) => String(task.inputs.goal || '农场里的一个问题');
export const recordTitle = (record: JsonObject) =>
  String(record.name || record.target_id || record.subject || record.id || '知识记录');
export function displayDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? '日期未知'
    : new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric' }).format(date);
}
