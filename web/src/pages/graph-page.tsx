import {
  PixelMap,
  PixelCrop,
  PixelSeeds,
  PixelFlower,
  PixelJar,
  PixelBundle,
  PixelBarrel,
  PixelBook,
} from '@/components/pixel-icons';
import { Sprout as PixelSprout } from '@/components/pixel-art';
import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  useNodesState,
  useReactFlow,
  type FitViewOptions,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { BookOpen, Expand, List, Network, Search, Sprout, X } from 'lucide-react';
import { api, queryString } from '@/lib/api';
import { layoutGraph, exampleGraph, type EntityNode } from '@/lib/graph';
import { relationLabel, typeLabels } from '@/lib/format';
import type { GraphData, SearchEntity } from '@/lib/types';
import { useBootstrap } from '@/hooks/use-workbench';
import { EmptyState, ErrorState, Loading } from '@/components/feedback';
import { RecordDrawer } from '@/components/record-detail';
import { Button } from '@/components/ui/button';

const entityIcons = {
  Crop: PixelCrop,
  Seed: PixelSeeds,
  Season: PixelFlower,
  Product: PixelJar,
  Bundle: PixelBundle,
  Equipment: PixelBarrel,
  CropStage: PixelSprout,
};
function EntityIcon({ type }: { type: string }) {
  const Icon = entityIcons[type as keyof typeof entityIcons] || PixelBook;
  return <Icon />;
}
function ItemNode({ data }: NodeProps<EntityNode>) {
  return (
    <div className={`item-node ${data.selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Left} />
      <span className="entity-icon" aria-hidden="true">
        <EntityIcon type={data.entity.type} />
      </span>
      <div>
        <strong>{data.entity.name}</strong>
        <small>{typeLabels[data.entity.type] || data.entity.type}</small>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
const nodeTypes = { entity: ItemNode };
const emptyGraph: GraphData = { nodes: [], edges: [], snapshot_id: '', truncated: false };
// Keep labels readable on small canvases; users can pan or choose “适应画布”.
const initialFitOptions: FitViewOptions = { padding: '6%', minZoom: 0.75, maxZoom: 1 };

function FitOnResize({ container }: { container: RefObject<HTMLDivElement | null> }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    if (!container.current) return;
    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => void fitView(initialFitOptions));
    });
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [container, fitView]);
  return null;
}

export default function GraphPage() {
  const canvas = useRef<HTMLDivElement>(null);
  const { data: boot } = useBootstrap();
  const [params, setParams] = useSearchParams();
  const example = params.get('example') === '1';
  const center = params.get('id') || undefined;
  const taskId = params.get('task') || undefined;
  const filter = params.get('relation') || '';
  const listView = params.get('view') === 'list';
  const [search, setSearch] = useState('');
  const [term, setTerm] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [record, setRecord] = useState<string | null>(null);
  const graph = useQuery({
    queryKey: ['graph', center, taskId],
    enabled: Boolean(boot?.snapshot && !example),
    queryFn: ({ signal }) =>
      api<GraphData>(`/graph?${queryString({ id: center, task_id: taskId })}`, undefined, signal),
  });
  const searchQuery = useQuery({
    queryKey: ['entity-search', term, taskId],
    enabled: Boolean(term && boot?.snapshot && !example),
    queryFn: ({ signal }) =>
      api<{ entities: SearchEntity[] }>(
        `/search?${queryString({ q: term, task_id: taskId })}`,
        undefined,
        signal,
      ),
  });
  const data = example ? exampleGraph : graph.data || emptyGraph;
  const layout = useMemo(() => layoutGraph(data, filter), [data, filter]);
  const [nodes, setNodes, onNodesChange] = useNodesState<EntityNode>(layout.nodes);
  useEffect(() => {
    setNodes(layout.nodes);
  }, [layout.nodes, setNodes]);
  const displayNodes = useMemo(
    () =>
      nodes.map((node) => ({ ...node, data: { ...node.data, selected: node.id === selected } })),
    [nodes, selected],
  );
  const entity = data.nodes.find((node) => node.id === selected);
  const related = data.edges.filter(
    (edge) => edge.subject === selected || edge.object === selected,
  );
  const names = new Map(data.nodes.map((node) => [node.id, node.name]));
  const searchResults = example
    ? exampleGraph.nodes
        .filter((node) => node.name.includes(term))
        .map((node) => ({ entity_id: node.id, name: node.name }))
    : searchQuery.data?.entities || [];
  function update(values: Record<string, string | null>) {
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      Object.entries(values).forEach(([key, value]) =>
        value ? next.set(key, value) : next.delete(key),
      );
      return next;
    });
  }
  return (
    <div className="graph-page page">
      <div className="page-heading">
        <div>
          <h1>
            <PixelMap />
            物品图谱
          </h1>
          <p>探索物品的生长、加工与献祭关系</p>
        </div>
        <div className="segmented">
          <button
            className={!listView ? 'active' : ''}
            aria-pressed={!listView}
            onClick={() => update({ view: null })}
          >
            <Network size={17} />
            图谱
          </button>
          <button
            className={listView ? 'active' : ''}
            aria-pressed={listView}
            onClick={() => update({ view: 'list' })}
          >
            <List size={17} />
            列表
          </button>
        </div>
      </div>
      <div className="graph-toolbar">
        <form
          className="search-field"
          onSubmit={(event) => {
            event.preventDefault();
            setTerm(search.trim());
          }}
        >
          <Search size={20} />
          <input
            aria-label="搜索物品"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜索物品、作物或收集包…"
          />
          <button type="submit">搜索</button>
        </form>
        <label className="filter-select">
          <span className="sr-only">关系筛选</span>
          <select value={filter} onChange={(event) => update({ relation: event.target.value })}>
            <option value="">全部关系</option>
            {[...new Set(data.edges.map((edge) => edge.predicate))].map((predicate) => (
              <option key={predicate} value={predicate}>
                {relationLabel(predicate)}
              </option>
            ))}
          </select>
        </label>
        {center && (
          <button
            className="chip"
            onClick={() => {
              update({ id: null });
              setSelected(null);
            }}
          >
            返回全图
          </button>
        )}
      </div>
      {term && (
        <div className="search-results">
          <strong>搜索结果</strong>
          {searchQuery.isFetching ? (
            <Loading text="正在查找…" />
          ) : searchResults.length ? (
            searchResults.map((result) => (
              <button
                className="chip"
                key={result.entity_id}
                onClick={() => {
                  setSelected(result.entity_id);
                  if (!example) update({ id: result.entity_id });
                  setTerm('');
                }}
              >
                {result.name}
              </button>
            ))
          ) : (
            <span className="muted">未找到匹配物品。</span>
          )}
          <button className="icon-button" aria-label="关闭搜索结果" onClick={() => setTerm('')}>
            <X size={17} />
          </button>
        </div>
      )}
      {searchQuery.error && <ErrorState error={searchQuery.error} />}
      <div className="graph-context">
        {example && (
          <div className="example-note">
            <span>交互示例 · 非知识库数据，不用于回答</span>
            <button
              className="text-link"
              onClick={() => {
                update({ example: null, id: null, relation: null });
                setSelected(null);
              }}
            >
              退出示例
            </button>
          </div>
        )}
        <div className="graph-legend">
          <span>
            <i className="green" />
            生长
          </span>
          <span>
            <i className="gold" />
            加工
          </span>
          <span>
            <i className="blue" />
            献祭
          </span>
          <small>连线箭头表示关系方向</small>
        </div>
      </div>
      {!example && !boot?.snapshot ? (
        <div className="graph-empty">
          <EmptyState
            icon={<PixelMap size={64} />}
            title="物品之间的故事，等待展开"
            action={
              <div className="button-row">
                <Button className="town-button" onClick={() => update({ example: '1' })}>
                  查看交互示例
                </Button>
                <Link className="chip" to="/knowledge">
                  准备知识库
                </Link>
              </div>
            }
          >
            导入知识库后，就能在这里探索真实物品关系，点击连线查看原文依据。
          </EmptyState>
        </div>
      ) : graph.isLoading && !example ? (
        <Loading />
      ) : graph.error && !example ? (
        <ErrorState error={graph.error} retry={() => void graph.refetch()} />
      ) : (
        <div className={`graph-workspace ${entity ? 'with-detail' : ''}`}>
          {listView ? (
            <div className="relation-list">
              {layout.edges.length ? (
                layout.edges.map((edge) => (
                  <button
                    className="relation-row"
                    key={edge.id}
                    onClick={() => (example ? setSelected(edge.source) : setRecord(edge.id))}
                  >
                    <strong>{names.get(edge.source)}</strong>
                    <span>{String(edge.label)}</span>
                    <strong>{names.get(edge.target)}</strong>
                    <BookOpen size={17} />
                  </button>
                ))
              ) : (
                <EmptyState title="没有匹配的关系">尝试更换物品或清除关系筛选。</EmptyState>
              )}
            </div>
          ) : (
            <div className="flow-canvas" ref={canvas}>
              <ReactFlow
                key={`${data.snapshot_id}:${center}:${filter}`}
                forceColorMode="light"
                nodes={displayNodes}
                edges={layout.edges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                fitView
                fitViewOptions={initialFitOptions}
                minZoom={0.25}
                maxZoom={2}
                nodesConnectable={false}
                deleteKeyCode={null}
                onNodeClick={(_, node) => setSelected(node.id)}
                onNodeDoubleClick={(_, node) => !example && update({ id: node.id })}
                onEdgeClick={(_, edge) => (example ? setSelected(edge.source) : setRecord(edge.id))}
                ariaLabelConfig={{
                  'controls.zoomIn.ariaLabel': '放大图谱',
                  'controls.zoomOut.ariaLabel': '缩小图谱',
                  'controls.fitView.ariaLabel': '适应画布',
                  'node.a11yDescription.default':
                    '按 Enter 选择物品，方向键移动节点，Escape 取消。',
                }}
              >
                <FitOnResize container={canvas} />
                <Background gap={24} size={1} color="#dfd4bd" />
                <Controls showInteractive={false} />
              </ReactFlow>
              <div className="canvas-hint">单击选择物品 · 双击展开关联 · 拖动与缩放</div>
            </div>
          )}
          {entity && (
            <aside className="graph-detail paper-panel">
              <button
                className="icon-button close-detail"
                aria-label="关闭物品详情"
                onClick={() => setSelected(null)}
              >
                <X size={19} />
              </button>
              <div className="entity-heading">
                <span className="entity-icon">
                  <EntityIcon type={entity.type} />
                </span>
                <div>
                  <h2>{entity.name}</h2>
                  <p>{typeLabels[entity.type] || entity.type}</p>
                </div>
              </div>
              <hr />
              <h3>
                <Sprout size={19} />
                关联用途
              </h3>
              <ul className="uses-list">
                {related.map((edge) => (
                  <li key={edge.id}>
                    <button
                      onClick={() =>
                        example
                          ? setSelected(edge.subject === selected ? edge.object : edge.subject)
                          : setRecord(edge.id)
                      }
                    >
                      {edge.subject === selected ? relationLabel(edge.predicate) : '关联来源'}：
                      {names.get(edge.subject === selected ? edge.object : edge.subject)}
                    </button>
                  </li>
                ))}
              </ul>
              <hr />
              {example ? (
                <p className="muted">这是图谱交互示例。真实数据会提供关系条件与 Wiki 来源。</p>
              ) : (
                <>
                  <button className="text-link" onClick={() => setRecord(entity.id)}>
                    <BookOpen size={18} />
                    查看原文与图片依据
                  </button>
                  <Button
                    className="town-button secondary"
                    onClick={() => update({ id: entity.id })}
                  >
                    <Expand size={17} />
                    展开关联物品
                  </Button>
                  <Link
                    className="town-button"
                    to={`/chat?q=${encodeURIComponent(`请介绍${entity.name}的用途与关联物品。`)}`}
                  >
                    围绕{entity.name}提问
                  </Link>
                </>
              )}
            </aside>
          )}
        </div>
      )}
      {!example && graph.data?.truncated && (
        <p className="muted">当前最多显示 45 条关系，请搜索一个物品缩小范围。</p>
      )}
      <RecordDrawer id={record} taskId={taskId} onClose={() => setRecord(null)} />
    </div>
  );
}
