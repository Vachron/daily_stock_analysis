import { Download } from 'lucide-react';

interface BacktestReportExportProps {
  onExport: () => void;
  loading?: boolean;
  disabled?: boolean;
}

export function BacktestReportExport({ onExport, loading, disabled }: BacktestReportExportProps) {
  return (
    <button
      type="button"
      onClick={onExport}
      disabled={disabled || loading}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan/10 border border-cyan/20 text-cyan text-[11px] hover:bg-cyan/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {loading ? (
        <span className="flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          生成中...
        </span>
      ) : (
        <><Download className="h-3.5 w-3.5" />下载 HTML 报告</>
      )}
    </button>
  );
}
