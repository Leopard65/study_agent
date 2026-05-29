interface BarSegment {
  value: number;
  color: string;
}

interface MiniBarChartProps {
  /** 每个数据点的日期标签 */
  dates: string[];
  /** 每个数据点的柱子配置（支持堆叠多段） */
  bars: BarSegment[][];
  /** 最大值（用于计算高度百分比） */
  max: number;
  /** 图例配置 */
  legends: { label: string; color: string }[];
  /** 每个数据点的 tooltip 文本 */
  tooltips?: string[];
}

export default function MiniBarChart({ dates, bars, max, legends, tooltips }: MiniBarChartProps) {
  return (
    <div>
      <div className="flex items-end gap-1" style={{ height: 60 }}>
        {dates.map((date, i) => {
          const segments = bars[i] || [];
          return (
            <div
              key={date}
              className="flex-1 flex flex-col items-center"
              title={tooltips?.[i] ?? date}
            >
              <div className="w-full flex flex-col justify-end" style={{ height: 50 }}>
                {segments.map((seg, j) => {
                  const h = max > 0 ? (seg.value / max) * 100 : 0;
                  return (
                    <div
                      key={j}
                      className={j === segments.length - 1 ? 'w-full rounded-t' : 'w-full'}
                      style={{ height: `${h}%`, background: seg.color }}
                    />
                  );
                })}
              </div>
              <div className="text-[9px] text-gray-400 mt-0.5">{date.slice(5)}</div>
            </div>
          );
        })}
      </div>
      {legends.length > 0 && (
        <div className="flex gap-3 mt-1 text-[10px] text-gray-400">
          {legends.map(l => (
            <span key={l.label} className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-sm inline-block" style={{ backgroundColor: l.color }} />
              {l.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
