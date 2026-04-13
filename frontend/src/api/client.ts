import type { Plan, UserProfile } from '../types';

const BASE = 'http://localhost:8000';

export async function generatePlan(message: string, model = 'gpt-4o-mini'): Promise<Plan> {
  const res = await fetch(`${BASE}/chat/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, model }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface RunEvent {
  type: 'task_start' | 'task_done' | 'complete' | 'error' | 'agent_log' | 'tool_call' | 'tool_result';
  task_id?: number;
  summary?: string;
  message?: string;
  tool?: string;
}

export function runPlan(
  plan: Plan,
  model: string,
  onEvent: (event: RunEvent) => void,
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${BASE}/chat/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan, model }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              onEvent(JSON.parse(line.slice(6)));
            } catch {
              // skip malformed line
            }
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        onEvent({ type: 'error', message: err.message });
      }
    }
  })();

  return () => controller.abort();
}

export async function getProfile(): Promise<UserProfile> {
  const res = await fetch(`${BASE}/profile`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function updateProfile(profile: UserProfile): Promise<UserProfile> {
  const res = await fetch(`${BASE}/profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getContext(): Promise<{ role: string; content: string }[]> {
  const res = await fetch(`${BASE}/context`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.messages;
}

export async function clearContext(): Promise<void> {
  await fetch(`${BASE}/context`, { method: 'DELETE' });
}
