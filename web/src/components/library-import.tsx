import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { FileUp, Globe } from 'lucide-react';
import { api, errorMessage } from '@/lib/api';
import { encodeSource, SOURCE_FORMATS, type LibraryDetail } from '@/lib/library';
import { useAction } from './feedback';
import { Button } from './ui/button';
import { PixelScroll } from './pixel-icons';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';

export function LibraryImport({ onClose }: { onClose: () => void }) {
  const [kind, setKind] = useState<'file' | 'web'>('file');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState('');
  const { run, pending } = useAction();
  const client = useQueryClient();
  const navigate = useNavigate();
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !pending) onClose();
      }}
    >
      <DialogContent className="town-dialog library-dialog">
        <DialogHeader>
          <DialogTitle>添加知识资料</DialogTitle>
          <DialogDescription>先收藏原文，再整理成可供农场助手使用的知识。</DialogDescription>
        </DialogHeader>
        <div className="button-row" aria-label="导入方式">
          <button
            className="chip"
            aria-pressed={kind === 'file'}
            disabled={pending}
            onClick={() => setKind('file')}
          >
            <FileUp size={17} /> 上传文件
          </button>
          <button
            className="chip"
            aria-pressed={kind === 'web'}
            disabled={pending}
            onClick={() => setKind('web')}
          >
            <Globe size={17} /> 导入网页
          </button>
        </div>
        <form
          className="library-form"
          onSubmit={(event) => {
            event.preventDefault();
            const values = new FormData(event.currentTarget);
            void run(async () => {
              setError('');
              try {
                if (kind === 'file' && !file) throw new Error('请先选择文件。');
                const payload =
                  kind === 'file'
                    ? { kind, filename: file!.name, data: await encodeSource(file!) }
                    : { kind, url: String(values.get('url')).trim() };
                const source = await api<LibraryDetail>('/library/create', {
                  ...payload,
                  title: String(values.get('title') || '').trim(),
                });
                await client.invalidateQueries({ queryKey: ['library'] });
                onClose();
                navigate(`/library/${source.id}`);
              } catch (reason) {
                setError(errorMessage(reason));
              }
            });
          }}
        >
          {error && (
            <p role="alert" className="library-notice">
              {error}
            </p>
          )}
          <label>
            资料名称（选填）
            <input
              name="title"
              maxLength={160}
              placeholder="例如：春季种植笔记"
              disabled={pending}
            />
          </label>
          {kind === 'file' ? (
            <label className="library-upload">
              <PixelScroll size={40} />
              选择知识文件
              <input
                type="file"
                accept={SOURCE_FORMATS}
                disabled={pending}
                required
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
              <small>UTF-8 编码 · TXT / Markdown / HTML / JSON / CSV · 单份最多 2 MB</small>
            </label>
          ) : (
            <label>
              网页地址
              <input
                name="url"
                type="url"
                placeholder="https://stardewvalleywiki.com/Potato"
                required
                disabled={pending}
              />
              <small>公开 HTTPS 网页，保存当前正文；不支持登录页面、内网或需脚本加载的正文。</small>
            </label>
          )}
          <p className="library-notice">
            上传后状态为「待构图」，暂不进入问答。原文预览不会执行网页脚本，也不会调用模型。
          </p>
          <div className="button-row">
            <Button className="town-button" disabled={pending}>
              {pending ? '正在导入…' : '保存资料'}
            </Button>
            <Button
              type="button"
              className="town-button secondary"
              disabled={pending}
              onClick={onClose}
            >
              取消
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
