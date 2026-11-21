// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { FeedbackProvider } from '@/components/feedback';
import { readPlans } from '@/lib/plans';
import type { Task } from '@/lib/types';
import ChatPage from './chat-page';

const task: Task = {
  task_id: 'test-task',
  revision: 7,
  snapshot_id: 'historical-snapshot',
  execution_mode: 'released',
  inputs: { quantity: 5, goal: '测试方案' },
  status: 'DONE',
  created_at: '2026-01-01',
  uploaded_images: [],
  selected_regions: [],
  inventory_plan_copy: {},
  answer: {
    answer_text: '测试专用答案，来自已绑定的历史版本。',
    claim_evidence_refs: ['fact:test'],
  },
};
const response = (data: unknown) =>
  new Response(JSON.stringify(data), { headers: { 'content-type': 'application/json' } });
beforeEach(() => {
  localStorage.clear();
  Element.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.includes('/bootstrap'))
        return response({
          csrf: 'test-token',
          snapshot: { snapshot_id: 'newest-snapshot' },
          released: {},
          tasks: [task],
          rules: [],
        });
      if (url.includes('/record?'))
        return response({
          snapshot_id: task.snapshot_id,
          record: { id: 'fact:test', name: '测试事实' },
          evidence: [],
          assets: [],
          alignments: [],
          regions: [],
          observations: [],
        });
      if (url.includes('/state')) return response({ ...task, revision: 8 });
      return response({
        task,
        messages: [{ role: 'assistant', content: task.answer }],
        events: [],
        running: false,
      });
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function renderTask() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/chat/test-task']}>
        <FeedbackProvider>
          <Routes>
            <Route path="/chat/:taskId" element={<ChatPage mode="candidate_diagnostic" />} />
          </Routes>
        </FeedbackProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
describe('existing task interactions', () => {
  it('loads evidence from the task snapshot rather than the newest candidate', async () => {
    renderTask();
    fireEvent.click(await screen.findByRole('button', { name: '依据 1' }));
    expect(await screen.findByRole('heading', { name: '测试事实' })).toBeInTheDocument();
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(([url]) =>
          String(url).includes('/record?id=fact%3Atest&task_id=test-task'),
        ),
    ).toBe(true);
  });
  it('submits explicit conditions with the task revision and CSRF token', async () => {
    renderTask();
    fireEvent.click(await screen.findByRole('button', { name: '游戏条件' }));
    fireEvent.change(screen.getByLabelText('数量'), { target: { value: '12' } });
    fireEvent.click(screen.getByRole('button', { name: '保存条件' }));
    await waitFor(() =>
      expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url) === '/api/state')).toBe(true),
    );
    const [, options] = vi.mocked(fetch).mock.calls.find(([url]) => String(url) === '/api/state')!;
    expect(JSON.parse(String(options?.body))).toEqual({
      task_id: 'test-task',
      revision: 7,
      fields: { quantity: 12 },
    });
    expect(options?.headers).toMatchObject({ 'X-CSRF-Token': 'test-token' });
  });
  it('saves a versioned plan without changing the backend inventory', async () => {
    renderTask();
    fireEvent.click(await screen.findByRole('button', { name: '保存为计划' }));
    expect(readPlans()[0]).toMatchObject({
      taskId: 'test-task',
      revision: 7,
      snapshotId: 'historical-snapshot',
      inputs: { quantity: 5 },
    });
    expect(vi.mocked(fetch).mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(
      true,
    );
  });
});
