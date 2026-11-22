import type { Bootstrap } from './types';
import { requireApiKey } from './credentials';

const errors: Record<string, string> = {
  AUTH_REQUIRED: '请先登录账号',
  ADMIN_REQUIRED: '只有管理员可以审核与发布知识',
  RESOURCE_DENIED: '你没有权限访问或修改这条记录',
  LIBRARY_NOT_FOUND: '这份资料不存在或已删除，请返回资料列表。',
  LIBRARY_STALE_REVISION: '资料已被其他页面修改或删除，请刷新后重试。',
  LIBRARY_INVALID_URL: '请输入公开 HTTPS 网页地址，不支持账号密码或自定义端口。',
  LIBRARY_PRIVATE_URL: '不能导入本机、内网或保留地址，请使用公开网页。',
  LIBRARY_FETCH_FAILED: '网页读取失败，请检查网址；若网站限制访问，可以上传已保存的 HTML 文件。',
  LIBRARY_REDIRECT_LIMIT: '网页跳转次数过多，请使用最终页面地址。',
  LIBRARY_WEB_FORMAT: '该地址没有返回支持的 HTML 或文本网页。',
  LIBRARY_SIZE_LIMIT: '资料不能超过 2 MB。',
  LIBRARY_UNSUPPORTED_FORMAT: '暂支持 TXT、Markdown、HTML、JSON 和 CSV 文件。',
  LIBRARY_UTF8_REQUIRED: '文件读取失败，请使用 UTF-8 编码的文本文件。',
  LIBRARY_EMPTY_CONTENT: '资料正文不能为空，且不能包含二进制内容。',
  LIBRARY_INVALID_JSON: 'JSON 文件内容格式不正确，请检查后重新保存。',
  LIBRARY_TITLE_REQUIRED: '请填写 1–160 字的资料名称。',
  LIBRARY_INVALID_FILENAME: '文件名称不合法，请重命名后上传。',
  API_KEY_REQUIRED: '请先在「设置 → 模型连接」中填写你的 ChatECNU API 密钥。',
  INVALID_API_KEY: '密钥格式不正确，请在设置中重新填写。',
  NO_RELEASED_SNAPSHOT: '还没有可用的知识库。请先在审核与发布中查看准备步骤。',
  ORIGIN_OR_CSRF_DENIED: '连接会话已过期，请刷新页面后重试。',
  STALE_TASK_REVISION: '任务条件已更新。请刷新任务，再提交你的修改。',
  TASK_BUSY: '助手正在处理这个问题，请等待完成或先停止生成。',
  REVIEW_REASON_REQUIRED: '请填写审核理由，再保存决定。',
  UNKNOWN_ENTITY_USE_SEARCH: '未找到这个物品，请通过搜索选择知识库中的物品。',
};

let csrf = '';
export function setCsrf(value: string) {
  csrf = value;
}

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
  if (response.status === 401 && path !== '/auth') window.location.assign('/login');
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
