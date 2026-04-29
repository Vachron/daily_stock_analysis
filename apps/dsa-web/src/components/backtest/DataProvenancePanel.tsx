import { useState } from 'react';
import { ChevronDown, ChevronUp, Search } from 'lucide-react';

interface ProvenanceStep {
  description: string;
  result_sample: string;
}

interface DataProvenancePanelProps {
  metric: string;
  formulaHuman: string;
  formulaExact: string;
  inputs: Array<{ field: string; range: string; record_count: number }>;
  steps: ProvenanceStep[];
}

export function DataProvenancePanel({ metric, formulaHuman, formulaExact, inputs, steps }: DataProvenancePanelProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl bg-card/30 border border-border/20">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between p-3 text-left"
      >
        <div className="flex items-center gap-2">
          <Search className="h-3.5 w-3.5 text-cyan" />
          <span className="text-xs font-medium text-foreground">数据溯源: {metric}</span>
        </div>
        {open ? <ChevronUp className="h-3.5 w-3.5 text-muted-text" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-text" />}
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-3 animate-fade-in">
          <div>
            <span className="text-[10px] font-medium text-cyan block mb-1">📐 计算方式</span>
            <p className="text-[10px] text-muted-text">{formulaHuman}</p>
            <code className="text-[9px] text-muted-text/60 mt-0.5 block font-mono">{formulaExact}</code>
          </div>
          <div>
            <span className="text-[10px] font-medium text-cyan block mb-1">📥 输入数据</span>
            {inputs.map((inp, i) => (
              <div key={i} className="flex justify-between text-[10px] py-0.5">
                <span className="text-muted-text">{inp.field}</span>
                <span className="text-foreground font-mono">{inp.range} ({inp.record_count}条)</span>
              </div>
            ))}
          </div>
          <div>
            <span className="text-[10px] font-medium text-cyan block mb-1">📝 计算步骤</span>
            {steps.map((s, i) => (
              <div key={i} className="text-[10px] py-0.5 border-b border-border/10 last:border-0">
                <span className="text-secondary-text">{i + 1}. {s.description}</span>
                {s.result_sample && <span className="text-muted-text/60 block text-[9px] font-mono">{s.result_sample}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
