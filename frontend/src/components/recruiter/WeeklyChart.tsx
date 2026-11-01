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

const AXIS = { fontSize: 11, fill: "#5A6270", fontFamily: "JetBrains Mono, monospace" };

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
      <div className="mb-1 flex items-baseline justify-between">
        <figcaption className="text-sm font-medium">Applications this week</figcaption>
        <span className="font-mono text-sm">{total}</span>
      </div>
      <div className="h-[140px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -24 }}>
            <CartesianGrid stroke="#E3E6EB" strokeDasharray="0" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={dayLabel}
              tick={AXIS}
              tickLine={false}
              axisLine={{ stroke: "#E3E6EB" }}
            />
            <YAxis
              allowDecimals={false}
              domain={[0, top]}
              ticks={ticks}
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <Tooltip
              labelFormatter={(v) => dayLabel(String(v))}
              formatter={(v) => [v, "Applications"]}
              contentStyle={{
                border: "1px solid #E3E6EB",
                borderRadius: 6,
                fontSize: 12,
                boxShadow: "none",
              }}
            />
            <Line
              type="linear"
              dataKey="count"
              stroke="#0F766E"
              strokeWidth={1.5}
              dot={{ r: 2, fill: "#0F766E", strokeWidth: 0 }}
              activeDot={{ r: 3 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
