export interface TaskLog {
  type: 'agent_log' | 'tool_call' | 'tool_result';
  message: string;
  tool?: string;
}

export interface Task {
  id: number;
  description: string;
  tool: string;
  args: Record<string, unknown>;
  status: 'pending' | 'running' | 'done' | 'error';
  summary?: string;
  logs: TaskLog[];
}

export interface Plan {
  goal: string;
  tasks: Task[];
}

export interface UserProfile {
  background: string;
  preferences: string;
  cover_letter_tone: string;
}

export type PlanPhase = 'confirming' | 'running' | 'done';

export type ChatMessage =
  | { id: string; type: 'user'; content: string }
  | { id: string; type: 'plan'; plan: Plan; tasks: Task[]; phase: PlanPhase; error?: string };
