import { useRef, useState, type PointerEvent } from 'react';
import { Scan, Search } from 'lucide-react';
import { api, imageUrl, queryString } from '@/lib/api';
import type { MatchResult, SearchEntity, Task } from '@/lib/types';
import { useRefreshTask } from '@/hooks/use-workbench';
import { useAction } from './feedback';
import { Button } from './ui/button';
import { JsonDetails } from './record-detail';

type Box = [number, number, number, number];
function point(event: PointerEvent<HTMLDivElement>): [number, number] {
  const bounds = event.currentTarget.getBoundingClientRect();
  return [
    Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
    Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)),
  ];
}

export function ImageInspector({ task, busy }: { task: Task; busy: boolean }) {
  const image = task.uploaded_images.at(-1);
  const start = useRef<[number, number] | null>(null);
  const [box, setBox] = useState<Box | null>(null);
  const [kind, setKind] = useState('item');
  const [result, setResult] = useState<MatchResult | null>(null);
  const [selected, setSelected] = useState('');
  const [search, setSearch] = useState('');
  const [matches, setMatches] = useState<SearchEntity[]>([]);
  const { run, pending, notify } = useAction();
  const refresh = useRefreshTask();
  if (!image) return null;
  const disabled = busy || pending;
  function recognize(bbox: Box) {
    if (disabled || !image) return;
    void run(async () => {
      const response = await api<MatchResult>('/region', {
        task_id: task.task_id,
        revision: task.revision,
        image_id: image.image_id,
        bbox,
        kind,
      });
      setResult(response);
      setSelected('');
      await refresh(task.task_id);
    });
  }
  return (
    <section className="image-inspector">
      <div className="section-heading">
        <h3>
          <Scan size={19} /> 看看这是什么
        </h3>
        <label className="inline-label">
          识别范围
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="item">物品</option>
            <option value="stage">生长阶段</option>
          </select>
        </label>
      </div>
      <p className="muted">拖动框选物品，或识别整张图片。候选结果需要你确认。</p>
      <div
        className="crop-area"
        onPointerDown={(event) => {
          if (disabled) return;
          start.current = point(event);
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (!start.current) return;
          const end = point(event);
          setBox([
            Math.min(start.current[0], end[0]),
            Math.min(start.current[1], end[1]),
            Math.max(start.current[0], end[0]),
            Math.max(start.current[1], end[1]),
          ]);
        }}
        onPointerCancel={() => {
          start.current = null;
        }}
        onPointerUp={(event) => {
          const begin = start.current;
          start.current = null;
          if (!begin) return;
          const end = point(event);
          const bounds: Box = [
            Math.min(begin[0], end[0]),
            Math.min(begin[1], end[1]),
            Math.max(begin[0], end[0]),
            Math.max(begin[1], end[1]),
          ];
          if (bounds[2] - bounds[0] > 0.01 && bounds[3] - bounds[1] > 0.01) recognize(bounds);
        }}
      >
        <img
          src={imageUrl(image.image_id, task.task_id, true)}
          width={image.width}
          height={image.height}
          alt="上传的游戏截图，可拖动选择识别区域"
          draggable={false}
        />
        {box && (
          <div
            className="crop-box"
            style={{
              left: `${box[0] * 100}%`,
              top: `${box[1] * 100}%`,
              width: `${(box[2] - box[0]) * 100}%`,
              height: `${(box[3] - box[1]) * 100}%`,
            }}
          />
        )}
      </div>
      <Button
        className="town-button secondary"
        disabled={disabled}
        onClick={() => {
          setBox([0, 0, 1, 1]);
          recognize([0, 0, 1, 1]);
        }}
      >
        识别整张图片
      </Button>
      <details className="json-details">
        <summary>精确选择区域（键盘可用）</summary>
        <form
          className="form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            const bounds = ['left', 'top', 'right', 'bottom'].map(
              (key) => Number(form.get(key)) / 100,
            ) as Box;
            if (bounds[0] >= bounds[2] || bounds[1] >= bounds[3]) {
              notify('右边界与下边界需要大于起点。');
              return;
            }
            setBox(bounds);
            recognize(bounds);
          }}
        >
          {[
            ['left', '左边界', 0],
            ['top', '上边界', 0],
            ['right', '右边界', 100],
            ['bottom', '下边界', 100],
          ].map(([key, name, value]) => (
            <label key={key}>
              {name}（%）
              <input
                name={String(key)}
                type="number"
                min={0}
                max={100}
                step="0.1"
                defaultValue={value}
                required
              />
            </label>
          ))}
          <Button className="town-button" disabled={disabled}>
            识别所选区域
          </Button>
        </form>
      </details>
      {result && (
        <div className="candidate-panel">
          <h4>确认识别结果</h4>
          <p className="muted">数量和品质不会根据图片自动填写，也不会自动计入库存。</p>
          <div className="chip-row">
            {result.match.candidates.map((candidate) => (
              <button
                key={candidate.entity_id}
                className={`chip ${selected === candidate.entity_id ? 'selected' : ''}`}
                onClick={() => setSelected(candidate.entity_id)}
              >
                {candidate.name}
              </button>
            ))}
          </div>
          <form
            className="search-field"
            onSubmit={(event) => {
              event.preventDefault();
              void run(async () => {
                const data = await api<{ entities: SearchEntity[] }>(
                  `/search?${queryString({ q: search, task_id: task.task_id })}`,
                );
                setMatches(data.entities);
                if (!data.entities.length) notify('没有匹配物品，请尝试其他名称。');
              });
            }}
          >
            <Search size={18} />
            <input
              aria-label="搜索正确物品"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="识别不对？搜索正确物品…"
            />
            <button disabled={pending}>搜索</button>
          </form>
          <div className="chip-row">
            {matches.map((entity) => (
              <button
                key={entity.entity_id}
                className={`chip ${selected === entity.entity_id ? 'selected' : ''}`}
                onClick={() => setSelected(entity.entity_id)}
              >
                {entity.name}
              </button>
            ))}
          </div>
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              void run(async () => {
                if (!selected) throw new Error('请先从候选或搜索结果中选择一个物品。');
                await api('/confirm', {
                  task_id: task.task_id,
                  revision: task.revision,
                  region_id: result.region.region_id,
                  entity_id: selected,
                  quantity: form.get('quantity') === '' ? null : Number(form.get('quantity')),
                  quality: form.get('quality') || null,
                });
                await refresh(task.task_id);
                notify('已确认物品，可以继续向助手提问。');
                setResult(null);
              });
            }}
          >
            <label>
              数量
              <input name="quantity" type="number" min={0} placeholder="未知可留空…" />
            </label>
            <label>
              品质
              <select name="quality">
                <option value="">未确定</option>
                <option value="normal">普通</option>
                <option value="silver">银星</option>
                <option value="gold">金星</option>
                <option value="iridium">铱星</option>
              </select>
            </label>
            <Button className="town-button" disabled={disabled}>
              确认所选物品
            </Button>
          </form>
        </div>
      )}
      {task.selected_regions.length > 0 && (
        <JsonDetails
          title={`已保存 ${task.selected_regions.length} 个区域及确认记录`}
          value={{ regions: task.selected_regions, confirmed: task.inputs.confirmed_entities }}
        />
      )}
    </section>
  );
}
