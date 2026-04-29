interface ParamHeatmapProps {
  heatmap?: Record<string, unknown>;
  height?: number;
}

export function ParamHeatmap({ heatmap }: ParamHeatmapProps) {
  if (!heatmap || !heatmap.data) {
    return (
      <div className="text-center py-4 text-[10px] text-muted-text">
        无热力图数据，请先运行参数优化
      </div>
    );
  }

  const data = heatmap.data as Record<number, Record<number, number>>;
  const xParam = String(heatmap.x_param || '');
  const yParam = String(heatmap.y_param || '');
  const metric = String(heatmap.metric || '');

  const xKeys = Object.keys(data).map(Number).sort((a, b) => a - b);
  const yKeys: number[] = [];
  for (const x of xKeys) {
    for (const y of Object.keys(data[x] || {})) {
      if (!yKeys.includes(Number(y))) yKeys.push(Number(y));
    }
  }
  yKeys.sort((a, b) => a - b);

  const values: number[] = [];
  for (const x of xKeys) {
    for (const y of yKeys) {
      values.push(data[x]?.[y] ?? 0);
    }
  }
  const maxVal = Math.max(...values);
  const minVal = Math.min(...values);

  if (xKeys.length === 0 || yKeys.length === 0) {
    return <div className="text-center py-4 text-[10px] text-muted-text">热力图数据为空</div>;
  }

  const cellW = Math.max(28, Math.min(50, Math.floor(600 / xKeys.length)));
  const cellH = Math.max(18, Math.min(32, Math.floor(400 / yKeys.length)));

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-secondary-text">参数热力图</span>
        <span className="text-[9px] text-muted-text">{xParam} × {yParam} → {metric}</span>
      </div>
      <div className="overflow-auto">
        <div className="inline-block">
          <div className="flex">
            <div style={{ width: 40 }} />
            {xKeys.map((x) => (
              <div key={x} style={{ width: cellW }} className="text-center text-[8px] text-muted-text pb-1">
                {x}
              </div>
            ))}
          </div>
          {yKeys.map((y) => (
            <div key={y} className="flex">
              <div style={{ width: 40 }} className="text-right text-[8px] text-muted-text pr-1 leading-none flex items-center justify-end">
                {y}
              </div>
              {xKeys.map((x) => {
                const v = data[x]?.[y];
                if (v == null) return <div key={x} style={{ width: cellW, height: cellH }} className="border border-border/10" />;
                const ratio = maxVal !== minVal ? (v - minVal) / (maxVal - minVal) : 0.5;
                const r = Math.round(6 + ratio * 30);
                const g = Math.round(182 + ratio * (55 - 182));
                const b = Math.round(212 + ratio * (65 - 212));
                return (
                  <div
                    key={x}
                    style={{ width: cellW, height: cellH, background: `rgb(${r},${g},${b})` }}
                    className="border border-border/10 flex items-center justify-center relative group"
                    title={`${xParam}=${x}, ${yParam}=${y}: ${v.toFixed(3)}`}
                  >
                    <span className="text-[7px] text-white/80 tabular-nums">{v.toFixed(2)}</span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-1.5 justify-center">
        <span className="text-[8px] text-muted-text">{minVal.toFixed(3)}</span>
        <div className="h-2 w-28 rounded" style={{ background: 'linear-gradient(to right, #06b6d4, #0ea5e9, #22c55e)' }} />
        <span className="text-[8px] text-muted-text">{maxVal.toFixed(3)}</span>
      </div>
    </div>
  );
}
