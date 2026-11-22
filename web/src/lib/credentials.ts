import { useSyncExternalStore } from 'react';

export const CREDENTIAL_KEY = 'pelican:chatecnu-key:v1';
const listeners = new Set<() => void>();

function readApiKey() {
  try {
    const key = localStorage.getItem(CREDENTIAL_KEY) || '';
    return /^[\x21-\x7e]{1,512}$/.test(key) ? key : '';
  } catch {
    return '';
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (
      event.storageArea === localStorage &&
      (event.key === CREDENTIAL_KEY || event.key === null)
    ) {
      listener();
    }
  };
  window.addEventListener('storage', onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('storage', onStorage);
  };
}

export function hasApiKey() {
  return Boolean(readApiKey());
}

export function useApiKey() {
  return useSyncExternalStore(subscribe, readApiKey);
}

export function setApiKey(value: string) {
  const key = value.trim();
  if (key && !/^[\x21-\x7e]{1,512}$/.test(key)) {
    throw new Error('密钥格式不正确，请检查是否包含空格或多余字符。');
  }
  try {
    if (key) localStorage.setItem(CREDENTIAL_KEY, key);
    else localStorage.removeItem(CREDENTIAL_KEY);
  } catch {
    throw new Error('浏览器无法保存或清除密钥，请检查网站存储权限或可用空间。');
  }
  listeners.forEach((listener) => listener());
}

export function requireApiKey() {
  const apiKey = readApiKey();
  if (!apiKey) throw new Error('请先在「设置 → 连接与隐私」中填写你的 ChatECNU API 密钥。');
  return apiKey;
}
