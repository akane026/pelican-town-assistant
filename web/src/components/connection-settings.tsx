import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { setApiKey, useApiKey } from '@/lib/credentials';
import { errorMessage } from '@/lib/api';
import { Button } from './ui/button';

export function ConnectionSettings({ onSaved }: { onSaved: () => void }) {
  const savedKey = useApiKey();
  const configured = Boolean(savedKey);
  // null follows the saved value; typing creates an unsaved draft.
  const [draft, setDraft] = useState<string | null>(null);
  const value = draft ?? savedKey;
  const [visible, setVisible] = useState(false);
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
            setApiKey(value);
            setDraft(null);
            setVisible(false);
            setError('');
            onSaved();
          } catch (reason) {
            setError(errorMessage(reason));
          }
        }}
      >
        <label htmlFor="model-api-key">ChatECNU API 密钥</label>
        <div className="credential-input">
          <input
            id="model-api-key"
            type={visible ? 'text' : 'password'}
            value={value}
            onChange={(event) => {
              setDraft(event.target.value);
              setError('');
            }}
            placeholder="输入你的 API 密钥"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={512}
            required
            aria-describedby="credential-privacy"
            aria-invalid={Boolean(error)}
          />
          <button
            type="button"
            className="icon-button credential-visibility"
            aria-label={visible ? '隐藏密钥' : '显示密钥'}
            aria-pressed={visible}
            onClick={() => setVisible(!visible)}
          >
            {visible ? <EyeOff size={19} /> : <Eye size={19} />}
          </button>
        </div>
        {error && <p role="alert">{error}</p>}
        <div className="button-row">
          <Button className="town-button" disabled={!value.trim()}>
            保存密钥并返回
          </Button>
          {configured && (
            <Button
              type="button"
              className="town-button secondary"
              onClick={() => {
                try {
                  setApiKey('');
                  setDraft(null);
                  setVisible(false);
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
        仅保存在当前浏览器，刷新后仍可使用；保存不会调用模型。
      </p>
      <details className="help-details">
        <summary>密钥如何保存和使用</summary>
        <p className="muted">
          密钥存储在当前网站的本地存储中，重新打开同一地址后仍可使用。点击「清除密钥」或清除网站数据可删除。
          提问时交给本机后端临时调用 ChatECNU，不写入配置文件或对话记录。
        </p>
      </details>
    </section>
  );
}
