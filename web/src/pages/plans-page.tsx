import { PixelCalendar } from '@/components/pixel-icons';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import Markdown from 'react-markdown';
import { Check, ClipboardList, Plus, Trash2 } from 'lucide-react';
import { readPlans, writePlans } from '@/lib/plans';
import { displayDate } from '@/lib/format';
import { EmptyState, useAction } from '@/components/feedback';
import { JsonDetails } from '@/components/record-detail';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useBootstrap } from '@/hooks/use-workbench';

export default function PlansPage() {
  const [plans, setPlans] = useState(readPlans);
  const [selected, setSelected] = useState<string[]>([]);
  const [remove, setRemove] = useState<string | null>(null);
  const { notify } = useAction();
  const { data: boot } = useBootstrap();
  const comparison = plans.filter((plan) => selected.includes(plan.id));
  return (
    <div className="page plans-page">
      <div className="page-heading">
        <div>
          <h1>
            <PixelCalendar />
            我的农场计划
          </h1>
          <p>保存当时的条件和回答，放在一起比较，再决定怎么做。</p>
        </div>
        <Link className="town-button" to="/chat">
          <Plus size={18} />
          制定新计划
        </Link>
      </div>
      <div className="plan-notice">
        <ClipboardList size={19} />
        <span>计划保存在当前浏览器。每份计划独立比较，不会扣减库存或推进游戏日期。</span>
      </div>
      {plans.length === 0 ? (
        <EmptyState
          icon={<PixelCalendar size={64} />}
          title="记录你的第一个计划"
          action={
            <Link
              className="town-button"
              to={`/chat?q=${encodeURIComponent('帮我比较土豆直接出售和加工的方案，需要我提供哪些条件？')}`}
            >
              和助手聊聊计划
            </Link>
          }
        >
          在对话回答下点击「保存为计划」，就能把方案收在这里。
        </EmptyState>
      ) : (
        <>
          <div className="section-heading">
            <h2>
              我的方案 <small>{plans.length}</small>
            </h2>
            <span className="muted">选择 2–3 份方案进行对照</span>
          </div>
          <div className="plans-grid">
            {plans.map((plan) => (
              <article
                className={`plan-card paper-panel ${selected.includes(plan.id) ? 'selected' : ''}`}
                key={plan.id}
              >
                <div className="section-heading">
                  <span className="tag">{displayDate(plan.createdAt)}保存</span>
                  <button
                    className="icon-button"
                    aria-label={`删除计划：${plan.title}`}
                    onClick={() => setRemove(plan.id)}
                  >
                    <Trash2 size={17} />
                  </button>
                </div>
                <h2>{plan.title}</h2>
                <p className="plan-excerpt">{plan.answer}</p>
                <p className="muted">
                  知识版本 {plan.snapshotId.slice(0, 8)} · 任务版本 {plan.revision}
                </p>
                {boot?.tasks.find((task) => task.task_id === plan.taskId)?.revision !==
                  plan.revision && (
                  <p className="saved-note">原对话已变化或不可用，这里保留保存时的结果。</p>
                )}
                <div className="button-row">
                  <button
                    className={`chip ${selected.includes(plan.id) ? 'selected' : ''}`}
                    aria-pressed={selected.includes(plan.id)}
                    onClick={() => {
                      if (selected.includes(plan.id))
                        setSelected(selected.filter((id) => id !== plan.id));
                      else if (selected.length < 3) setSelected([...selected, plan.id]);
                      else notify('一次最多比较三份方案。');
                    }}
                  >
                    {selected.includes(plan.id) ? <Check size={16} /> : <Plus size={16} />}加入对照
                  </button>
                  <Link className="text-link" to={`/chat/${plan.taskId}`}>
                    查看原对话
                  </Link>
                </div>
              </article>
            ))}
          </div>
          {comparison.length > 0 && (
            <section className="comparison">
              <div className="section-heading">
                <h2>方案对照</h2>
                <button className="text-link" onClick={() => setSelected([])}>
                  清空选择
                </button>
              </div>
              <p className="muted">
                先核对数量、品质和职业是否一致。以下是保存的结果，不会自动重新计算。
              </p>
              <div
                className="comparison-grid"
                style={{ '--columns': comparison.length } as React.CSSProperties}
              >
                {comparison.map((plan) => (
                  <article className="paper-panel" key={plan.id}>
                    <h3>{plan.title}</h3>
                    <JsonDetails title="计算时使用的条件" value={plan.inputs} />
                    <div className="markdown">
                      <Markdown>{plan.answer}</Markdown>
                    </div>
                    <Link className="text-link" to={`/chat/${plan.taskId}`}>
                      返回对话调整条件
                    </Link>
                  </article>
                ))}
              </div>
            </section>
          )}
        </>
      )}
      <Dialog open={Boolean(remove)} onOpenChange={(open) => !open && setRemove(null)}>
        <DialogContent className="town-dialog">
          <DialogHeader>
            <DialogTitle>删除这份计划？</DialogTitle>
            <DialogDescription>只删除浏览器中保存的这份副本，原对话仍然保留。</DialogDescription>
          </DialogHeader>
          <div className="button-row">
            <Button className="town-button secondary" onClick={() => setRemove(null)}>
              保留计划
            </Button>
            <Button
              className="town-button danger"
              onClick={() => {
                try {
                  const next = plans.filter((plan) => plan.id !== remove);
                  writePlans(next);
                  setPlans(next);
                  setSelected(selected.filter((id) => id !== remove));
                  setRemove(null);
                  notify('计划已删除。');
                } catch (error) {
                  notify(error instanceof Error ? error.message : '删除失败');
                }
              }}
            >
              删除计划
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
