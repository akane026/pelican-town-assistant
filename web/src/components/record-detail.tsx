import { useQuery } from '@tanstack/react-query';
import { BookOpen, ExternalLink } from 'lucide-react';
import { api, imageUrl, queryString, safeSourceUrl } from '@/lib/api';
import { recordTitle, readable } from '@/lib/format';
import type { RecordDetail as RecordPayload } from '@/lib/types';
import { ErrorState, Loading } from './feedback';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';

export function JsonDetails({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="json-details">
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

export function Evidence({ data, taskId }: { data: RecordPayload; taskId?: string }) {
  return (
    <div className="evidence-content">
      <div className="tag">来源版本 {data.snapshot_id.slice(0, 10)}</div>
      <h3>{recordTitle(data.record)}</h3>
      {data.record.predicate ? (
        <p>
          {readable(data.record.predicate)} · {readable(data.record.object ?? data.record.value)}
        </p>
      ) : null}
      {data.assets.length > 0 && (
        <div className="asset-strip">
          {data.assets.map((asset) => (
            <figure key={asset.id}>
              <img src={imageUrl(asset.id, taskId)} alt="来源中的原始图像" loading="lazy" />
              <figcaption>
                {asset.width} × {asset.height}
              </figcaption>
            </figure>
          ))}
        </div>
      )}
      <h4>
        <BookOpen size={18} /> 原文依据
      </h4>
      {data.evidence.length ? (
        data.evidence.map((source) => (
          <blockquote key={source.id}>
            <p>{source.quote}</p>
            <small>
              {source.page_id} · {source.locator}
            </small>
            {safeSourceUrl(source.url) && (
              <a
                className="text-link"
                href={safeSourceUrl(source.url)}
                target="_blank"
                rel="noreferrer"
              >
                查看 Wiki 原文 <ExternalLink size={14} />
              </a>
            )}
          </blockquote>
        ))
      ) : (
        <p className="muted">这条记录暂未提供直接原文。可查看它的关联记录。</p>
      )}
      <JsonDetails title="记录与关系条件" value={data.record} />
      <JsonDetails
        title="图文对齐与区域依据"
        value={{
          alignments: data.alignments,
          regions: data.regions,
          observations: data.observations,
        }}
      />
    </div>
  );
}

export function RecordDrawer({
  id,
  taskId,
  onClose,
}: {
  id: string | null;
  taskId?: string;
  onClose: () => void;
}) {
  const query = useQuery({
    queryKey: ['record', id, taskId],
    enabled: Boolean(id),
    queryFn: ({ signal }) =>
      api<RecordPayload>(`/record?${queryString({ id: id!, task_id: taskId })}`, undefined, signal),
  });
  return (
    <Dialog open={Boolean(id)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="town-dialog drawer">
        <DialogHeader>
          <DialogTitle>查看知识依据</DialogTitle>
          <DialogDescription>核对原文、图片与物品之间的关系。</DialogDescription>
        </DialogHeader>
        {query.isLoading && <Loading />}
        {query.error && <ErrorState error={query.error} retry={() => void query.refetch()} />}
        {query.data && <Evidence data={query.data} taskId={taskId} />}
      </DialogContent>
    </Dialog>
  );
}
