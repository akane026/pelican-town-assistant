import { useState } from 'react';
import { setApiKey, useHasApiKey } from '@/lib/credentials';
import { errorMessage } from '@/lib/api';
import { Button } from './ui/button';

export function ConnectionSettings({ onSaved }: { onSaved: () => void }) {
  const configured = useHasApiKey();
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');
  return (
    <section aria-labelledby="connection-heading" className="connection-settings">
      <h3 id="connection-heading">连接与隐私</h3>
      <p className="muted" role="status">
        {configured
          ? '已在当前浏览器中保存密钥，可随时更换或清除。'
          : '首次使用，请填写你自己的 ChatECNU API 密钥。'}
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          try {
            setApiKey(draft);
            setDraft('');
            setError('');
            onSaved();
          } catch (reason) {
            setError(errorMessage(reason));
          }
        }}
      >
        <label htmlFor="model-api-key">ChatECNU API 密钥</label>
        <input
          id="model-api-key"
          type="password"
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            setError('');
          }}
          placeholder={configured ? '输入新密钥以更换' : '输入你的 API 密钥'}
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          maxLength={512}
          required
          aria-describedby="credential-privacy"
          aria-invalid={Boolean(error)}
        />
        {error && <p role="alert">{error}</p>}
        <div className="button-row">
          <Button className="town-button" disabled={!draft.trim()}>
            保存并返回
          </Button>
          {configured && (
            <Button
              type="button"
              className="town-button secondary"
              onClick={() => {
                try {
                  setApiKey('');
                  setDraft('');
                  setError('');
                } catch (reason) {
                  setError(errorMessage(reason));
                }
              }}
            >
              清除密钥
            </Button>
          )}
        </div>
      </form>
      <p className="muted" id="credential-privacy">
        密钥保存在当前浏览器的本地存储中，刷新或重新打开同一地址后仍可使用。点击「清除密钥」或清除网站数据后删除。提问时交给本机后端临时调用
        ChatECNU，不写入配置文件或对话记录。保存不会发起模型调用。
      </p>
    </section>
  );
}
