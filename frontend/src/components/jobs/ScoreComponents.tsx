import type { ScoreComponent } from "@/api/types";

/**
 * Every part of the match score: points earned out of its weight, with the reason.
 * A thin single-hue bar shows the share of the weight earned; the numbers carry the meaning.
 */
export function ScoreComponents({
  components,
  score,
}: {
  components: ScoreComponent[];
  score: number;
}) {
  if (!components.length) return null;
  return (
    <div>
      <table className="w-full text-sm" aria-label="How the score is calculated">
        <thead className="sr-only">
          <tr>
            <th>Part</th>
            <th>Points</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {components.map((c) => (
            <tr key={c.key} className="align-top">
              <td className="py-1 pr-3">
                <span>{c.label}</span>
                <span className="mt-1 block h-1 w-full rounded-sm bg-border" aria-hidden="true">
                  <span
                    className="block h-1 rounded-sm bg-accent"
                    style={{ width: `${(c.points / c.weight) * 100}%` }}
                  />
                </span>
                <span className="mt-0.5 block text-xs text-ink-secondary">{c.detail}</span>
              </td>
              <td className="whitespace-nowrap py-1 text-right tabular text-xs leading-5">
                {c.points.toFixed(1)} / {c.weight}
              </td>
            </tr>
          ))}
          <tr className="border-t border-border">
            <td className="pt-1.5 font-medium">Match score</td>
            <td className="pt-1.5 text-right tabular text-xs font-medium leading-5">
              {score} / 100
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
