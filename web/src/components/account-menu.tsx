import { useRef, useState } from 'react';
import { DropdownMenu } from 'radix-ui';
import { ChevronsUpDown, LogOut, Settings, UserRound } from 'lucide-react';
import type { User } from './auth';
import { api } from '@/lib/api';
import { useAction } from './feedback';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';

function FarmerAvatar() {
  return (
    <svg
      className="farmer-avatar"
      viewBox="0 0 32 32"
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      <path fill="#e6eacb" d="M0 0h32v32H0z" />
      <path fill="#425d31" d="M6 26h4v-4h12v4h4v6H6z" />
      <path fill="#667eaa" d="M11 23h4v5h2v-5h4v9H11z" />
      <path fill="#6a442b" d="M8 10h16v9h-3v4H11v-4H8z" />
      <path fill="#efc791" d="M11 12h11v8h-3v4h-5v-4h-3z" />
      <path fill="#563823" d="M12 15h2v2h-2zM19 15h2v2h-2z" />
      <path fill="#a66a34" d="M4 9h24v4H4zM9 4h14v5H9z" />
      <path fill="#e7bd61" d="M10 4h12v4H10zM5 9h22v2H5z" />
    </svg>
  );
}

export function AccountMenu({
  user,
  onSettings,
  onAccount,
}: {
  user: User;
  onSettings: () => void;
  onAccount: () => void;
}) {
  const [open, setOpen] = useState(false);
  const openingDialog = useRef(false);
  const { run, pending } = useAction();
  return (
    <DropdownMenu.Root open={open} onOpenChange={setOpen}>
      <DropdownMenu.Trigger asChild>
        <button
          className="account-trigger"
          aria-label={`账户菜单：${user.username}`}
          disabled={pending}
        >
          <FarmerAvatar />
          <span className="account-username">{user.username}</span>
          <ChevronsUpDown size={16} aria-hidden="true" />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="account-menu"
          side="top"
          align="start"
          sideOffset={8}
          collisionPadding={16}
          onCloseAutoFocus={(event) => {
            if (openingDialog.current) {
              event.preventDefault();
              openingDialog.current = false;
            }
          }}
        >
          <DropdownMenu.Item
            className="account-menu-item"
            onSelect={() => {
              openingDialog.current = true;
              onSettings();
            }}
          >
            <Settings />
            设置
          </DropdownMenu.Item>
          <DropdownMenu.Item
            className="account-menu-item"
            onSelect={() => {
              openingDialog.current = true;
              onAccount();
            }}
          >
            <UserRound />
            查看账户
          </DropdownMenu.Item>
          <DropdownMenu.Separator className="account-menu-separator" />
          <DropdownMenu.Item
            className="account-menu-item account-menu-logout"
            disabled={pending}
            onSelect={() =>
              void run(async () => {
                await api('/auth/logout', {});
                window.location.assign('/login');
              })
            }
          >
            <LogOut />
            退出登录
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export function AccountDialog({
  user,
  open,
  onClose,
}: {
  user: User;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
      <DialogContent className="town-dialog account-dialog">
        <DialogHeader>
          <DialogTitle>我的账户</DialogTitle>
          <DialogDescription className="sr-only">当前登录账户的信息</DialogDescription>
        </DialogHeader>
        <div className="account-profile">
          <FarmerAvatar />
          <strong>{user.username}</strong>
        </div>
        <dl className="account-details">
          <div>
            <dt>用户名</dt>
            <dd>{user.username}</dd>
          </div>
          <div>
            <dt>身份</dt>
            <dd>{user.role === 'admin' ? '管理员' : '普通用户'}</dd>
          </div>
        </dl>
      </DialogContent>
    </Dialog>
  );
}
