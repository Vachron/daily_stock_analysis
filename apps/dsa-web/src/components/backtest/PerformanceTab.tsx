import { BarChart3 } from 'lucide-react';

interface PerformanceTabProps {
  metrics: Record<string, number>;
}

const METRIC_META: Array<{ key: string; label: string; format: 'pct' | 'num' | 'int'; tooltip: string }> = [
  { key: 'total_return_pct', label: '总收益率', format: 'pct', tooltip: '整个回测区间的累计收益百分比' },
  { key: 'annualized_return_pct', label: '年化收益率', format: 'pct', tooltip: '按复利折算的年化收益率' },
  { key: 'sharpe_ratio', label: '夏普比率', format: 'num', tooltip: '(策略收益 - 无风险利率) / 波动率，衡量风险调整后收益' },
  { key: 'sortino_ratio', label: '索提诺比率', format: 'num', tooltip: '仅用下行波动率计算的夏普比率，对回撤更敏感' },
  { key: 'calmar_ratio', label: '卡尔玛比率', format: 'num', tooltip: '年化收益 / 最大回撤，衡量回撤效率' },
  { key: 'max_drawdown_pct', label: '最大回撤', format: 'pct', tooltip: '净值最高点到最低点的最大亏损' },
  { key: 'excess_return_pct', label: '超额收益', format: 'pct', tooltip: '组合收益减去基准(沪深300)收益' },
  { key: 'information_ratio', label: '信息比率', format: 'num', tooltip: '超额收益 / 跟踪误差' },
  { key: 'tracking_error_pct', label: '跟踪误差', format: 'pct', tooltip: '组合与基准的标准差' },
  { key: 'win_rate_pct', label: '胜率', format: 'pct', tooltip: '盈利交易占总交易的比例' },
  { key: 'turnover_rate_pct', label: '换手率', format: 'pct', tooltip: '平均每期交易金额占组合的比例' },
  { key: 'total_trades', label: '交易总数', format: 'int', tooltip: '买入卖出合计' },
  { key: 'avg_return_per_trade_pct', label: '平均单笔收益', format: 'pct', tooltip: '每笔交易的算术平均收益' },
  { key: 'max_single_return_pct', label: '最大单笔盈利', format: 'pct', tooltip: '单笔交易最大盈利' },
  { key: 'max_single_loss_pct', label: '最大单笔亏损', format: 'pct', tooltip: '单笔交易最大亏损' },
];

function formatValue(val: number | undefined, format: 'pct' | 'num' | 'int'): string {
  if (val == null) return '--';
  if (format === 'pct') return `${val > 0 ? '+' : ''}${val.toFixed(2)}%`;
  if (format === 'int') return String(Math.round(val));
  return val.toFixed(4);
}

function valueColor(val: number | undefined, format: 'pct' | 'num' | 'int'): string {
  if (val == null) return 'text-muted-text';
  if (format === 'pct' || format === 'num') {
    if (val > 0) return 'text-success';
    if (val < 0) return 'text-danger';
  }
  return 'text-foreground';
}

export function PerformanceTab({ metrics }: PerformanceTabProps) {
  if (!metrics || Object.keys(metrics).length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-text gap-2">
        <BarChart3 className="h-8 w-8" />
        <span className="text-xs">暂无绩效数据</span>
      </div>
    );
  }

  const visible = METRIC_META.filter(m => metrics[m.key] != null);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border/20">
            <th className="text-left py-2 px-3 text-muted-text font-medium w-32">指标</th>
            <th className="text-right py-2 px-3 text-muted-text font-medium">数值</th>
            <th className="hidden sm:table-cell text-left py-2 px-3 text-muted-text font-medium">说明</th>
          </tr>
        </thead>
        <tbody>
          {visible.map(m => (
            <tr key={m.key} className="border-b border-border/10 hover:bg-border/5 transition-colors">
              <td className="py-2 px-3 text-secondary-text font-medium" title={m.tooltip}>
                {m.label}
              </td>
              <td className={`py-2 px-3 text-right font-mono tabular-nums ${valueColor(metrics[m.key], m.format)}`}>
                {formatValue(metrics[m.key], m.format)}
              </td>
              <td className="hidden sm:table-cell py-2 px-3 text-muted-text text-[10px]">
                {m.tooltip}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[9px] text-muted-text mt-2 px-3">鼠标悬停指标名查看详细解释</p>
    </div>
  );
}
