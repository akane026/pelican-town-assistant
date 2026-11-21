import type { Bootstrap } from './types';
import { requireApiKey } from './credentials';

const errors: Record<string, string> = {
  API_KEY_REQUIRED: '请先在「设置 → 连接与隐私」中填写你的 ChatECNU API 密钥。',
  INVALID_API_KEY: '密钥格式不正确，请在设置中重新填写。',
  NO_RELEASED_SNAPSHOT: '还没有可用的知识库。请先在知识管理中查看准备步骤。',
  ORIGIN_OR_CSRF_DENIED: '连接会话已过期，请刷新页面后重试。',
  STALE_TASK_REVISION: '任务条件已更新。请刷新任务，再提交你的修改。',
  TASK_BUSY: '助手正在处理这个问题，请等待完成或先停止生成。',
  REVIEW_REASON_REQUIRED: '请填写审核理由，再保存决定。',
  UNKNOWN_ENTITY_USE_SEARCH: '未找到这个物品，请通过搜索选择知识库中的物品。',
};

let csrf = '';

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '操作未完成，请重试。';
}

export async function api<T>(path: string, data?: unknown, signal?: AbortSignal): Promise<T> {
  if (data !== undefined && !csrf) throw new Error('工作台尚未连接，请稍后重试。');
  const response = await fetch(`/api${path}`, {
    signal,
    ...(data === undefined
      ? {}
      : {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrf,
            ...(path === '/chat' ? { Authorization: `Bearer ${requireApiKey()}` } : {}),
          },
          body: JSON.stringify(data),
        }),
  });
  if (!response.headers.get('content-type')?.includes('application/json')) {
    throw new Error('未连接到工作台接口，请确认 Python 后端已经启动。');
  }
  const result = await response.json();
  if (!response.ok)
    throw new Error(errors[result.error] || result.error || `请求失败（${response.status}）`);
  return result as T;
}

export async function bootstrap(signal?: AbortSignal) {
  const result = await api<Bootstrap>('/bootstrap', undefined, signal);
  csrf = result.csrf;
  return result;
}

export function queryString(values: Record<string, string | number | undefined>) {
  return new URLSearchParams(
    Object.entries(values)
      .filter((entry): entry is [string, string | number] => entry[1] !== undefined)
      .map(([key, value]) => [key, String(value)]),
  ).toString();
}

export function imageUrl(id: string, taskId?: string, uploaded = false) {
  return `/api/image?${queryString({ id, task_id: taskId, kind: uploaded ? 'upload' : undefined })}`;
}

export function safeSourceUrl(url: string) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' ? parsed.href : undefined;
  } catch {
    return undefined;
  }
}
