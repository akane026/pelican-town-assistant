import { PixelBook, PixelScroll, PixelGlobe } from '@/components/pixel-icons';
import { useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Plus, Search, Pencil, Trash2 } from 'lucide-react';
import { api, queryString, safeSourceUrl } from '@/lib/api';
import type { LibraryDetail, LibraryList } from '@/lib/library';
import { ErrorState, Loading, EmptyState, useAction } from '@/components/feedback';
import { Button } from '@/components/ui/button';
import { LibraryImport } from '@/components/library-import';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';

function date(value: string) {
  return new Date(value).toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' });
}

export default function LibraryPage() {
  const { sourceId } = useParams();
  const [importOpen, setImportOpen] = useState(false);
  return (
    <div className="page library-page">
      <div className="page-heading">
        <div>
          <h1>
            <PixelBook /> 知识资料
          </h1>
          <p>把农场资料收进书架，随时翻阅与整理。</p>
        </div>
        <Button className="town-button library-add-button" onClick={() => setImportOpen(true)}>
          <Plus size={18} /> 添加资料
        </Button>
      </div>
      {sourceId ? (
        <SourceDetail key={sourceId} sourceId={sourceId} />
      ) : (
        <SourceList onImport={() => setImportOpen(true)} />
      )}
      {importOpen && <LibraryImport onClose={() => setImportOpen(false)} />}
    </div>
  );
}

function SourceList({ onImport }: { onImport: () => void }) {
  const [params, setParams] = useSearchParams();
  const query = params.get('q') || '';
  const kind = params.get('kind') || '';
  const offset = Math.max(0, Number(params.get('offset')) || 0);
  const result = useQuery({
    queryKey: ['library', query, kind, offset],
    queryFn: ({ signal }) =>
      api<LibraryList>(`/library?${queryString({ q: query, kind, offset })}`, undefined, signal),
  });
  return (
    <>
      <div className="library-notice">
        资料保存在本机。新增、修改或删除资料后，需要重新构建知识快照才会影响回答。
        <Link to="/knowledge">构图、审核与发布 →</Link>
      </div>
      <form
        className="library-toolbar"
        key={`${query}:${kind}`}
        onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          setParams({
            q: String(form.get('q') || '').trim(),
            kind: String(form.get('kind') || ''),
          });
        }}
      >
        <label className="library-search">
          <Search size={18} />
          <input
            name="q"
            aria-label="搜索知识资料"
            maxLength={200}
            defaultValue={query}
            placeholder="搜索资料名称或正文…"
          />
        </label>
        <select name="kind" aria-label="资料类型" defaultValue={kind}>
          <option value="">全部类型</option>
          <option value="file">本地文件</option>
          <option value="web">网页</option>
        </select>
        <Button className="town-button secondary">搜索</Button>
      </form>
      {result.isLoading ? (
        <Loading text="正在打开知识书架…" />
      ) : result.error ? (
        <ErrorState error={result.error} retry={() => void result.refetch()} />
      ) : result.data?.items.length ? (
        <>
          <div className="library-list" aria-label="知识资料列表">
            <div className="library-list-heading">
              <span>资料 / 来源</span>
              <span>状态</span>
              <span>最后更新</span>
              <span />
            </div>
            {result.data.items.map((source) => (
              <Link className="library-row" key={source.id} to={`/library/${source.id}`}>
                <div className="library-row-title">
                  <span className="library-source-icon">
                    {source.kind === 'web' ? <PixelGlobe /> : <PixelScroll />}
                  </span>
                  <div>
                    <strong>{source.title}</strong>
                    <small>
                      {source.kind === 'web' ? source.url : source.filename} ·{' '}
                      {(source.characters || 0).toLocaleString()} 字
                    </small>
                  </div>
                </div>
                <span className="library-badge">待构图</span>
                <time dateTime={source.updated_at}>{date(source.updated_at)}</time>
                <span className="library-open">查看 →</span>
              </Link>
            ))}
          </div>
          <div className="library-pagination">
            <span>共 {result.data.total} 份资料</span>
            <div className="button-row">
              <Button
                className="town-button secondary"
                disabled={offset === 0}
                onClick={() =>
                  setParams({ q: query, kind, offset: String(Math.max(0, offset - 20)) })
                }
              >
                上一页
              </Button>
              <Button
                className="town-button secondary"
                disabled={offset + result.data.limit >= result.data.total}
                onClick={() => setParams({ q: query, kind, offset: String(offset + 20) })}
              >
                下一页
              </Button>
            </div>
          </div>
        </>
      ) : (
        <EmptyState
          icon={<PixelBook size={64} />}
          title={query || kind ? '没有找到符合条件的资料' : '添加第一份农场资料'}
          action={
            <Button className="town-button" onClick={onImport}>
              添加资料
            </Button>
          }
        >
          {query || kind
            ? '试试其他关键词或资料类型。'
            : '上传文件或导入网页，保留完整原文，方便之后构图和核对证据。'}
        </EmptyState>
      )}
    </>
  );
}

function SourceDetail({ sourceId }: { sourceId: string }) {
  const result = useQuery({
    queryKey: ['library-source', sourceId],
    queryFn: ({ signal }) =>
      api<LibraryDetail>(`/library/source?${queryString({ id: sourceId })}`, undefined, signal),
  });
  if (result.isLoading) return <Loading />;
  if (result.error) return <ErrorState error={result.error} retry={() => void result.refetch()} />;
  return (
    result.data && <SourceReader key={`${sourceId}:${result.data.revision}`} source={result.data} />
  );
}

function SourceReader({ source }: { source: LibraryDetail }) {
  const [editing, setEditing] = useState(false);
  const [raw, setRaw] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const { run, pending, notify } = useAction();
  const client = useQueryClient();
  const navigate = useNavigate();
  async function refresh() {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['library'] }),
      client.invalidateQueries({ queryKey: ['library-source', source.id] }),
    ]);
  }
  return (
    <>
      <Link className="text-link library-back" to="/library">
        <ArrowLeft size={17} /> 返回资料列表
      </Link>
      <section className="paper-panel library-reader">
        <div className="library-detail-heading">
          <div>
            <span className="library-badge">待构图 · 尚未用于问答</span>
            <h2>{source.title}</h2>
            <p className="muted">
              {source.kind === 'web' ? '网页快照' : source.filename} · 第 {source.revision} 版 ·{' '}
              {date(source.updated_at)}
            </p>
          </div>
          {!editing && (
            <div className="button-row">
              <Button className="town-button secondary" onClick={() => setEditing(true)}>
                <Pencil size={16} /> 编辑
              </Button>
              <Button className="town-button secondary" onClick={() => setDeleteOpen(true)}>
                <Trash2 size={16} /> 删除
              </Button>
            </div>
          )}
        </div>
        {source.url && (
          <a
            className="text-link library-url"
            href={safeSourceUrl(source.url)}
            target="_blank"
            rel="noreferrer"
          >
            查看原网页：{source.url}
          </a>
        )}
        {editing ? (
          <form
            className="library-form"
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              void run(async () => {
                await api('/library/update', {
                  id: source.id,
                  revision: source.revision,
                  title: String(data.get('title')),
                  content: String(data.get('content')),
                });
                await refresh();
                setEditing(false);
                notify('资料已保存；已有知识快照保持原样。');
              });
            }}
          >
            <label>
              资料名称
              <input
                name="title"
                maxLength={160}
                required
                defaultValue={source.title}
                disabled={pending}
              />
            </label>
            <label>
              原始内容
              <textarea
                name="content"
                className="library-editor"
                rows={18}
                required
                defaultValue={source.content}
                disabled={pending}
                spellCheck={false}
              />
            </label>
            <p className="muted">
              修改的是本地副本，不会修改原网站。HTML 可在保存后切换「正文」查看。
            </p>
            <div className="button-row">
              <Button className="town-button" disabled={pending}>
                {pending ? '保存中…' : '保存修改'}
              </Button>
              <Button
                type="button"
                className="town-button secondary"
                disabled={pending}
                onClick={() => setEditing(false)}
              >
                取消编辑
              </Button>
            </div>
          </form>
        ) : (
          <>
            <div className="button-row library-reader-tabs" aria-label="内容视图">
              <button className="chip" aria-pressed={!raw} onClick={() => setRaw(false)}>
                正文
              </button>
              <button className="chip" aria-pressed={raw} onClick={() => setRaw(true)}>
                原始内容
              </button>
            </div>
            <pre
              className="library-content"
              tabIndex={0}
              aria-label={raw ? '原始内容' : '资料正文'}
            >
              {raw ? source.content : source.text_content}
            </pre>
          </>
        )}
      </section>
      <Dialog
        open={deleteOpen}
        onOpenChange={(open) => {
          if (!pending) setDeleteOpen(open);
        }}
      >
        <DialogContent className="town-dialog library-dialog">
          <DialogHeader>
            <DialogTitle>删除这份资料？</DialogTitle>
            <DialogDescription>
              「{source.title}
              」的本地副本将被删除，无法撤销。已经生成的知识快照和历史对话不会被删除。
            </DialogDescription>
          </DialogHeader>
          <div className="button-row">
            <Button
              className="town-button secondary"
              disabled={pending}
              onClick={() => setDeleteOpen(false)}
            >
              保留资料
            </Button>
            <Button
              className="town-button"
              disabled={pending}
              onClick={() =>
                void run(async () => {
                  await api('/library/delete', { id: source.id, revision: source.revision });
                  client.removeQueries({ queryKey: ['library-source', source.id] });
                  await client.invalidateQueries({ queryKey: ['library'] });
                  navigate('/library');
                  notify('资料已删除。');
                })
              }
            >
              {pending ? '删除中…' : '确认删除'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
