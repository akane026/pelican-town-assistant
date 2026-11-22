// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LoginPage } from './auth';
import { api } from '@/lib/api';
vi.mock('@/lib/api', () => ({
  api: vi.fn(),
  setCsrf: vi.fn(),
  errorMessage: (e: Error) => e.message,
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
it('uses a single login entry regardless of role and only registers ordinary accounts', async () => {
  vi.mocked(api).mockRejectedValue(new Error('用户名或密码不正确'));
  render(
    <QueryClientProvider client={new QueryClient()}>
      <LoginPage />
    </QueryClientProvider>,
  );
  expect(screen.queryByText(/管理员/)).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '鹈鹕镇助手' })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'manager' } });
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'test-password-123' } });
  fireEvent.click(screen.getByRole('button', { name: '登录' }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith('/auth/login', {
      username: 'manager',
      password: 'test-password-123',
    }),
  );
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: '注册' }));
  fireEvent.click(screen.getByRole('button', { name: '注册' }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith('/auth/register', {
      username: 'manager',
      password: 'test-password-123',
    }),
  );
});
