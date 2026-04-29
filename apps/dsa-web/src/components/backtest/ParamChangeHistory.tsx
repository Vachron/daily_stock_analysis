import { useState } from 'react';

export interface ParamChangeRecord {
  id: string;
  timestamp: string;
  changeType: 'manual' | 'preset' | 'optimization' | 'reset';
  changes: Array<{ param: string; oldValue: number | string; newValue: number | string }>;
  source: string;
}

interface ParamChangeHistoryProps {
  history: ParamChangeRecord[];
  onSelect?: (record: ParamChangeRecord) => void;
  maxItems?: number;
}

const TYPE_LABELS: Record<string, string> = {
  manual: '手动', preset: '预设', optimization: '优化', reset: '重置',
};

export function ParamChangeHistory({ history, onSelect, maxItems = 10 }: ParamChangeHistoryProps) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? history.slice(0, maxItems) : history.slice(0, 3);

  if (history.length === 0) {
    return null;
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium text-secondary-text">📝 参数变更历史</span>
        <span className="text-[9px] text-muted-text">{history.length} 次变更</span>
      </div>

      <div className="space-y-1">
        {visible.map((record) => (
          <button
            key={record.id}
            type="button"
            onClick={() => onSelect?.(record)}
            className="w-full text-left rounded-lg bg-card/30 border border-border/20 px-2.5 py-1.5 hover:border-cyan/20 transition-colors group"
          >
            <div className="flex items-center gap-2">
              <span className="text-[8px] text-muted-text/50 font-mono">{record.timestamp}</span>
              <span className={`text-[8px] px-1 py-0.5 rounded font-medium ${
                record.changeType === 'manual' ? 'bg-cyan/10 text-cyan' :
                record.changeType === 'preset' ? 'bg-success/10 text-success' :
                record.changeType === 'optimization' ? 'bg-warning/10 text-warning' :
                'bg-muted/10 text-muted-text'
              }`}>
                {TYPE_LABELS[record.changeType] || record.changeType}
              </span>
              <span className="text-[9px] text-muted-text flex-1 truncate">{record.source}</span>
            </div>
            <div className="flex flex-wrap gap-1 mt-1">
              {record.changes.map((ch) => (
                <span key={ch.param} className="text-[8px] font-mono text-muted-text/60">
                  {ch.param}: <span className="text-muted-text">{String(ch.oldValue)}</span>
                  <span className="text-cyan mx-0.5">→</span>
                  <span className="text-foreground">{String(ch.newValue)}</span>
                </span>
              ))}
            </div>
          </button>
        ))}

        {history.length > 3 && !expanded && (
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="w-full text-center text-[9px] text-cyan hover:text-cyan/80 transition-colors py-1"
          >
            显示全部 {history.length} 条历史
          </button>
        )}
      </div>
    </div>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useParamChangeHistory() {
  const [history, setHistory] = useState<ParamChangeRecord[]>([]);

  const addChange = (
    changeType: ParamChangeRecord['changeType'],
    changes: ParamChangeRecord['changes'],
    source: string,
  ) => {
    setHistory((prev) => [
      {
        id: crypto.randomUUID?.() || Math.random().toString(36).slice(2),
        timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        changeType,
        changes,
        source,
      },
      ...prev,
    ]);
  };

  const clear = () => setHistory([]);

  return { history, addChange, clear };
}
