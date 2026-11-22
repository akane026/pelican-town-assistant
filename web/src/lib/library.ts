export interface LibrarySource {
  id: string;
  title: string;
  kind: 'file' | 'web';
  filename: string;
  url: string;
  revision: number;
  created_at: string;
  updated_at: string;
  status: 'pending_build';
  characters?: number;
}

export interface LibraryDetail extends LibrarySource {
  content: string;
  text_content: string;
}

export interface LibraryList {
  items: LibrarySource[];
  total: number;
  offset: number;
  limit: number;
}

export const SOURCE_FORMATS = '.txt,.md,.markdown,.html,.htm,.json,.csv';
export const MAX_SOURCE_BYTES = 2 * 1024 * 1024;

export async function encodeSource(file: File) {
  if (file.size > MAX_SOURCE_BYTES) throw new Error('每份资料不能超过 2 MB。');
  if (!SOURCE_FORMATS.split(',').some((extension) => file.name.toLowerCase().endsWith(extension))) {
    throw new Error('请选择 TXT、Markdown、HTML、JSON 或 CSV 文件。');
  }
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('无法读取文件，请重新选择。'));
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.readAsDataURL(file);
  });
}
