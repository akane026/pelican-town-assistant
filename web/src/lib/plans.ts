import type { Task, JsonObject } from './types';

export interface SavedPlan {
  id: string;
  taskId: string;
  revision: number;
  snapshotId: string;
  title: string;
  answer: string;
  inputs: JsonObject;
  createdAt: string;
}
export const PLANS_KEY = 'pelican:plans:v1';

export function readPlans(): SavedPlan[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(PLANS_KEY) || '[]');
    if (!Array.isArray(stored)) return [];
    return stored.filter((row): row is SavedPlan =>
      Boolean(
        row &&
        typeof row.id === 'string' &&
        typeof row.taskId === 'string' &&
        typeof row.answer === 'string' &&
        typeof row.title === 'string' &&
        typeof row.revision === 'number' &&
        typeof row.snapshotId === 'string' &&
        typeof row.createdAt === 'string' &&
        row.inputs &&
        typeof row.inputs === 'object',
      ),
    );
  } catch {
    return [];
  }
}
export function writePlans(plans: SavedPlan[]) {
  try {
    localStorage.setItem(PLANS_KEY, JSON.stringify(plans));
  } catch {
    throw new Error('浏览器无法保存计划，请检查存储权限或可用空间。');
  }
}
export function savePlan(task: Task) {
  if (!task.answer?.answer_text) throw new Error('先完成一次对话，再保存结果。');
  const plan: SavedPlan = {
    id: `${task.task_id}:${task.revision}`,
    taskId: task.task_id,
    revision: task.revision,
    snapshotId: task.snapshot_id,
    title: String(task.inputs.goal || '我的农场计划'),
    answer: task.answer.answer_text,
    inputs: task.inputs,
    createdAt: new Date().toISOString(),
  };
  writePlans([plan, ...readPlans().filter((row) => row.id !== plan.id)]);
  return plan;
}
