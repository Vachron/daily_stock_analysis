interface SensitivityCell {
  metric: string;
  paramName: string;
  score: number;
}

interface ParamSensitivityHeatmapProps {
  data: SensitivityCell[];
  params: string[];
  metrics: string[];
}

export function ParamSensitivityHeatmap({ data, params, metrics }: ParamSensitivityHeatmapProps) {
  const lookup = new Map<string, number>();
  for (const d of data) {
    lookup.set(`${d.paramName}:${d.metric}`, d.score);
  }

  if (params.length === 0 || metrics.length === 0) {
    return (
      <div className="text-center py-4 text-[10px] text-muted-text">
        暂无敏感性数据。运行回测或优化后可展示参数对指标的影响程度。
      </div>
    );
  }

  const allScores = data.map((d) => d.score);
  const maxScore = Math.max(...allScores, 0.001);

  function scoreColor(score: number): string {
    if (score >= 0.8) return 'bg-red-400/80 text-white';
    if (score >= 0.5) return 'bg-orange-400/70 text-white';
    if (score >= 0.3) return 'bg-yellow-400/60 text-gray-900';
    return 'bg-gray-400/30 text-muted-text';
  }

  function scoreLabel(score: number): string {
    if (score >= 0.8) return '极敏感';
    if (score >= 0.5) return '较敏感';
    if (score >= 0.3) return '一般';
    return '不敏感';
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-secondary-text">🔬 参数敏感性分析</span>
        <span className="text-[9px] text-muted-text">哪个参数最值得调？</span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border/20">
        <table className="w-full text-[10px] border-collapse">
          <thead>
            <tr>
              <th className="text-left px-2 py-1.5 text-muted-text font-medium bg-border/5 sticky left-0">参数 \ 指标</th>
              {metrics.map((m) => (
                <th key={m} className="text-center px-2 py-1.5 text-muted-text font-medium bg-border/5 whitespace-nowrap">
                  {m.slice(0, 8)}
                </th>
              ))}
              <th className="text-center px-2 py-1.5 text-muted-text font-medium bg-border/5 whitespace-nowrap">敏感度</th>
            </tr>
          </thead>
          <tbody>
            {params.map((param) => {
              const paramScores = metrics.map((m) => lookup.get(`${param}:${m}`) ?? 0);
              const avgScore = paramScores.reduce((a, b) => a + b, 0) / paramScores.length;
              return (
                <tr key={param} className="border-t border-border/10 hover:bg-border/5 transition-colors">
                  <td className="px-2 py-1.5 font-mono text-muted-text bg-border/5 sticky left-0">{param}</td>
                  {metrics.map((metric) => {
                    const score = lookup.get(`${param}:${metric}`) ?? 0;
                    const bgOpacity = Math.max(0.1, (score / maxScore) * 0.6);
                    return (
                      <td
                        key={metric}
                        className="text-center px-2 py-1.5 font-mono tabular-nums whitespace-nowrap"
                        style={{
                          background: score > 0.3
                            ? score >= 0.8
                              ? `rgba(239,68,68,${bgOpacity.toFixed(2)})`
                              : score >= 0.5
                                ? `rgba(249,115,22,${bgOpacity.toFixed(2)})`
                                : `rgba(234,179,8,${bgOpacity.toFixed(2)})`
                            : `rgba(156,163,175,${bgOpacity.toFixed(2)})`,
                        }}
                        title={`${param} × ${metric}: ${score.toFixed(3)} — ${scoreLabel(score)}`}
                      >
                        {score.toFixed(2)}
                      </td>
                    );
                  })}
                  <td className="text-center px-2 py-1.5 font-medium">
                    <span className={`inline-block px-1.5 py-0.5 rounded text-[8px] ${scoreColor(avgScore)}`}>
                      {avgScore.toFixed(2)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-3 justify-center text-[8px] text-muted-text">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-red-400/80" /> ≥0.8 极敏感</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-orange-400/70" /> ≥0.5 较敏感</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-yellow-400/60" /> ≥0.3 一般</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-gray-400/30" /> &lt;0.3 不敏感</span>
      </div>

      <div className="rounded-lg bg-cyan/5 border border-cyan/10 p-2">
        <p className="text-[9px] text-cyan/80">
          💡 得分最高的参数对你的策略影响最大，建议优先优化。敏感性 = 该参数在取值范围内变化时, 对应指标的变化幅度(归一化到0-1)。
        </p>
      </div>
    </div>
  );
}
