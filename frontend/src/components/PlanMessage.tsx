import type { Task, Plan, PlanPhase, TaskLog } from '../types';

const TOOL_LABELS: Record<string, string> = {
  job_search: 'Search',
  notion: 'Notion',
  cover_letter: 'Cover letter',
  company_info: 'Company info',
  none: 'Respond',
};

function StatusIcon({ status }: { status: Task['status'] }) {
  if (status === 'pending') {
    return (
      <svg className="task-icon pending" width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    );
  }
  if (status === 'running') {
    return (
      <span className="task-spinner" aria-hidden="true" />
    );
  }
  if (status === 'done') {
    return (
      <svg className="task-icon done" width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="5.5" fill="currentColor" opacity="0.15" />
        <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M5.5 8.25l1.75 1.75L10.5 6.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  return (
    <svg className="task-icon error" width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="5.5" fill="currentColor" opacity="0.15" />
      <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M6 6l4 4M10 6l-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

const LOG_ICONS: Record<TaskLog['type'], string> = {
  agent_log:   '·',
  tool_call:   '→',
  tool_result: '←',
};

function TaskLogList({ logs }: { logs: TaskLog[] }) {
  if (logs.length === 0) return null;
  return (
    <ul className="task-log-list">
      {logs.map((log, i) => (
        <li key={i} className={`task-log-entry log-${log.type}`}>
          <span className="log-icon">{LOG_ICONS[log.type]}</span>
          <span className="log-msg">{log.message}</span>
        </li>
      ))}
    </ul>
  );
}

interface Props {
  plan: Plan;
  tasks: Task[];
  phase: PlanPhase;
  onConfirm: () => void;
  onCancel: () => void;
  error?: string;
}

export default function PlanMessage({ plan, tasks, phase, onConfirm, onCancel, error }: Props) {
  const doneCount = tasks.filter(t => t.status === 'done').length;
  const total = tasks.length;

  return (
    <div className="plan-message">
      <div className="plan-header">
        <span className="plan-label">Plan</span>
        {phase !== 'confirming' && total > 0 && (
          <span className="plan-progress">
            {doneCount}/{total}
          </span>
        )}
      </div>

      <p className="plan-goal">{plan.goal}</p>

      {tasks.length > 0 && (
        <ul className="task-list">
          {tasks.map(task => (
            <li key={task.id} className={`task-item task-${task.status}`}>
              <StatusIcon status={task.status} />
              <div className="task-body">
                <span className="task-desc">{task.description}</span>
                {task.tool !== 'none' && (
                  <span className="task-tool">{TOOL_LABELS[task.tool] ?? task.tool}</span>
                )}
                {task.summary && (
                  <span className="task-summary">{task.summary}</span>
                )}
                {(task.status === 'running' || task.logs.length > 0) && (
                  <TaskLogList logs={task.logs} />
                )}
              </div>
              {task.status === 'running' && (
                <span className="task-running-badge">Running…</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {error && <p className="plan-error">{error}</p>}

      {phase === 'confirming' && (
        <div className="plan-actions">
          <button className="btn-run" onClick={onConfirm}>
            Run plan
          </button>
          <button className="btn-ghost" onClick={onCancel}>
            Cancel
          </button>
        </div>
      )}

      {phase === 'running' && (
        <p className="plan-running-hint">Executing…</p>
      )}

      {phase === 'done' && !error && (
        <p className="plan-done-hint">Done</p>
      )}
    </div>
  );
}
