import type React from 'react';
import { useState } from 'react';
import { Badge, Card, StatusDot } from '../common';
import { DashboardPanelHeader } from '../dashboard';
import type { TaskInfo, AnalysisProgressStep } from '../../types/analysis';

interface TaskItemProps {
  task: TaskInfo;
}

const STAGE_ICONS: Record<string, string> = {
  prepare: '⚙',
  data_fetch: '📊',
  realtime_quote: '📈',
  chip: '🎯',
  fundamental: '📋',
  trend: '📉',
  news: '📰',
  agent_switch: '🤖',
  context: '📦',
  llm: '🧠',
  validate: '✅',
  save: '💾',
};

function getStepIcon(stage: string): string {
  return STAGE_ICONS[stage] || '●';
}

function getStepStatusStyle(step: AnalysisProgressStep): { dotClass: string; textClass: string } {
  if (step.status === 'done') {
    return { dotClass: 'bg-emerald-400 shadow-[0_0_0_3px_hsl(142_76%_36%/0.12)]', textClass: 'text-emerald-400' };
  }
  if (step.status === 'error') {
    return { dotClass: 'bg-red-400 shadow-[0_0_0_3px_hsl(0_84%_60%/0.12)]', textClass: 'text-red-400' };
  }
  return { dotClass: 'bg-cyan shadow-[0_0_0_3px_hsl(var(--primary)/0.12)] animate-pulse', textClass: 'text-secondary-text' };
}

const TaskStepList: React.FC<{ steps: AnalysisProgressStep[] }> = ({ steps }) => {
  if (steps.length === 0) return null;

  return (
    <div className="ml-1 mt-1.5 space-y-1 border-l border-border/30 pl-3">
      {steps.map((step, idx) => {
        const { dotClass, textClass } = getStepStatusStyle(step);
        const icon = getStepIcon(step.stage);
        return (
          <div key={`${step.stage}-${idx}`} className="flex items-start gap-2 text-[11px] leading-relaxed">
            <span className={`mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full ${dotClass}`} />
            <span className={`${textClass} flex-1`}>
              <span className="mr-1">{icon}</span>
              {step.label}
              {step.detail && (
                <span className="ml-1 text-muted-text">· {step.detail}</span>
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
};

const TaskItem: React.FC<TaskItemProps> = ({ task }) => {
  const isPending = task.status === 'pending';
  const isProcessing = task.status === 'processing';
  const statusLabel = isProcessing ? '分析中' : '等待中';
  const statusVariant = isProcessing ? 'info' : 'default';
  const statusTone = isProcessing ? 'info' : 'neutral';
  const progress = Math.max(0, Math.min(100, task.progress || 0));
  const [expanded, setExpanded] = useState(true);
  const hasSteps = task.steps && task.steps.length > 0;

  return (
    <div className="home-subpanel px-3 py-2.5">
      <div className="flex items-center gap-3">
        <div className="shrink-0">
          {isProcessing ? (
            <StatusDot tone="info" pulse className="h-2.5 w-2.5" aria-label="任务进行中" />
          ) : isPending ? (
            <StatusDot tone="neutral" className="h-2.5 w-2.5" aria-label="任务等待中" />
          ) : null}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-foreground truncate">
              {task.stockName || task.stockCode}
            </span>
            <span className="text-xs text-muted-text">
              {task.stockCode}
            </span>
            {hasSteps && isProcessing && (
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="ml-auto shrink-0 rounded p-0.5 text-muted-text transition-colors hover:bg-white/8 hover:text-foreground"
                aria-label={expanded ? '收起详情' : '展开详情'}
              >
                <svg
                  className={`h-3.5 w-3.5 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            )}
          </div>
          {task.message && (
            <p className="text-xs text-secondary-text truncate mt-0.5">
              {task.message}
            </p>
          )}
          <div className="mt-2 flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/8">
              <div
                className="h-full rounded-full bg-cyan transition-[width] duration-300 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="shrink-0 text-[11px] text-muted-text tabular-nums">
              {progress}%
            </span>
          </div>
        </div>

        <div className="flex-shrink-0">
          <Badge
            variant={statusVariant}
            className="min-w-[4.75rem] justify-center gap-1.5 shadow-none"
            aria-label={`任务状态：${statusLabel}`}
          >
            <StatusDot tone={statusTone} pulse={isProcessing} className="h-1.5 w-1.5" />
            {statusLabel}
          </Badge>
        </div>
      </div>

      {hasSteps && expanded && isProcessing && (
        <TaskStepList steps={task.steps} />
      )}
    </div>
  );
};

interface TaskPanelProps {
  tasks: TaskInfo[];
  visible?: boolean;
  title?: string;
  className?: string;
}

export const TaskPanel: React.FC<TaskPanelProps> = ({
  tasks,
  visible = true,
  title = '分析任务',
  className = '',
}) => {
  const activeTasks = tasks.filter(
    (t) => t.status === 'pending' || t.status === 'processing'
  );

  if (!visible || activeTasks.length === 0) {
    return null;
  }

  const pendingCount = activeTasks.filter((t) => t.status === 'pending').length;
  const processingCount = activeTasks.filter((t) => t.status === 'processing').length;

  return (
    <Card
      variant="bordered"
      padding="none"
      className={`home-panel-card overflow-hidden ${className}`}
    >
      <div className="border-b border-subtle px-3 py-3">
        <DashboardPanelHeader
          className="mb-0"
          title={title}
          titleClassName="text-sm font-medium"
          leading={(
            <svg className="h-4 w-4 text-cyan" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          )}
          headingClassName="items-center"
          actions={(
            <div className="flex items-center gap-2 text-xs text-muted-text">
              {processingCount > 0 && (
                <span className="flex items-center gap-1">
                  <StatusDot tone="info" pulse className="h-1.5 w-1.5" aria-label="进行中任务" />
                  {processingCount} 进行中
                </span>
              )}
              {pendingCount > 0 ? (
                <span className="flex items-center gap-1">
                  <StatusDot tone="neutral" className="h-1.5 w-1.5" aria-label="等待中任务" />
                  {pendingCount} 等待中
                </span>
              ) : null}
            </div>
          )}
        />
      </div>

      <div className="max-h-80 overflow-y-auto p-2">
        <div className="space-y-2">
          {activeTasks.map((task) => (
            <TaskItem key={task.taskId} task={task} />
          ))}
        </div>
      </div>
    </Card>
  );
};

export default TaskPanel;
