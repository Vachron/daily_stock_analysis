import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TaskPanel } from '../TaskPanel';
import type { TaskInfo } from '../../../types/analysis';

const baseTask: TaskInfo = {
  taskId: 'task-1',
  stockCode: '600519',
  stockName: '贵州茅台',
  status: 'processing',
  progress: 40,
  message: '正在抓取最新行情',
  reportType: 'detailed',
  createdAt: '2026-03-21T08:00:00Z',
  steps: [],
};

describe('TaskPanel', () => {
  it('renders active tasks with preserved dashboard panel styling', () => {
    const { container } = render(
      <TaskPanel
        tasks={[
          baseTask,
          {
            ...baseTask,
            taskId: 'task-2',
            stockCode: 'AAPL',
            stockName: 'Apple',
            status: 'pending',
            message: '等待分析队列',
          },
        ]}
      />,
    );

    expect(screen.getByText('分析任务')).toBeInTheDocument();
    expect(screen.getByText('1 进行中')).toBeInTheDocument();
    expect(screen.getByText('1 等待中')).toBeInTheDocument();
    expect(screen.getByText('贵州茅台')).toBeInTheDocument();
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByLabelText('任务状态：分析中')).toBeInTheDocument();
    expect(container.querySelector('.home-panel-card')).toBeTruthy();
    expect(container.querySelector('.home-subpanel')).toBeTruthy();
  });

  it('does not render when there are no active tasks', () => {
    const { container } = render(
      <TaskPanel
        tasks={[
          {
            ...baseTask,
            status: 'completed',
          },
        ]}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('renders analysis steps for processing tasks', () => {
    const taskWithSteps: TaskInfo = {
      ...baseTask,
      steps: [
        { stage: 'data_fetch', label: '数据获取', message: '正在获取数据', status: 'done', timestamp: '2026-03-21T08:00:01Z', detail: '数据源: tushare' },
        { stage: 'realtime_quote', label: '实时行情', message: '获取实时行情', status: 'active', timestamp: '2026-03-21T08:00:02Z' },
      ],
    };

    render(<TaskPanel tasks={[taskWithSteps]} />);

    expect(screen.getByText('数据获取')).toBeInTheDocument();
    expect(screen.getByText('实时行情')).toBeInTheDocument();
    expect(screen.getByText('· 数据源: tushare')).toBeInTheDocument();
  });
});
