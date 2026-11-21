import dagre from '@dagrejs/dagre';
import { MarkerType, type Edge, type Node } from '@xyflow/react';
import type { Entity, GraphData } from './types';
import { relationLabel } from './format';

export type EntityNode = Node<{ entity: Entity; selected: boolean }, 'entity'>;

export function relationColor(predicate: string) {
  if (/PROCESS|PRODUCT|EQUIPMENT/i.test(predicate)) return '#b17c21';
  if (/BUNDLE|REQUIRE|PART_OF/i.test(predicate)) return '#5485a8';
  return '#698a42';
}

/** Keep backend IDs and edge direction intact; layout changes coordinates only. */
export function layoutGraph(
  data: GraphData,
  filter: string,
): { nodes: EntityNode[]; edges: Edge[] } {
  const relations = data.edges.filter((edge) => !filter || edge.predicate === filter);
  const included = new Set(relations.flatMap((edge) => [edge.subject, edge.object]));
  const entities = data.nodes.filter((entity) => !filter || included.has(entity.id));
  const ids = new Set(entities.map((entity) => entity.id));
  const graph = new dagre.graphlib.Graph({ multigraph: true }).setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: 'LR', nodesep: 85, ranksep: 160, marginx: 45, marginy: 45 });
  entities.forEach((entity) => graph.setNode(entity.id, { width: 180, height: 76 }));
  const visible = relations.filter((edge) => ids.has(edge.subject) && ids.has(edge.object));
  visible.forEach((edge) => graph.setEdge(edge.subject, edge.object, {}, edge.id));
  dagre.layout(graph);
  return {
    nodes: entities.map((entity) => ({
      id: entity.id,
      type: 'entity',
      data: { entity, selected: false },
      position: { x: graph.node(entity.id).x - 90, y: graph.node(entity.id).y - 38 },
    })),
    edges: visible.map((edge) => ({
      id: edge.id,
      source: edge.subject,
      target: edge.object,
      label: relationLabel(edge.predicate),
      type: 'default',
      style: { stroke: relationColor(edge.predicate), strokeWidth: 2 },
      markerEnd: { type: MarkerType.ArrowClosed, color: relationColor(edge.predicate) },
      labelStyle: { fill: '#593b26', fontSize: 13 },
      labelBgStyle: { fill: '#fff8e8', fillOpacity: 1 },
      labelBgPadding: [8, 5],
    })),
  };
}

/** UI demonstration only; never submitted to the knowledge or agent APIs. */
export const exampleGraph: GraphData = {
  snapshot_id: 'design-example',
  truncated: false,
  nodes: [
    { id: 'demo-seed', name: '土豆种子', type: 'Seed' },
    { id: 'demo-potato', name: '土豆', type: 'Crop' },
    { id: 'demo-spring', name: '春季', type: 'Season' },
    { id: 'demo-pickles', name: '腌菜', type: 'Product' },
    { id: 'demo-juice', name: '蔬菜汁', type: 'Product' },
    { id: 'demo-bundle', name: '春季作物收集包', type: 'Bundle' },
  ],
  edges: [
    { id: 'demo-1', subject: 'demo-seed', predicate: 'GROWS_INTO', object: 'demo-potato' },
    { id: 'demo-2', subject: 'demo-potato', predicate: 'GROWS_IN', object: 'demo-spring' },
    { id: 'demo-3', subject: 'demo-potato', predicate: 'PROCESSED_INTO', object: 'demo-pickles' },
    { id: 'demo-4', subject: 'demo-potato', predicate: 'PROCESSED_INTO', object: 'demo-juice' },
    { id: 'demo-5', subject: 'demo-potato', predicate: 'REQUIRED_FOR', object: 'demo-bundle' },
  ],
};
