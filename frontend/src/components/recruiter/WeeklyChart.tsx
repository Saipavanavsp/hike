import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DayCount } from "@/api/types";
import { CHART } from "./chartTheme";

function dayLabel(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
  });
}

/** "Applications this week": one 1.5px line, no fill, light gridlines. */
export function WeeklyChart({ data }: { data: DayCount[] }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  // Even integer ticks: 0, half, max (max rounded up to an even number, at least 4).
  const peak = Math.max(4, ...data.map((d) => d.count));
  const top = peak % 2 === 0 ? peak : peak + 1;
  const ticks = [0, top / 2, top];
  return (
    <figure aria-label={`Applications this week: ${total} in total`}>
      <div className="mb-3 flex items-baseline justify-between">
        <figcaption className="text-sm font-medium text-ink">Applications this week</figcaption>
        <span className="text-2xl font-semibold tabular text-ink">{total}</span>
      </div>
      <div className="h-[140px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -24 }}>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="0" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={dayLabel}
              tick={CHART.axis}
              tickLine={false}
              axisLine={{ stroke: CHART.grid }}
            />
            <YAxis
              allowDecimals={false}
              domain={[0, top]}
              ticks={ticks}
              tick={CHART.axis}
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <Tooltip
              labelFormatter={(v) => dayLabel(String(v))}
              formatter={(v) => [v, "Applications"]}
              contentStyle={CHART.tooltip}
              labelStyle={CHART.tooltipLabel}
              itemStyle={CHART.tooltipItem}
              cursor={{ stroke: CHART.grid }}
            />
            <Line
              type="linear"
              dataKey="count"
              stroke={CHART.series}
              strokeWidth={2}
              dot={{ r: 2.5, fill: CHART.series, strokeWidth: 0 }}
              activeDot={{ r: 4, fill: CHART.series, strokeWidth: 0 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
