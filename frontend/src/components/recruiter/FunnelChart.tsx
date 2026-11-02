import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { FunnelStep } from "@/api/types";
import { STATUS_LABELS } from "@/lib/format";

const AXIS = { fontSize: 11, fill: "#5A6270", fontFamily: "JetBrains Mono, monospace" };
const LABEL = { fontSize: 12, fill: "#1A1D21", fontFamily: "JetBrains Mono, monospace" };

function pct(x: number | null): string {
  return x === null ? "" : `${Math.round(x * 100)}%`;
}

/**
 * Hiring funnel: one series (applications that reached each stage), so one hue and no
 * legend. Bars are direct-labelled with the count; the table below repeats every number,
 * including stage-to-stage conversion, for screen readers and exact reading.
 */
export function FunnelChart({ funnel }: { funnel: FunnelStep[] }) {
  const data = funnel.map((f) => ({ ...f, label: STATUS_LABELS[f.stage] }));
  // Evenly spaced integer ticks: 0, half, top (top rounded up to an even number, at least 4).
  const peak = Math.max(4, ...data.map((d) => d.count));
  const max = peak % 2 === 0 ? peak : peak + 1;
  const ticks = [0, max / 2, max];
  return (
    <figure aria-label="Hiring funnel">
      <figcaption className="mb-1 text-sm font-medium">
        Applications that reached each stage
      </figcaption>
      <div className="h-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 40, bottom: 0, left: 0 }}
            barCategoryGap={8}
          >
            <CartesianGrid stroke="#E3E6EB" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, max]}
              ticks={ticks}
              allowDecimals={false}
              tick={AXIS}
              tickLine={false}
              axisLine={{ stroke: "#E3E6EB" }}
            />
            <YAxis
              type="category"
              dataKey="label"
              tick={{ ...AXIS, fontFamily: "IBM Plex Sans, sans-serif", fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={84}
            />
            <Tooltip
              cursor={{ fill: "#F7F8FA" }}
              formatter={(v, _n, item) => {
                const conv = (item.payload as FunnelStep).conversion_from_previous;
                return [conv === null ? v : `${v} (${pct(conv)} of previous stage)`, "Reached"];
              }}
              contentStyle={{
                border: "1px solid #E3E6EB",
                borderRadius: 6,
                fontSize: 12,
                boxShadow: "none",
              }}
            />
            <Bar
              dataKey="count"
              fill="#0F766E"
              barSize={18}
              radius={[0, 4, 4, 0]}
              isAnimationActive={false}
            >
              <LabelList dataKey="count" position="right" style={LABEL} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="mt-2 w-full text-xs">
        <caption className="sr-only">Funnel values</caption>
        <thead>
          <tr className="text-left text-ink-secondary">
            <th className="py-1 font-normal">Stage</th>
            <th className="py-1 text-right font-normal">Reached</th>
            <th className="py-1 text-right font-normal">From previous stage</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.stage} className="border-t border-border">
              <td className="py-1">{d.label}</td>
              <td className="py-1 text-right font-mono">{d.count}</td>
              <td className="py-1 text-right font-mono">
                {d.conversion_from_previous === null ? "--" : pct(d.conversion_from_previous)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
