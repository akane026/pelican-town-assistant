// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { PLANS_KEY, readPlans, savePlan } from './plans';
import type { Task } from './types';

const task: Task = {
  task_id: 'task-1',
  revision: 2,
  snapshot_id: 'snapshot-1',
  execution_mode: 'candidate_diagnostic',
  inputs: { quantity: 5, goal: '比较加工方案' },
  status: 'DONE',
  created_at: '2026-01-01',
  uploaded_images: [],
  selected_regions: [],
  inventory_plan_copy: {},
  answer: { answer_text: '待核对的测试答案' },
};
beforeEach(() => localStorage.clear());
describe('saved plans', () => {
  it('keeps conditions from the saved revision when a task changes', () => {
    savePlan(task);
    savePlan({ ...task, revision: 3, inputs: { quantity: 10 } });
    expect(readPlans().map((plan) => plan.inputs.quantity)).toEqual([10, 5]);
    expect(task.inputs.quantity).toBe(5);
  });
  it('deduplicates the same revision and tolerates malformed storage', () => {
    savePlan(task);
    savePlan(task);
    expect(readPlans()).toHaveLength(1);
    localStorage.setItem(PLANS_KEY, '[{}]');
    expect(readPlans()).toEqual([]);
    localStorage.setItem(PLANS_KEY, 'broken');
    expect(readPlans()).toEqual([]);
  });
});
