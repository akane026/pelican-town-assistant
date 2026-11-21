// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { FeedbackProvider } from '@/components/feedback';
import ChatPage from './chat-page';
import { setApiKey } from '@/lib/credentials';

const missingBoot = {
  csrf: 'test-csrf',
  snapshot: null,
  released: null,
  knowledge_status: 'MISSING',
  tasks: [],
  rules: [],
};
beforeEach(() => {
  setApiKey('synthetic-browser-key');
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response(JSON.stringify(missingBoot), {
          headers: { 'content-type': 'application/json' },
        }),
    ),
  );
});
afterEach(() => {
  setApiKey('');
  cleanup();
  vi.unstubAllGlobals();
});
function renderChat() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <FeedbackProvider>
          <ChatPage mode="candidate_diagnostic" />
        </FeedbackProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
describe('chat without a knowledge snapshot', () => {
  it('asks for a key before creating any task and keeps the draft', async () => {
    setApiKey('');
    renderChat();
    const input = screen.getByRole('textbox', { name: '你的农场问题' });
    fireEvent.change(input, { target: { value: '土豆多少钱？' } });
    fireEvent.click(screen.getByRole('button', { name: /^发送$/ }));
    expect(await screen.findByRole('status')).toHaveTextContent('连接与隐私');
    expect(input).toHaveValue('土豆多少钱？');
    expect(vi.mocked(fetch).mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(
      true,
    );
  });
  it('preserves the question and explains how to recover instead of creating a broken task', async () => {
    renderChat();
    const input = screen.getByRole('textbox', { name: '你的农场问题' });
    fireEvent.change(input, { target: { value: '土豆多少钱？' } });
    fireEvent.click(screen.getByRole('button', { name: /^发送$/ }));
    expect(await screen.findByRole('status')).toHaveTextContent('还没有导入知识库');
    expect(input).toHaveValue('土豆多少钱？');
    expect(vi.mocked(fetch).mock.calls.every(([, options]) => options?.method !== 'POST')).toBe(
      true,
    );
  });
  it('does not send while the Chinese input method is composing', async () => {
    renderChat();
    const input = screen.getByRole('textbox', { name: '你的农场问题' });
    fireEvent.change(input, { target: { value: '土豆' } });
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true });
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(
      screen.queryByText('还没有导入知识库，请先到「知识管理」查看准备步骤。'),
    ).not.toBeInTheDocument();
    expect(input).toHaveValue('土豆');
  });
});
