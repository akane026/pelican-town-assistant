// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { AccountMenu, AccountDialog } from './account-menu';
const user = { id: 'test-user', username: 'farm_resident', role: 'user' as const };
afterEach(cleanup);
it('opens the account menu by keyboard and routes settings and account actions', async () => {
  const onSettings = vi.fn(),
    onAccount = vi.fn();
  render(<AccountMenu user={user} onSettings={onSettings} onAccount={onAccount} />);
  const trigger = screen.getByRole('button', { name: '账户菜单：farm_resident' });
  fireEvent.keyDown(trigger, { key: 'ArrowDown' });
  expect(await screen.findByRole('menuitem', { name: '退出登录' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('menuitem', { name: '设置' }));
  expect(onSettings).toHaveBeenCalledOnce();
  fireEvent.keyDown(trigger, { key: 'ArrowDown' });
  fireEvent.click(await screen.findByRole('menuitem', { name: '查看账户' }));
  expect(onAccount).toHaveBeenCalledOnce();
});
it('shows actual account identity without exposing credentials', () => {
  render(<AccountDialog user={user} open onClose={vi.fn()} />);
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  expect(screen.getByText('普通用户')).toBeInTheDocument();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
});
