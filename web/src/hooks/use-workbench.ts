import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, bootstrap, queryString } from '@/lib/api';
import type { TaskDetail } from '@/lib/types';

export function useBootstrap() {
  return useQuery({
    queryKey: ['bootstrap'],
    queryFn: ({ signal }) => bootstrap(signal),
    staleTime: 30_000,
  });
}

export function useTask(taskId?: string) {
  return useQuery({
    queryKey: ['task', taskId],
    enabled: Boolean(taskId),
    queryFn: ({ signal }) =>
      api<TaskDetail>(`/task?${queryString({ id: taskId, task_id: taskId })}`, undefined, signal),
    refetchInterval: (query) => (query.state.data?.running ? 1200 : false),
  });
}

export function useRefreshTask() {
  const client = useQueryClient();
  return async (taskId: string) => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['task', taskId] }),
      client.invalidateQueries({ queryKey: ['bootstrap'] }),
    ]);
  };
}
