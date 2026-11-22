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
      <h3 id="connection-heading">模型连接</h3>
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
    </section>
  );
}
