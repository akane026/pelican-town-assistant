// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, bootstrap, safeSourceUrl } from './api';
import { setApiKey } from './credentials';

afterEach(() => {
  vi.unstubAllGlobals();
  setApiKey('');
});
describe('workbench requests', () => {
  it('sends the current key only with chat headers, never in task data or read requests', async () => {
    const fetcher = vi.fn().mockImplementation(
      async () =>
        new Response(JSON.stringify({ csrf: 'test-token' }), {
          headers: { 'content-type': 'application/json' },
        }),
    );
    vi.stubGlobal('fetch', fetcher);
    setApiKey('synthetic-first-key');
    await bootstrap();
    await api('/task', { mode: 'released' });
    const body = { task_id: 'test', message: '土豆多少钱？' };
    await api('/chat', body);
    expect(fetcher.mock.calls[0][1].headers).toBeUndefined();
    expect(fetcher.mock.calls[1][1].headers.Authorization).toBeUndefined();
    expect(fetcher.mock.calls[2][1].headers.Authorization).toBe('Bearer synthetic-first-key');
    expect(JSON.parse(fetcher.mock.calls[2][1].body)).toEqual(body);
    setApiKey('synthetic-second-key');
    await api('/chat', body);
    expect(fetcher.mock.calls[3][1].headers.Authorization).toBe('Bearer synthetic-second-key');
    setApiKey('');
    await expect(api('/chat', body)).rejects.toThrow('连接与隐私');
    expect(fetcher).toHaveBeenCalledTimes(4);
  });
  it('uses the bootstrap token for a write and preserves server conflict errors', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrf: 'session-token' }), {
          headers: { 'content-type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: 'STALE_TASK_REVISION' }), {
          status: 400,
          headers: { 'content-type': 'application/json' },
        }),
      );
    vi.stubGlobal('fetch', fetcher);
    await bootstrap();
    await expect(api('/state', { revision: 3 })).rejects.toThrow('任务条件已更新');
    expect(fetcher.mock.calls[1][1].headers['X-CSRF-Token']).toBe('session-token');
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ revision: 3 });
  });
  it('explains a static-only preview instead of parsing HTML as API data', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response('<html></html>', { headers: { 'content-type': 'text/html' } }),
        ),
    );
    await expect(api('/bootstrap')).rejects.toThrow('Python 后端');
  });
  it('never opens an executable source URL', () => {
    expect(safeSourceUrl('javascript:alert(1)')).toBeUndefined();
    expect(safeSourceUrl('https://stardewvalleywiki.com/Potato')).toBe(
      'https://stardewvalleywiki.com/Potato',
    );
  });
});
