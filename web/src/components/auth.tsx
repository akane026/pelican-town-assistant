import { setAccountScope } from '@/lib/account';
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, setCsrf, errorMessage } from '@/lib/api';
import { Sprout } from './pixel-art';
import { UserRound, LockKeyhole } from 'lucide-react';
export interface User {
  id: string;
  username: string;
  role: 'admin' | 'user';
}
export function useAuth() {
  return useQuery({
    queryKey: ['auth'],
    queryFn: async () => {
      const result = await api<{ user: User | null; setup: boolean; csrf: string }>('/auth');
      setCsrf(result.csrf);
      setAccountScope(result.user?.id || '');
      return result;
    },
    retry: false,
  });
}
export function LoginPage() {
  const [register, setRegister] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const client = useQueryClient();
  return (
    <main className="login-page">
      <section className="login-landscape" aria-label="星露谷春季场景">
        <img src="/images/stardew-valley-spring.png" alt="星露谷春季的乡间小路、树木与木屋" />
      </section>
      <section className="login-panel">
        <div className="login-form-wrap">
          <img
            className="login-logo pixel-art"
            src="/images/pelican-logo.svg"
            alt="鹈鹕 logo"
            width="112"
            height="126"
          />
          <h1 className="login-name">鹈鹕镇助手</h1>
          <form
            className="login-form"
            onSubmit={async (event) => {
              event.preventDefault();
              setPending(true);
              setError('');
              const data = new FormData(event.currentTarget);
              try {
                await api(`/auth/${register ? 'register' : 'login'}`, {
                  username: data.get('username'),
                  password: data.get('password'),
                });
                client.clear();
                location.assign('/chat');
              } catch (e) {
                setError(errorMessage(e));
              } finally {
                setPending(false);
              }
            }}
          >
            <label className="login-field">
              <UserRound aria-hidden="true" />
              <span className="sr-only">用户名</span>
              <input
                name="username"
                autoComplete="username"
                required
                minLength={3}
                maxLength={32}
                placeholder="用户名"
              />
            </label>
            <label className="login-field">
              <LockKeyhole aria-hidden="true" />
              <span className="sr-only">密码</span>
              <input
                name="password"
                type="password"
                autoComplete={register ? 'new-password' : 'current-password'}
                required
                minLength={register ? 6 : 1}
                maxLength={128}
                placeholder={register ? '至少 6 个字符' : '输入密码'}
              />
            </label>
            {error && (
              <p role="alert" className="login-error">
                {error}
              </p>
            )}
            <button className="login-submit" disabled={pending}>
              {pending ? '请稍候…' : register ? '注册' : '登录'}
            </button>
          </form>
          <button
            type="button"
            className="login-switch"
            disabled={pending}
            onClick={() => {
              setRegister(!register);
              setError('');
            }}
          >
            {register ? '返回登录' : '注册'}
          </button>
          <div className="login-ornament" aria-hidden="true">
            <Sprout />
          </div>
        </div>
      </section>
    </main>
  );
}
