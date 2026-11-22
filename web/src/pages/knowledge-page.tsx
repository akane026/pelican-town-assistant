import { PixelBook, PixelScroll, PixelCalendar } from '@/components/pixel-icons';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, History, RefreshCw, Search, X } from 'lucide-react';
import { api, queryString } from '@/lib/api';
import type { RecordDetail, ReviewData, Rule } from '@/lib/types';
import { readable, recordTitle, statusLabels } from '@/lib/format';
import { useBootstrap } from '@/hooks/use-workbench';
import { EmptyState, ErrorState, Loading, useAction } from '@/components/feedback';
import { Evidence, JsonDetails } from '@/components/record-detail';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

const tabs = [
  { value: 'sources', label: '资料来源', icon: PixelBook },
  { value: 'review', label: '知识审核', icon: PixelScroll },
  { value: 'versions', label: '版本发布', icon: PixelScroll },
  { value: 'evaluation', label: '评测记录', icon: PixelCalendar },
];

function Preparation() {
  return (
    <div className="preparation paper-panel">
      <div className="preparation-title">
        <PixelBook size={48} />
        <div>
          <h2>准备可用于问答的知识</h2>
          <p>当前尚无知识快照。上传原文后，还需构图、审核与发布。</p>
        </div>
      </div>
      <ol className="preparation-steps">
        <li>
          <strong>准备 Wiki 原文与图片</strong>
          <p>在「知识资料」上传文件或导入网页，保留原文供核对。</p>
        </li>
        <li>
          <strong>校验资料并构建知识库</strong>
          <p>由项目维护者将资料纳入建库清单，在终端构建知识快照。</p>
        </li>
        <li>
          <strong>刷新并核对知识</strong>
          <p>候选快照就绪后，可在「知识审核」查看证据，批准可靠记录，再发布知识子集。</p>
        </li>
      </ol>
      <details className="help-details">
        <summary>维护者建库说明</summary>
        <p className="muted">
          按照项目 data/manifests 清单恢复资料，保留原始路径和哈希；新上传的资料需先转换到建库清单。
          在终端执行 ingest、build 和 snapshot，完整步骤见项目根目录 README。
          在线问答还需在农场设置中填写个人 API 密钥，并由后端配置模型地址和大于 0 的调用上限。
        </p>
      </details>
      <Link className="text-link" to="/library">
        上传或查看知识资料 →
      </Link>
      <Link className="text-link" to="/graph?example=1">
        先体验物品图谱的交互示例
      </Link>
    </div>
  );
}

function RuleReview({ rule }: { rule: Rule }) {
  const [reason, setReason] = useState('');
  const { run, pending, notify } = useAction();
  const client = useQueryClient();
  return (
    <details className="rule-review">
      <summary>
        {rule.description}
        <span className="tag">{statusLabels[rule.audit.status] || rule.audit.status}</span>
      </summary>
      <JsonDetails title="规则实现与审计记录" value={rule} />
      <label>
        规则审核理由
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="核对实现与来源后，记录判断依据…"
        />
      </label>
      <div className="button-row">
        {[
          ['approve', '批准规则'],
          ['defer', '暂缓'],
          ['reject', '拒绝'],
        ].map(([action, label]) => (
          <Button
            className={`town-button ${action === 'approve' ? '' : 'secondary'}`}
            key={action}
            disabled={pending || !reason.trim()}
            onClick={() =>
              void run(async () => {
                await api('/rule-review', { rule_id: rule.rule_id, action, reason });
                await client.invalidateQueries({ queryKey: ['bootstrap'] });
                notify('规则审核已保存。');
              })
            }
          >
            {label}
          </Button>
        ))}
      </div>
    </details>
  );
}

function ReviewPanel() {
  const boot = useBootstrap();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const kind = params.get('kind') || 'relations';
  const offset = Math.max(0, Number(params.get('offset')) || 0);
  const search = params.get('q') || '';
  const [draft, setDraft] = useState(search);
  const [selected, setSelected] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const { run, pending, notify } = useAction();
  const review = useQuery({
    queryKey: ['review', kind, offset, search, boot.data?.snapshot?.snapshot_id],
    queryFn: ({ signal }) =>
      api<ReviewData>(`/review?${queryString({ kind, offset, q: search })}`, undefined, signal),
  });
  const record = useQuery({
    queryKey: ['record', selected],
    enabled: Boolean(selected),
    queryFn: ({ signal }) =>
      api<RecordDetail>(`/record?${queryString({ id: selected! })}`, undefined, signal),
  });
  function update(values: Record<string, string>) {
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      Object.entries(values).forEach(([key, value]) => next.set(key, value));
      return next;
    });
    setSelected(null);
    setReason('');
  }
  return (
    <>
      <div className="review-toolbar">
        <label className="sr-only" htmlFor="record-kind">
          记录类型
        </label>
        <select
          id="record-kind"
          value={kind}
          onChange={(event) => update({ kind: event.target.value, offset: '0' })}
        >
          <option value="relations">物品关系</option>
          <option value="facts">知识事实</option>
          <option value="alignments">图文对齐</option>
        </select>
        <form
          className="search-field"
          onSubmit={(event) => {
            event.preventDefault();
            update({ q: draft, offset: '0' });
          }}
        >
          <Search size={18} />
          <input
            aria-label="搜索审核记录"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="搜索实体、关系或来源…"
          />
          <button>筛选</button>
        </form>
      </div>
      {review.isLoading && <Loading />}
      {review.error && <ErrorState error={review.error} retry={() => void review.refetch()} />}
      {review.data && (
        <>
          <div className="review-workspace">
            <aside className="review-list paper-panel">
              <h2>
                待核对记录 <small>{review.data.total}</small>
              </h2>
              {review.data.items.length ? (
                review.data.items.map((item) => (
                  <button
                    className={`review-row ${selected === item.record.id ? 'selected' : ''}`}
                    key={item.record.id}
                    onClick={() => {
                      setSelected(item.record.id);
                      setReason(item.decision?.reason || '');
                    }}
                  >
                    <strong>{recordTitle(item.record)}</strong>
                    <small>
                      {readable(item.record.predicate || item.record.method || '图文对齐')}
                    </small>
                    <span className="tag">
                      {statusLabels[item.decision?.action || 'candidate']}
                    </span>
                  </button>
                ))
              ) : (
                <p className="muted">没有匹配的记录。</p>
              )}
              <div className="pagination">
                <Button
                  className="town-button secondary"
                  disabled={offset === 0}
                  onClick={() => update({ offset: String(Math.max(0, offset - 30)) })}
                >
                  上一页
                </Button>
                <Button
                  className="town-button secondary"
                  disabled={offset + 30 >= review.data.total}
                  onClick={() => update({ offset: String(offset + 30) })}
                >
                  下一页
                </Button>
              </div>
              <small className="muted">
                已处理 {review.data.decisions_count} 条 · 第 {Math.floor(offset / 30) + 1} 页
              </small>
            </aside>
            <section className="review-detail paper-panel">
              {!selected ? (
                <EmptyState icon={<PixelBook size={64} />} title="让每条知识都有据可查">
                  从左侧选择记录，对照原文和图片，再填写审核意见。
                </EmptyState>
              ) : record.isLoading ? (
                <Loading />
              ) : record.error ? (
                <ErrorState error={record.error} />
              ) : (
                record.data && (
                  <>
                    <Evidence data={record.data} />
                    <hr />
                    <label>
                      审核意见
                      <textarea
                        rows={3}
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder="记录你的判断与依据…"
                      />
                    </label>
                    <div className="button-row review-actions">
                      {[
                        { action: 'approve', text: '批准此条', icon: Check },
                        { action: 'defer', text: '保留待审', icon: History },
                        { action: 'reject', text: '拒绝', icon: X },
                      ].map(({ action, text, icon: Icon }) => (
                        <Button
                          key={action}
                          className={`town-button ${action === 'approve' ? '' : 'secondary'}`}
                          disabled={pending || !reason.trim()}
                          onClick={() =>
                            void run(async () => {
                              await api('/review', {
                                snapshot_id: record.data!.snapshot_id,
                                id: selected,
                                action,
                                reason,
                              });
                              await client.invalidateQueries({ queryKey: ['review'] });
                              notify('审核决定已保存，发布请前往「版本发布」。');
                            })
                          }
                        >
                          <Icon size={17} />
                          {text}
                        </Button>
                      ))}
                    </div>
                  </>
                )
              )}
            </section>
          </div>
          <JsonDetails title="当前知识质量报告" value={review.data.quality} />
        </>
      )}
      <section className="rules-section">
        <h2>计算规则审核</h2>
        <p className="muted">知识记录和计算规则分别审核。请核对实现与来源后再批准。</p>
        {boot.data?.rules.map((rule) => (
          <RuleReview key={rule.rule_id} rule={rule} />
        ))}
      </section>
    </>
  );
}

function Evaluations() {
  const query = useQuery({
    queryKey: ['evaluations'],
    queryFn: ({ signal }) => api<Record<string, unknown>>('/evaluations', undefined, signal),
  });
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} retry={() => void query.refetch()} />;
  return Object.keys(query.data || {}).length ? (
    <div className="evaluation-list">
      {Object.entries(query.data!).map(([key, value]) => (
        <article key={key} className="paper-panel">
          <h2>{key}</h2>
          <JsonDetails title="查看评测结果" value={value} />
        </article>
      ))}
    </div>
  ) : (
    <EmptyState icon={<PixelCalendar size={64} />} title="还没有评测报告">
      后端生成评测结果后，会在这里展示。单次对话的工具记录可在回答下展开查看。
    </EmptyState>
  );
}

export default function KnowledgePage() {
  const boot = useBootstrap();
  const [params, setParams] = useSearchParams();
  const tab = tabs.some((item) => item.value === params.get('tab'))
    ? params.get('tab')!
    : 'sources';
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishResult, setPublishResult] = useState<unknown>(null);
  const { run, pending, notify } = useAction();
  const snapshot = boot.data?.snapshot;
  return (
    <div className="page knowledge-page">
      <div className="page-heading">
        <div>
          <h1>
            <PixelScroll />
            审核与发布
          </h1>
          <p>核对原文与关系，发布可用于问答的知识</p>
        </div>
        <Button
          className="town-button secondary"
          disabled={boot.isFetching}
          onClick={() => void boot.refetch()}
        >
          <RefreshCw size={17} />
          刷新知识状态
        </Button>
      </div>
      <Tabs value={tab} onValueChange={(value) => setParams({ tab: value })}>
        <TabsList className="knowledge-tabs">
          {tabs.map(({ value, label, icon: Icon }) => (
            <TabsTrigger className="knowledge-tab" key={value} value={value}>
              <Icon size={24} />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="sources">
          {!snapshot ? (
            <Preparation />
          ) : (
            <>
              <div className="knowledge-metrics">
                {[
                  ['entities', '物品与实体'],
                  ['relations', '物品关系'],
                  ['assets', '来源图片'],
                  ['evidence', '原文证据'],
                ].map(([key, label]) => (
                  <div key={key}>
                    <strong>{snapshot.counts?.[key] ?? '—'}</strong>
                    <span>{label}</span>
                  </div>
                ))}
              </div>
              <section className="paper-panel">
                <h2>当前候选知识库</h2>
                <p className="muted">
                  选择知识审核中的记录，可以查看各条原文及其链接；这里显示已导入版本的清单。
                </p>
                <JsonDetails title="查看快照清单" value={snapshot} />
                <Link className="text-link" to="/knowledge?tab=review">
                  开始核对知识
                </Link>
              </section>
            </>
          )}
        </TabsContent>
        <TabsContent value="review">{snapshot ? <ReviewPanel /> : <Preparation />}</TabsContent>
        <TabsContent value="versions">
          <section className="paper-panel release-panel">
            <PixelScroll size={48} />
            <h2>让可靠的知识进入正式回答</h2>
            <p>只发布人工批准且满足依赖要求的知识子集。候选记录与旧快照会保留。</p>
            <div className="release-status">
              <div>
                <span>候选版本</span>
                <strong>{snapshot ? snapshot.snapshot_id.slice(0, 12) : '尚未导入'}</strong>
              </div>
              <div>
                <span>正式版本</span>
                <strong>{boot.data?.released ? '已有发布记录' : '尚未发布'}</strong>
              </div>
            </div>
            {boot.data?.released && (
              <JsonDetails title="正式版本发布记录" value={boot.data.released} />
            )}
            <Button
              className="town-button"
              disabled={!snapshot || pending}
              onClick={() => setPublishOpen(true)}
            >
              检查并发布已审核知识
            </Button>
            {publishResult ? <JsonDetails title="本次发布检查结果" value={publishResult} /> : null}
          </section>
        </TabsContent>
        <TabsContent value="evaluation">
          <Evaluations />
        </TabsContent>
      </Tabs>
      <Dialog open={publishOpen} onOpenChange={setPublishOpen}>
        <DialogContent className="town-dialog">
          <DialogHeader>
            <DialogTitle>发布已批准的知识子集</DialogTitle>
            <DialogDescription>
              后端会检查审核与依赖关系。通过后，新对话可使用新版本；已有对话仍绑定原来的知识版本。
            </DialogDescription>
          </DialogHeader>
          <div className="button-row">
            <Button className="town-button secondary" onClick={() => setPublishOpen(false)}>
              返回核对
            </Button>
            <Button
              className="town-button"
              disabled={pending}
              onClick={() =>
                void run(async () => {
                  const result = await api<{ status?: string }>('/publish', {
                    snapshot_id: snapshot?.snapshot_id,
                  });
                  setPublishResult(result);
                  setPublishOpen(false);
                  await boot.refetch();
                  notify(
                    result.status === 'BLOCKED'
                      ? '发布被阻止，请查看检查结果并补齐审核。'
                      : '发布检查已完成，请查看结果。',
                  );
                })
              }
            >
              确认检查并发布
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
