import { useState } from 'react';
import { useMatch } from 'react-router-dom';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { useBootstrap, useTask, useRefreshTask } from '@/hooks/use-workbench';
import { useAction } from './feedback';
import { api } from '@/lib/api';
import type { ExecutionMode, Task, JsonObject } from '@/lib/types';
import { JsonDetails } from './record-detail';
import { ConnectionSettings } from './connection-settings';

export function TaskConditions({ task, onSaved }: { task: Task; onSaved?: () => void }) {
  const { run, pending, notify } = useAction();
  const refresh = useRefreshTask();
  const [advanced, setAdvanced] = useState(false);
  return (
    <form
      key={`${task.task_id}-${task.revision}`}
      className="conditions-form"
      onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        void run(async () => {
          const fields: JsonObject = advanced ? JSON.parse(String(form.get('json'))) : {};
          if (!advanced) {
            for (const key of ['season', 'quality', 'profession', 'day', 'quantity', 'watered']) {
              const value = String(form.get(key) || '');
              if (value)
                fields[key] = ['day', 'quantity'].includes(key)
                  ? Number(value)
                  : key === 'watered'
                    ? value === 'true'
                    : value;
            }
          }
          if (!Object.keys(fields).length) throw new Error('请至少填写一个已知条件。');
          await api('/state', { task_id: task.task_id, revision: task.revision, fields });
          await refresh(task.task_id);
          notify('条件已保存。继续提问时会按新条件计算。');
          onSaved?.();
        });
      }}
    >
      {!advanced ? (
        <div className="form-grid">
          <label>
            季节
            <select name="season" defaultValue={String(task.inputs.season || '')}>
              <option value="">未确定</option>
              <option value="Spring">春季</option>
              <option value="Summer">夏季</option>
              <option value="Fall">秋季</option>
              <option value="Winter">冬季</option>
            </select>
          </label>
          <label>
            日期
            <input
              name="day"
              type="number"
              min={1}
              max={28}
              placeholder="1–28"
              defaultValue={(task.inputs.day as number) ?? ''}
            />
          </label>
          <label>
            数量
            <input
              name="quantity"
              type="number"
              min={0}
              placeholder="物品数量…"
              defaultValue={(task.inputs.quantity as number) ?? ''}
            />
          </label>
          <label>
            品质
            <select name="quality" defaultValue={String(task.inputs.quality || '')}>
              <option value="">未确定</option>
              <option value="normal">普通</option>
              <option value="silver">银星</option>
              <option value="gold">金星</option>
              <option value="iridium">铱星</option>
            </select>
          </label>
          <label>
            职业
            <select name="profession" defaultValue={String(task.inputs.profession || '')}>
              <option value="">未确定</option>
              <option value="none">无加成</option>
              <option value="tiller">农耕人</option>
              <option value="artisan">工匠</option>
            </select>
          </label>
          <label>
            浇水情况
            <select
              name="watered"
              defaultValue={task.inputs.watered === undefined ? '' : String(task.inputs.watered)}
            >
              <option value="">未确定</option>
              <option value="true">每天浇水</option>
              <option value="false">未浇水</option>
            </select>
          </label>
        </div>
      ) : (
        <label>
          高级参数（JSON）
          <textarea
            name="json"
            rows={10}
            spellCheck={false}
            defaultValue={JSON.stringify(task.inputs, null, 2)}
          />
        </label>
      )}
      <div className="button-row">
        <Button className="town-button" disabled={pending}>
          保存条件
        </Button>
        <button type="button" className="text-link" onClick={() => setAdvanced(!advanced)}>
          {advanced ? '返回表单' : '高级参数'}
        </button>
      </div>
    </form>
  );
}

export function Settings({
  open,
  onClose,
  mode,
  setMode,
}: {
  open: boolean;
  onClose: () => void;
  mode: ExecutionMode;
  setMode: (mode: ExecutionMode) => void;
}) {
  const boot = useBootstrap();
  const match = useMatch('/chat/:taskId');
  const { data } = useTask(match?.params.taskId);
  return (
    <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
      <DialogContent className="town-dialog settings-dialog">
        <DialogHeader>
          <DialogTitle>农场设置</DialogTitle>
          <DialogDescription className="sr-only">模型连接、知识版本与游戏条件</DialogDescription>
        </DialogHeader>
        <ConnectionSettings onSaved={onClose} />
        <hr />
        <section className="settings-section" aria-labelledby="knowledge-mode-heading">
          <h3 id="knowledge-mode-heading">知识版本</h3>
          <label>
            新对话使用的知识
            <select value={mode} onChange={(event) => setMode(event.target.value as ExecutionMode)}>
              <option value="candidate_diagnostic">候选知识 · 诊断体验</option>
              <option value="released" disabled={!boot.data?.released}>
                已审核知识
              </option>
            </select>
          </label>
          <p className="muted">仅用于新对话</p>
        </section>
        <hr />
        <section className="settings-section" aria-labelledby="game-conditions-heading">
          <h3 id="game-conditions-heading">当前游戏条件</h3>
          {data ? <TaskConditions task={data.task} /> : <p className="muted">暂无进行中的对话</p>}
        </section>
        {data && (
          <JsonDetails
            title="当前任务版本"
            value={{
              snapshot: data.task.snapshot_id,
              revision: data.task.revision,
              mode: data.task.execution_mode,
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
