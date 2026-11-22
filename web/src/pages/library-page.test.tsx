// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FeedbackProvider } from '@/components/feedback';
import { bootstrap } from '@/lib/api';
import type { LibraryDetail } from '@/lib/library';
import LibraryPage from './library-page';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('uploads, opens, edits, searches and deletes a source through the API', async () => {
  let row: LibraryDetail | null = null;
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    const body = options?.body ? JSON.parse(String(options.body)) : {};
    let result: unknown;
    if (url === '/api/bootstrap') result = { csrf: 'test-csrf' };
    else if (url === '/api/library/create') {
      expect(body.filename).toBe('notes.txt');
      expect(body.data).toBe(btoa('test original'));
      expect(options?.headers).toMatchObject({ 'X-CSRF-Token': 'test-csrf' });
      row = {
        id: 'test-source',
        title: '春季笔记',
        kind: 'file',
        filename: body.filename,
        content: 'test original',
        text_content: 'test original',
        url: '',
        revision: 1,
        status: 'pending_build',
        created_at: '2026-11-22',
        updated_at: '2026-11-22',
      };
      result = row;
    } else if (url === '/api/library/update') {
      expect(body.revision).toBe(1);
      row = {
        ...row!,
        title: body.title,
        content: body.content,
        text_content: body.content,
        revision: 2,
      };
      result = row;
    } else if (url === '/api/library/delete') {
      expect(body.revision).toBe(2);
      row = null;
      result = { status: 'DELETED' };
    } else if (url.startsWith('/api/library/source')) result = row;
    else result = { items: row ? [row] : [], total: row ? 1 : 0, offset: 0, limit: 20 };
    return new Response(JSON.stringify(result), {
      headers: { 'content-type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetcher);
  await bootstrap();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/library']}>
        <FeedbackProvider>
          <Routes>
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/library/:sourceId" element={<LibraryPage />} />
          </Routes>
        </FeedbackProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText('添加第一份农场资料')).toBeInTheDocument();
  fireEvent.click(screen.getAllByRole('button', { name: '添加资料' })[0]);
  fireEvent.change(screen.getByLabelText('资料名称（选填）'), { target: { value: '春季笔记' } });
  fireEvent.change(screen.getByLabelText(/选择知识文件/), {
    target: { files: [new File(['test original'], 'notes.txt', { type: 'text/plain' })] },
  });
  // jsdom's files assignment does not update native file-input validity.
  fireEvent.submit(screen.getByRole('button', { name: '保存资料' }).closest('form')!);
  expect(await screen.findByRole('heading', { name: '春季笔记' })).toBeInTheDocument();
  expect(screen.getByLabelText('资料正文')).toHaveTextContent('test original');
  expect(screen.getByText('待构图 · 尚未用于问答')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '编辑' }));
  fireEvent.change(screen.getByLabelText('资料名称'), { target: { value: '新的笔记' } });
  fireEvent.change(screen.getByLabelText('原始内容'), { target: { value: 'updated text' } });
  fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
  expect(await screen.findByRole('heading', { name: '新的笔记' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('link', { name: '返回资料列表' }));
  fireEvent.change(await screen.findByRole('textbox', { name: '搜索知识资料' }), {
    target: { value: 'updated' },
  });
  fireEvent.click(screen.getByRole('button', { name: '搜索' }));
  await waitFor(() =>
    expect(fetcher.mock.calls.some(([url]) => url.includes('q=updated'))).toBe(true),
  );
  fireEvent.click(await screen.findByRole('link', { name: /新的笔记/ }));
  fireEvent.click(await screen.findByRole('button', { name: '删除' }));
  fireEvent.click(screen.getByRole('button', { name: '确认删除' }));
  expect(await screen.findByText('添加第一份农场资料')).toBeInTheDocument();
});
