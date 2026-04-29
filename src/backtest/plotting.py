# -*- coding: utf-8 -*-
"""HTML 交互式报告生成 (FR-010)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from src.backtest.engine import BacktestResult


def _series_to_dict(stats: pd.Series) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for k, v in stats.items():
        if pd.isna(v):
            result[str(k)] = None
        elif isinstance(v, (float, int, bool, str)):
            result[str(k)] = v
        else:
            result[str(k)] = str(v)
    return result


def generate_html_report(result: "BacktestResult") -> str:
    """生成交互式 HTML 回测报告 (FR-010).

    使用 Plotly 生成交互式图表，单文件 HTML，无外部依赖.
    """
    stats_dict = _series_to_dict(result.stats)

    equity_data_json = "[]"
    if not result.equity_curve.empty:
        eq = result.equity_curve.reset_index()
        eq.columns = ["Date", "Equity", "DrawdownPct", "DrawdownDuration"]
        equity_data_json = eq.to_json(orient="records", date_format="iso")

    trades_data_json = "[]"
    if not result.trades.empty:
        trades_data_json = result.trades.to_json(orient="records", date_format="iso")

    stats_json = json.dumps(stats_dict, default=str, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>回测报告 - {result.strategy_name} | {result.symbol}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
  .header {{ text-align: center; padding: 24px 0; border-bottom: 1px solid #334155; margin-bottom: 24px; }}
  .header h1 {{ font-size: 24px; color: #38bdf8; }}
  .header p {{ color: #94a3b8; margin-top: 8px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }}
  .card .label {{ font-size: 12px; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px; }}
  .card .value {{ font-size: 28px; font-weight: 700; }}
  .green {{ color: #22c55e; }} .red {{ color: #ef4444; }} .yellow {{ color: #eab308; }} .blue {{ color: #38bdf8; }}
  .chart {{ background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 24px; border: 1px solid #334155; }}
  .chart h2 {{ font-size: 16px; color: #e2e8f0; margin-bottom: 12px; }}
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .metric-group {{ background: #1e293b; border-radius: 12px; padding: 16px; border: 1px solid #334155; }}
  .metric-group h3 {{ font-size: 14px; color: #38bdf8; margin-bottom: 12px; border-bottom: 1px solid #334155; padding-bottom: 8px; }}
  .metric-row {{ display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }}
  .metric-row .label-col {{ color: #94a3b8; }}
  .metric-row .value-col {{ font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #334155; }}
  th {{ color: #94a3b8; font-weight: 600; }}
  .exit-badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; }}
  .exit-trailing_stop {{ background: rgba(234,179,8,0.2); color: #eab308; }}
  .exit-take_profit {{ background: rgba(34,197,94,0.2); color: #22c55e; }}
  .exit-stop_loss {{ background: rgba(239,68,68,0.2); color: #ef4444; }}
  .exit-signal_lost {{ background: rgba(56,189,248,0.2); color: #38bdf8; }}
  .exit-fixed_days {{ background: rgba(168,85,247,0.2); color: #a855f7; }}
  .exit-max_hold_days {{ background: rgba(249,115,22,0.2); color: #f97316; }}
  .exit-force_close {{ background: rgba(156,163,175,0.2); color: #9ca3af; }}
  .section {{ margin-bottom: 24px; }}
  .section h2 {{ font-size: 18px; color: #e2e8f0; margin-bottom: 12px; border-left: 3px solid #38bdf8; padding-left: 12px; }}
  #equity-chart, #drawdown-chart, #kline-chart, #exit-pie, #monthly-heatmap {{ width: 100%; min-height: 400px; }}
</style>
</head>
<body>

<div class="header">
  <h1>📊 回测报告</h1>
  <p>{result.strategy_name} | {result.symbol} | {result.start_date} ~ {result.end_date}</p>
  <p style="color:#64748b;font-size:12px;">初始资金: ¥{result.initial_cash:,.0f} | 引擎版本: {result.engine_version}</p>
</div>

<div class="cards">
  <div class="card">
    <div class="label">累计收益</div>
    <div class="value {_color_class(stats_dict.get('Return [%]', 0))}">{_format_pct(stats_dict.get('Return [%]'))}</div>
  </div>
  <div class="card">
    <div class="label">夏普比率</div>
    <div class="value blue">{stats_dict.get('Sharpe Ratio', '-')}</div>
  </div>
  <div class="card">
    <div class="label">最大回撤</div>
    <div class="value {_color_class(stats_dict.get('Max Drawdown [%]', 0), reverse=True)}">{_format_pct(stats_dict.get('Max Drawdown [%]'))}</div>
  </div>
  <div class="card">
    <div class="label">胜率</div>
    <div class="value {_color_class(stats_dict.get('Win Rate [%]', 50))}">{stats_dict.get('Win Rate [%]', '-')}%</div>
  </div>
  <div class="card">
    <div class="label">交易次数</div>
    <div class="value blue">{stats_dict.get('# Trades', '-')}</div>
  </div>
  <div class="card">
    <div class="label">盈亏比</div>
    <div class="value {_color_class(stats_dict.get('Profit Factor', 1) * 10)}">{stats_dict.get('Profit Factor', '-')}</div>
  </div>
</div>

<div class="section">
  <h2>权益曲线</h2>
  <div class="chart">
    <div id="equity-chart"></div>
  </div>
</div>

<div class="section">
  <h2>回撤曲线</h2>
  <div class="chart">
    <div id="drawdown-chart"></div>
  </div>
</div>

<div class="section">
  <h2>绩效指标</h2>
  <div class="metrics">
    {_render_metric_group("收益指标", [
      ("总收益率", stats_dict.get("Return [%]"), "%"),
      ("年化收益率", stats_dict.get("Return (Ann.) [%]"), "%"),
      ("CAGR", stats_dict.get("CAGR [%]"), "%"),
      ("买入持有收益率", stats_dict.get("Buy & Hold Return [%]"), "%"),
      ("暴露时间", stats_dict.get("Exposure Time [%]"), "%"),
      ("最终权益", stats_dict.get("Equity Final [$]"), "¥"),
      ("最高权益", stats_dict.get("Equity Peak [$]"), "¥"),
    ])}
    {_render_metric_group("风险指标", [
      ("年化波动率", stats_dict.get("Volatility (Ann.) [%]"), "%"),
      ("最大回撤", stats_dict.get("Max Drawdown [%]"), "%"),
      ("平均回撤", stats_dict.get("Avg Drawdown [%]"), "%"),
      ("最大回撤持续", stats_dict.get("Max Drawdown Duration"), "天"),
      ("平均回撤持续", stats_dict.get("Avg Drawdown Duration"), "天"),
    ])}
    {_render_metric_group("风险调整指标", [
      ("夏普比率", stats_dict.get("Sharpe Ratio"), ""),
      ("Sortino比率", stats_dict.get("Sortino Ratio"), ""),
      ("Calmar比率", stats_dict.get("Calmar Ratio"), ""),
    ])}
    {_render_metric_group("CAPM指标", [
      ("Alpha", stats_dict.get("Alpha [%]"), "%"),
      ("Beta", stats_dict.get("Beta"), ""),
    ])}
    {_render_metric_group("交易统计", [
      ("交易次数", stats_dict.get("# Trades"), "次"),
      ("胜率", stats_dict.get("Win Rate [%]"), "%"),
      ("最佳交易", stats_dict.get("Best Trade [%]"), "%"),
      ("最差交易", stats_dict.get("Worst Trade [%]"), "%"),
      ("平均交易", stats_dict.get("Avg Trade [%]"), "%"),
      ("盈亏比", stats_dict.get("Profit Factor"), ""),
      ("SQN", stats_dict.get("SQN"), ""),
      ("Kelly", stats_dict.get("Kelly Criterion"), ""),
      ("期望收益", stats_dict.get("Expectancy [%]"), "%"),
      ("最长持仓", stats_dict.get("Max Trade Duration"), "天"),
      ("平均持仓", stats_dict.get("Avg Trade Duration"), "天"),
    ])}
    {_render_metric_group("A股扩展指标", [
      ("换手率", stats_dict.get("Turnover Rate [%]"), "%"),
      ("日胜率", stats_dict.get("Day Win Rate [%]"), "%"),
      ("盈亏比(均)", stats_dict.get("Profit/Loss Ratio"), ""),
      ("平均盈利", stats_dict.get("Avg Win [%]"), "%"),
      ("平均亏损", stats_dict.get("Avg Loss [%]"), "%"),
      ("总手续费", stats_dict.get("Commissions [$]"), "¥"),
    ])}
  </div>
</div>

<div class="section">
  <h2>交易明细</h2>
  <div class="chart" style="overflow-x:auto;">
    <div id="trades-table"></div>
  </div>
</div>

<script>
  // Embed data
  var equityData = {equity_data_json};
  var tradesData = {trades_data_json};

  // Equity curve
  if (equityData && equityData.length > 0) {{
    var dates = equityData.map(d => d.Date);
    var equityVals = equityData.map(d => d.Equity);
    var ddVals = equityData.map(d => d.DrawdownPct);

    Plotly.newPlot('equity-chart', [{{
      x: dates, y: equityVals, type: 'scatter', mode: 'lines',
      name: '策略权益', line: {{ color: '#38bdf8', width: 2 }},
      fill: 'tozeroy', fillcolor: 'rgba(56,189,248,0.1)'
    }}], {{
      template: 'plotly_dark',
      paper_bgcolor: '#1e293b', plot_bgcolor: '#1e293b',
      margin: {{ l: 60, r: 20, t: 10, b: 40 }},
      xaxis: {{ gridcolor: '#334155', title: '' }},
      yaxis: {{ gridcolor: '#334155', title: '权益 (¥)' }},
      showlegend: true, legend: {{ x: 0.01, y: 0.99 }}
    }}, {{ responsive: true }});

    Plotly.newPlot('drawdown-chart', [{{
      x: dates, y: ddVals, type: 'scatter', mode: 'lines',
      name: '回撤', line: {{ color: '#ef4444', width: 1.5 }},
      fill: 'tozeroy', fillcolor: 'rgba(239,68,68,0.15)'
    }}], {{
      template: 'plotly_dark',
      paper_bgcolor: '#1e293b', plot_bgcolor: '#1e293b',
      margin: {{ l: 60, r: 20, t: 10, b: 40 }},
      xaxis: {{ gridcolor: '#334155', title: '' }},
      yaxis: {{ gridcolor: '#334155', title: '回撤 (%)', tickformat: '.1f', ticksuffix: '%' }}
    }}, {{ responsive: true }});
  }}

  // Trades table
  if (tradesData && tradesData.length > 0) {{
    var headers = Object.keys(tradesData[0]).filter(function(k) {{
      return !['EntryBar','ExitBar','SL','TP','PositionPct'].includes(k);
    }});
    var thead = '<tr>' + headers.map(h => '<th>' + h + '</th>').join('') + '</tr>';
    var tbody = tradesData.map(function(t) {{
      var exitClass = 'exit-' + (t.ExitReason || 'force_close');
      return '<tr>' + headers.map(function(h) {{
        var v = t[h];
        if (h === 'ExitReason' && v) {{
          return '<td><span class="exit-badge ' + exitClass + '">' + v + '</span></td>';
        }}
        if (h === 'ReturnPct' && v != null) {{
          var cls = v >= 0 ? 'green' : 'red';
          return '<td class="' + cls + '">' + (v >= 0 ? '+' : '') + v.toFixed(2) + '%</td>';
        }}
        if (v != null) return '<td>' + v + '</td>';
        return '<td>-</td>';
      }}).join('') + '</tr>';
    }}).join('');
    document.getElementById('trades-table').innerHTML = '<table>' + thead + tbody + '</table>';
  }} else {{
    document.getElementById('trades-table').innerHTML = '<p style="color:#94a3b8; text-align:center; padding:40px;">无交易记录</p>';
  }}
</script>

</body>
</html>"""
    return html


def _color_class(value: Any, reverse: bool = False) -> str:
    try:
        v = float(value) if value is not None else 0
    except (ValueError, TypeError):
        return "blue"
    if reverse:
        if v < 10:
            return "green"
        if v < 20:
            return "yellow"
        return "red"
    if v > 20:
        return "green"
    if v > 0:
        return "yellow"
    return "red"


def _format_pct(value: Any) -> str:
    try:
        v = float(value) if value is not None else 0
    except (ValueError, TypeError):
        return "-"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def _render_metric_group(title: str, metrics: List[tuple]) -> str:
    rows = ""
    for label, value, suffix in metrics:
        val_str = "-"
        if value is not None:
            try:
                if isinstance(value, float):
                    val_str = f"{value:.2f}"
                else:
                    val_str = str(value)
            except (ValueError, TypeError):
                val_str = str(value)
        rows += f'<div class="metric-row"><span class="label-col">{label}</span><span class="value-col">{val_str}{suffix}</span></div>'
    return f"""<div class="metric-group">
    <h3>{title}</h3>
    {rows}
</div>"""
