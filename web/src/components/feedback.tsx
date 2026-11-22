import { createContext, useContext, useRef, useState, useEffect, type ReactNode } from 'react';
import { AlertCircle, LoaderCircle, X } from 'lucide-react';
import { errorMessage } from '@/lib/api';
import { Sprout } from './pixel-art';

const FeedbackContext = createContext<(message: string) => void>(() => {});

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState('');
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  function notify(text: string) {
    clearTimeout(timer.current);
    setMessage(text);
    timer.current = setTimeout(() => setMessage(''), 6500);
  }
  return (
    <FeedbackContext.Provider value={notify}>
      {children}
      {message && (
        <div className="toast" role="status">
          <AlertCircle size={20} />
          <span>{message}</span>
          <button aria-label="关闭提示" onClick={() => setMessage('')}>
            <X size={18} />
          </button>
        </div>
      )}
    </FeedbackContext.Provider>
  );
}

export function useAction() {
  const notify = useContext(FeedbackContext);
  const [pending, setPending] = useState(false);
  const lock = useRef(false);
  async function run<T>(action: () => Promise<T>): Promise<T | undefined> {
    if (lock.current) return;
    lock.current = true;
    setPending(true);
    try {
      return await action();
    } catch (error) {
      notify(errorMessage(error));
    } finally {
      lock.current = false;
      setPending(false);
    }
  }
  return { run, pending, notify };
}

export function Loading({ text = '正在整理农场笔记…' }: { text?: string }) {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={24} />
      {text}
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={24} />
      <div>
        <strong>这次没有加载成功</strong>
        <p>{errorMessage(error)}</p>
        {retry && (
          <button className="text-link" onClick={retry}>
            重新连接
          </button>
        )}
      </div>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon || <Sprout />}</div>
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </div>
  );
}
