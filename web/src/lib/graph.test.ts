import { describe, expect, it } from 'vitest';
import { exampleGraph, layoutGraph } from './graph';

describe('graph rendering contracts', () => {
  it('preserves real record IDs and relationship direction through layout', () => {
    const graph = layoutGraph(exampleGraph, 'PROCESSED_INTO');
    expect(graph.edges.map((edge) => [edge.id, edge.source, edge.target])).toEqual([
      ['demo-3', 'demo-potato', 'demo-pickles'],
      ['demo-4', 'demo-potato', 'demo-juice'],
    ]);
    expect(graph.nodes.map((node) => node.id).sort()).toEqual([
      'demo-juice',
      'demo-pickles',
      'demo-potato',
    ]);
    expect(
      graph.nodes.every(
        (node) => Number.isFinite(node.position.x) && Number.isFinite(node.position.y),
      ),
    ).toBe(true);
  });
  it('handles isolated nodes and relations whose targets are missing', () => {
    const graph = layoutGraph({ ...exampleGraph, nodes: [exampleGraph.nodes[0]] }, '');
    expect(graph.nodes).toHaveLength(1);
    expect(graph.edges).toHaveLength(0);
  });
});
