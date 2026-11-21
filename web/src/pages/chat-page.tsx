import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import Markdown from 'react-markdown';
import {
  BookmarkPlus,
  BookOpen,
  Coins,
  Download,
  ImagePlus,
  Send,
  Square,
  Star,
  Sprout as SproutIcon,
} from 'lucide-react';
import { api, queryString } from '@/lib/api';
import { requireApiKey } from '@/lib/credentials';
import type { ExecutionMode, Task } from '@/lib/types';
import { useBootstrap, useTask, useRefreshTask } from '@/hooks/use-workbench';
import { ErrorState, Loading, useAction } from '@/components/feedback';
import { Sprout } from '@/components/pixel-art';
import { Button } from '@/components/ui/button';
import { RecordDrawer, JsonDetails } from '@/components/record-detail';
import { TaskConditions } from '@/components/settings';
import { ImageInspector } from '@/components/image-inspector';
import { statusLabels } from '@/lib/format';
import { savePlan } from '@/lib/plans';

const prompts = [
  { label: '看图认物', icon: ImagePlus, text: '帮我辨认截图里的物品，并说明它的用途。' },
  { label: '收益计算', icon: Coins, text: '土豆直接出售和加工，哪种方式更合适？' },
  { label: '生长时间', icon: SproutIcon, text: '现在种下土豆，还来得及在这个季节收获吗？' },
  { label: '献祭准备', icon: Star, text: '帮我看看春季作物收集包还需要准备哪些东西。' },
];

export default function ChatPage({ mode }: { mode: ExecutionMode }) {
  const { taskId } = useParams();
  // Reset drafts and selected image candidates when navigating between conversations.
  return <Conversation key={taskId || 'new'} taskId={taskId} mode={mode} />;
}

function Conversation({ taskId, mode }: { taskId?: string; mode: ExecutionMode }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [draft, setDraft] = useState(params.get('q') || '');
  const [recordId, setRecordId] = useState<string | null>(null);
  const [showConditions, setShowConditions] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const { data: boot } = useBootstrap();
  const detail = useTask(taskId);
  const refresh = useRefreshTask();
  const { run, pending, notify } = useAction();
  const input = useRef<HTMLTextAreaElement>(null);
  const upload = useRef<HTMLInputElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const task = detail.data?.task;
  const messages = detail.data?.messages || [];
  const running = Boolean(detail.data?.running);
  const welcome = !taskId;
  const capabilities = useQuery({
    queryKey: ['capabilities', taskId, task?.revision],
    enabled: Boolean(taskId && showTrace),
    queryFn: ({ signal }) =>
      api(`/capabilities?${queryString({ task_id: taskId })}`, undefined, signal),
  });
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'nearest' });
  }, [messages.length]);

  async function ensureTask(): Promise<Task> {
    if (task) return task;
    if (!boot?.snapshot) throw new Error('还没有导入知识库，请先到「知识管理」查看准备步骤。');
    return api<Task>('/task', { mode });
  }

  function send(event: FormEvent) {
    event.preventDefault();
    if (!draft.trim() || pending || running) return;
    void run(async () => {
      requireApiKey();
      const current = await ensureTask();
      await api('/chat', { task_id: current.task_id, message: draft.trim() });
      setDraft('');
      if (!taskId) navigate(`/chat/${current.task_id}`);
      await refresh(current.task_id);
    });
  }

  async function uploadFile(file: File) {
    if (file.size > 10_000_000) throw new Error('图片不能超过 10 MB。');
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type))
      throw new Error('请选择 PNG、JPG 或 WebP 图片。');
    const current = await ensureTask();
    const data = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('无法读取这张图片。'));
      reader.onload = () => resolve(String(reader.result).split(',')[1]);
      reader.readAsDataURL(file);
    });
    await api('/upload', { task_id: current.task_id, data });
    if (!taskId) navigate(`/chat/${current.task_id}`);
    await refresh(current.task_id);
  }

  if (taskId && detail.isLoading) return <Loading />;
  if (detail.error) return <ErrorState error={detail.error} retry={() => void detail.refetch()} />;
  return (
    <div className={`chat-page ${welcome ? 'welcome-page' : 'active-chat'}`}>
      {welcome ? (
        <div className="welcome-heading">
          <Sprout className="hero-sprout" />
          <h1>今天，想解决什么农场难题？</h1>
          <p>查资料、认物品、算收益</p>
        </div>
      ) : (
        <div className="conversation-header">
          <div>
            <h1>我的农场笔记</h1>
            <span className="muted">
              {task?.execution_mode === 'released' ? '已审核知识' : '候选知识 · 待人工核验'} · 版本{' '}
              {task?.snapshot_id.slice(0, 8)}
            </span>
          </div>
          <div className="button-row">
            <button className="chip" onClick={() => setShowConditions(!showConditions)}>
              游戏条件
            </button>
            {task && (
              <a
                className="icon-button"
                href={`/api/export?${queryString({ id: task.task_id, task_id: task.task_id, format: 'md' })}`}
                download="农场笔记.md"
                aria-label="导出对话"
              >
                <Download size={19} />
              </a>
            )}
          </div>
        </div>
      )}
      {!welcome && (
        <div className="conversation-body">
          {messages.length === 0 && (
            <div className="small-empty">
              <Sprout />
              <p>笔记已经打开，说说你的农场问题吧。</p>
            </div>
          )}
          {messages.map((message, index) => (
            <article
              key={index}
              className={`message ${message.role === 'user' ? 'user-message' : 'assistant-message'}`}
            >
              <div className="message-label">
                {message.role === 'user' ? (
                  '你'
                ) : (
                  <>
                    <SproutIcon size={18} /> 农场助手
                  </>
                )}
              </div>
              <div className="message-content markdown">
                <Markdown>
                  {typeof message.content === 'string'
                    ? message.content
                    : message.content.answer_text || '当前步骤没有文本结果。'}
                </Markdown>
              </div>
              {typeof message.content !== 'string' &&
                Boolean(message.content.claim_evidence_refs?.length) && (
                  <div className="source-chips">
                    {message.content.claim_evidence_refs?.map((id, i) => (
                      <button className="chip" key={id} onClick={() => setRecordId(id)}>
                        <BookOpen size={14} />
                        依据 {i + 1}
                      </button>
                    ))}
                  </div>
                )}
            </article>
          ))}
          {task?.status === 'ERROR' && (
            <ErrorState
              error={
                new Error(task.answer?.answer_text || '请求中断，已保存此前工具结果。请重试。')
              }
            />
          )}
          {running && (
            <Loading
              text={task?.status === 'CANCELLED' ? '正在结束当前请求…' : '正在查阅资料与计算…'}
            />
          )}
          {task && (showConditions || task.status === 'NEEDS_INPUT') && (
            <section className="paper-panel">
              <h3>补充一下游戏条件</h3>
              <TaskConditions task={task} onSaved={() => setShowConditions(false)} />
            </section>
          )}
          {task && task.uploaded_images.length > 0 && (
            <ImageInspector
              key={task.uploaded_images.at(-1)?.image_id}
              task={task}
              busy={running}
            />
          )}
          {task && !running && task.answer && (
            <div className="answer-actions">
              <button
                className="chip"
                onClick={() => {
                  try {
                    savePlan(task);
                    notify('已保存到「我的计划」，可与其他方案比较。');
                  } catch (error) {
                    notify(error instanceof Error ? error.message : '保存失败');
                  }
                }}
              >
                <BookmarkPlus size={17} />
                保存为计划
              </button>
              <Link className="chip" to="/plans">
                查看我的计划
              </Link>
            </div>
          )}
          {task && (
            <details
              className="trace-section"
              onToggle={(event) => setShowTrace(event.currentTarget.open)}
            >
              <summary>
                <BookOpen size={17} /> 来源与计算过程{' '}
                <span>{statusLabels[task.status] || task.status}</span>
              </summary>
              <JsonDetails title="本轮目标覆盖情况" value={task.goal_coverage || {}} />
              <JsonDetails title="已执行工具与证据记录" value={detail.data?.events || []} />
              {capabilities.error && <ErrorState error={capabilities.error} />}
              {capabilities.data ? (
                <JsonDetails title="当前能力与缺失条件" value={capabilities.data} />
              ) : null}
            </details>
          )}
          <div ref={end} />
        </div>
      )}
      <div className="composer-area">
        <form className="composer" onSubmit={send}>
          <label className="sr-only" htmlFor="farm-question">
            你的农场问题
          </label>
          <textarea
            ref={input}
            id="farm-question"
            name="message"
            maxLength={12000}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={
              welcome
                ? '例如：先留出献祭用的土豆，剩下的怎么处理？'
                : '继续说说你的问题，或补充已知条件…'
            }
            rows={welcome ? 4 : 2}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <div className="composer-toolbar">
            <Button
              type="button"
              className="town-button secondary upload-button"
              disabled={pending || running}
              onClick={() => upload.current?.click()}
            >
              <ImagePlus size={19} />
              上传截图
            </Button>
            <input
              ref={upload}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="sr-only"
              tabIndex={-1}
              aria-label="选择游戏截图"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = '';
                if (file) void run(() => uploadFile(file));
              }}
            />
            <span className="keyboard-hint">Enter 发送 · Shift + Enter 换行</span>
            {running ? (
              <Button
                type="button"
                className="town-button secondary"
                disabled={pending || task?.status === 'CANCELLED'}
                onClick={() =>
                  void run(async () => {
                    await api('/cancel', { task_id: taskId, revision: task?.revision });
                    await refresh(taskId!);
                  })
                }
              >
                <Square size={16} />
                停止
              </Button>
            ) : (
              <Button
                className="town-button send-button"
                type="submit"
                disabled={pending || !draft.trim()}
              >
                {pending ? '正在发送…' : '发送'}
                <Send size={17} />
              </Button>
            )}
          </div>
        </form>
        {welcome && (
          <>
            <div className="prompt-grid">
              {prompts.map(({ label, icon: Icon, text }) => (
                <button
                  key={label}
                  className="prompt-chip"
                  onClick={() => {
                    setDraft(text);
                    input.current?.focus();
                  }}
                >
                  <Icon size={24} />
                  {label}
                </button>
              ))}
            </div>
            <p className="welcome-footnote">答案可展开查看来源原文与计算过程</p>
          </>
        )}
      </div>
      <footer className="farm-footer">
        <span />
        <SproutIcon size={16} />
        不会修改游戏存档
        <SproutIcon size={16} />
        <span />
      </footer>
      <RecordDrawer id={recordId} taskId={taskId} onClose={() => setRecordId(null)} />
    </div>
  );
}
