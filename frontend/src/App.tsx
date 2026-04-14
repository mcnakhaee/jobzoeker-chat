import { useState, useRef, useEffect } from 'react';
import type { ChatMessage, Task, PlanPhase } from './types';
import { generatePlan, runPlan, clearContext } from './api/client';
import ProfilePanel from './components/ProfilePanel';
import PlanMessage from './components/PlanMessage';
import ContextModal from './components/ContextModal';
import './App.css';

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

const EXAMPLES = [
  'Find AI engineering jobs in Amsterdam and save them to Notion',
  'Search for machine learning engineer roles and write cover letters for the top 3',
];

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [planning, setPlanning] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [contextOpen, setContextOpen] = useState(false);
  const model = 'gpt-4.1-mini';

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const cancelRunRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, planning]);

  function resizeTextarea() {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || planning) return;

    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setMessages(prev => [...prev, { id: uid(), type: 'user', content: text }]);
    setPlanning(true);

    try {
      const plan = await generatePlan(text, model);

      // Simple conversational message (greeting, question, no tool needed) —
      // auto-run immediately and show the response as a plain assistant bubble.
      if (plan.tasks.length === 1 && plan.tasks[0].tool === 'none') {
        let summary = '';
        await new Promise<void>(resolve => {
          const cancel = runPlan(plan, model, event => {
            if (event.type === 'task_done') summary = event.summary ?? '';
            if (event.type === 'complete' || event.type === 'error') resolve();
          });
          cancelRunRef.current = cancel;
        });
        cancelRunRef.current = null;
        setMessages(prev => [
          ...prev,
          { id: uid(), type: 'assistant' as const, content: summary || '…' },
        ]);
        return;
      }

      setMessages(prev => [
        ...prev,
        {
          id: uid(),
          type: 'plan',
          plan,
          tasks: plan.tasks.map(t => ({ ...t, status: 'pending' as const, logs: [] })),
          phase: 'confirming' as PlanPhase,
        },
      ]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to generate plan.';
      setMessages(prev => [
        ...prev,
        {
          id: uid(),
          type: 'plan',
          plan: { goal: text, tasks: [] },
          tasks: [],
          phase: 'done' as PlanPhase,
          error: msg,
        },
      ]);
    } finally {
      setPlanning(false);
    }
  }

  function handleConfirm(msgId: string) {
    // Read the plan from current messages state directly —
    // extracting it inside a setMessages updater doesn't work because
    // React batches updates and calls the updater asynchronously.
    const planMsg = messages.find(m => m.id === msgId && m.type === 'plan');
    if (!planMsg || planMsg.type !== 'plan') return;
    const planToRun = structuredClone(planMsg.plan);

    setMessages(prev =>
      prev.map(m =>
        m.id === msgId && m.type === 'plan' ? { ...m, phase: 'running' as PlanPhase } : m,
      ),
    );

    const taskSummaries: string[] = [];

    const cancel = runPlan(planToRun, model, event => {
      if (event.type === 'task_start' && event.task_id != null) {
        setMessages(prev =>
          prev.map(m => {
            if (m.id !== msgId || m.type !== 'plan') return m;
            return {
              ...m,
              tasks: m.tasks.map((t: Task) =>
                t.id === event.task_id ? { ...t, status: 'running' as const, logs: [] } : t,
              ),
            };
          }),
        );
      } else if (
        (event.type === 'agent_log' || event.type === 'tool_call' || event.type === 'tool_result') &&
        event.task_id != null
      ) {
        setMessages(prev =>
          prev.map(m => {
            if (m.id !== msgId || m.type !== 'plan') return m;
            return {
              ...m,
              tasks: m.tasks.map((t: Task) =>
                t.id === event.task_id
                  ? {
                      ...t,
                      logs: [
                        ...t.logs,
                        { type: event.type as 'agent_log' | 'tool_call' | 'tool_result', message: event.message ?? '', tool: event.tool },
                      ],
                    }
                  : t,
              ),
            };
          }),
        );
      } else if (event.type === 'task_done' && event.task_id != null) {
        if (event.summary) taskSummaries.push(event.summary);
        setMessages(prev =>
          prev.map(m => {
            if (m.id !== msgId || m.type !== 'plan') return m;
            return {
              ...m,
              tasks: m.tasks.map((t: Task) =>
                t.id === event.task_id
                  ? { ...t, status: 'done' as const, summary: event.summary }
                  : t,
              ),
            };
          }),
        );
      } else if (event.type === 'complete') {
        const combined = taskSummaries.join('\n\n').trim();
        setMessages(prev => {
          const updated = prev.map(m =>
            m.id === msgId && m.type === 'plan' ? { ...m, phase: 'done' as PlanPhase } : m,
          );
          if (combined) {
            return [...updated, { id: uid(), type: 'assistant' as const, content: combined }];
          }
          return updated;
        });
        cancelRunRef.current = null;
      } else if (event.type === 'error') {
        setMessages(prev =>
          prev.map(m =>
            m.id === msgId && m.type === 'plan'
              ? { ...m, phase: 'done' as PlanPhase, error: event.message }
              : m,
          ),
        );
        cancelRunRef.current = null;
      }
    });

    cancelRunRef.current = cancel;
  }

  function handleCancel(msgId: string) {
    cancelRunRef.current?.();
    cancelRunRef.current = null;
    setMessages(prev => prev.filter(m => m.id !== msgId));
  }

  async function handleNewChat() {
    cancelRunRef.current?.();
    cancelRunRef.current = null;
    setMessages([]);
    setInput('');
    await clearContext().catch(() => {});
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const isEmpty = messages.length === 0 && !planning;

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className={`sidebar${sidebarOpen ? '' : ' sidebar-collapsed'}`}>
        <div className="sidebar-top">
          <div className="brand">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" className="brand-icon">
              <circle cx="8" cy="8" r="5.5" stroke="var(--accent)" strokeWidth="2" />
              <path d="M12.5 12.5L17 17" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <span className="brand-name">Jobzoeker</span>
          </div>
          <button
            className="sidebar-toggle"
            onClick={() => setSidebarOpen(o => !o)}
            aria-label="Toggle sidebar"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {sidebarOpen && (
          <div className="sidebar-body">
            <ProfilePanel />
          </div>
        )}

        {sidebarOpen && (
          <div className="sidebar-footer">
            <button className="new-chat-btn" onClick={handleNewChat}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 2v10M2 7h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              New conversation
            </button>
            <button className="ctx-inspect-btn" onClick={() => setContextOpen(true)}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <rect x="1.5" y="2.5" width="11" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
                <path d="M4 5.5h6M4 8h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              Inspect context
            </button>
          </div>
        )}
      </aside>

      {/* Main */}
      <main className="chat-main">
        <div className="messages-area">
          {isEmpty && (
            <div className="empty-state">
              <div className="empty-icon">
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <circle cx="17" cy="17" r="11" stroke="var(--accent)" strokeWidth="2.5" />
                  <path d="M26 26L36 36" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" />
                </svg>
              </div>
              <h1 className="empty-title">What are you looking for?</h1>
              <p className="empty-sub">
                Describe your job search goal. I'll build a plan and run it for you.
              </p>
              <div className="examples">
                {EXAMPLES.map(ex => (
                  <button
                    key={ex}
                    className="example-btn"
                    onClick={() => {
                      setInput(ex);
                      textareaRef.current?.focus();
                    }}
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} className={`msg-row ${msg.type === 'user' ? 'msg-user' : 'msg-agent'}`}>
              {msg.type === 'user' ? (
                <div className="user-bubble">{msg.content}</div>
              ) : msg.type === 'assistant' ? (
                <div className="assistant-bubble">{msg.content}</div>
              ) : (
                <PlanMessage
                  plan={msg.plan}
                  tasks={msg.tasks}
                  phase={msg.phase}
                  onConfirm={() => handleConfirm(msg.id)}
                  onCancel={() => handleCancel(msg.id)}
                  error={msg.error}
                />
              )}
            </div>
          ))}

          {planning && (
            <div className="msg-row msg-agent">
              <div className="thinking">
                <span className="dot" />
                <span className="dot" />
                <span className="dot" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="input-area">
          <div className="input-box">
            <textarea
              ref={textareaRef}
              className="chat-input"
              placeholder="Describe your job search goal…"
              value={input}
              rows={1}
              disabled={planning}
              onChange={e => {
                setInput(e.target.value);
                resizeTextarea();
              }}
              onKeyDown={handleKeyDown}
            />
            <button
              className="send-btn"
              onClick={handleSend}
              disabled={!input.trim() || planning}
              aria-label="Send"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path
                  d="M2 8h12M9 3l5 5-5 5"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
          <p className="input-hint">Enter to send · Shift+Enter for new line</p>
        </div>
      </main>

      {contextOpen && <ContextModal onClose={() => setContextOpen(false)} />}
    </div>
  );
}
