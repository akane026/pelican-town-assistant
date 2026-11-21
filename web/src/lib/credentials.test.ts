// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';

afterEach(() => {
  localStorage.clear();
  vi.resetModules();
});

it('restores the saved key after reloading the application module', async () => {
  const first = await import('./credentials');
  first.setApiKey('synthetic-persisted-key');
  vi.resetModules();
  const reopened = await import('./credentials');
  expect(reopened.hasApiKey()).toBe(true);
  expect(reopened.requireApiKey()).toBe('synthetic-persisted-key');
  reopened.setApiKey('');
  vi.resetModules();
  const cleared = await import('./credentials');
  expect(cleared.hasApiKey()).toBe(false);
  expect(() => cleared.requireApiKey()).toThrow('连接与隐私');
});
