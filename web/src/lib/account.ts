let accountId = '';
export function setAccountScope(id: string) {
  accountId = id;
}
export function accountStorageKey(base: string) {
  return accountId ? `${base}:${accountId}` : base;
}
