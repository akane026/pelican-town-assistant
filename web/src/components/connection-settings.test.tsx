// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { ConnectionSettings } from './connection-settings';
import { CREDENTIAL_KEY, hasApiKey, requireApiKey, setApiKey } from '@/lib/credentials';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  setApiKey('');
});

it('persists, replaces and removes a key without network calls', () => {
  const write = vi.spyOn(Storage.prototype, 'setItem');
  const fetcher = vi.spyOn(globalThis, 'fetch');
  const onSaved = vi.fn();
  render(<ConnectionSettings onSaved={onSaved} />);
  expect(screen.getByRole('status')).toHaveTextContent('首次使用');
  const input = screen.getByLabelText('ChatECNU API 密钥');
  expect(input).toHaveAttribute('type', 'password');
  for (const key of ['synthetic-first-key', 'synthetic-second-key']) {
    fireEvent.change(input, { target: { value: ` ${key} ` } });
    fireEvent.click(screen.getByRole('button', { name: '保存并返回' }));
    expect(requireApiKey()).toBe(key);
    expect(input).toHaveValue('');
    expect(screen.getByRole('status')).toHaveTextContent('已在当前浏览器中保存');
    expect(localStorage.getItem(CREDENTIAL_KEY)).toBe(key);
  }
  fireEvent.click(screen.getByRole('button', { name: '清除密钥' }));
  expect(hasApiKey()).toBe(false);
  expect(onSaved).toHaveBeenCalledTimes(2);
  expect(write).toHaveBeenCalledTimes(2);
  expect(localStorage.getItem(CREDENTIAL_KEY)).toBeNull();
  expect(fetcher).not.toHaveBeenCalled();
});

it('reports blocked storage without claiming to save or closing the dialog', () => {
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new DOMException('Blocked', 'SecurityError');
  });
  const onSaved = vi.fn();
  render(<ConnectionSettings onSaved={onSaved} />);
  fireEvent.change(screen.getByLabelText('ChatECNU API 密钥'), {
    target: { value: 'synthetic-key' },
  });
  fireEvent.click(screen.getByRole('button', { name: '保存并返回' }));
  expect(screen.getByRole('alert')).toHaveTextContent('存储权限');
  expect(hasApiKey()).toBe(false);
  expect(onSaved).not.toHaveBeenCalled();
});

it('shows an error if clearing is blocked and keeps the saved status', () => {
  setApiKey('synthetic-key');
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
    throw new DOMException('Blocked', 'SecurityError');
  });
  render(<ConnectionSettings onSaved={vi.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: '清除密钥' }));
  expect(screen.getByRole('alert')).toHaveTextContent('存储权限');
  expect(requireApiKey()).toBe('synthetic-key');
});

it('updates settings when another tab clears the credential', () => {
  setApiKey('synthetic-key');
  render(<ConnectionSettings onSaved={vi.fn()} />);
  localStorage.removeItem(CREDENTIAL_KEY);
  fireEvent(
    window,
    new StorageEvent('storage', {
      key: CREDENTIAL_KEY,
      storageArea: localStorage,
      newValue: null,
    }),
  );
  expect(screen.getByRole('status')).toHaveTextContent('首次使用');
  expect(screen.queryByRole('button', { name: '清除密钥' })).not.toBeInTheDocument();
});

it('rejects malformed keys without discarding the previous key', () => {
  setApiKey('synthetic-good-key');
  render(<ConnectionSettings onSaved={vi.fn()} />);
  fireEvent.change(screen.getByLabelText('ChatECNU API 密钥'), {
    target: { value: 'contains spaces' },
  });
  fireEvent.click(screen.getByRole('button', { name: '保存并返回' }));
  expect(screen.getByRole('alert')).toHaveTextContent('密钥格式不正确');
  expect(requireApiKey()).toBe('synthetic-good-key');
});
