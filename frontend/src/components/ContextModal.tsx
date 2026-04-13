import { useState, useEffect, useCallback } from 'react';
import { getContext } from '../api/client';

interface Message {
  role: string;
  content: string;
}

interface Props {
  onClose: () => void;
}

export default function ContextModal({ onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setMessages(await getContext());
    } catch {
      setError('Could not load context.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-row">
            <h2 className="modal-title">Context window</h2>
            <span className="modal-count">
              {loading ? '…' : `${messages.length} message${messages.length !== 1 ? 's' : ''}`}
            </span>
          </div>
          <p className="modal-subtitle">
            Compressed rolling history sent to the LLM on every call.
          </p>
        </div>

        <div className="modal-body">
          {loading && <p className="modal-empty">Loading…</p>}
          {error  && <p className="modal-empty modal-error">{error}</p>}
          {!loading && !error && messages.length === 0 && (
            <p className="modal-empty">Context is empty.</p>
          )}
          {!loading && !error && messages.map((msg, i) => (
            <div key={i} className={`ctx-message ctx-${msg.role}`}>
              <span className="ctx-role">{msg.role}</span>
              <pre className="ctx-content">{msg.content}</pre>
            </div>
          ))}
        </div>

        <div className="modal-footer">
          <button className="btn-ghost" onClick={load} disabled={loading}>
            Refresh
          </button>
          <button className="btn-ghost modal-close" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
