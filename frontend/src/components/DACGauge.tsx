"use client";

interface Props {
  score: number;
  ttrHours: number;
  volumeSurge: number;
}

export default function DACGauge({ score, ttrHours, volumeSurge }: Props) {
  const percentage = Math.min(score * 100, 100);
  const color =
    score >= 0.1
      ? "text-accent-green"
      : score >= 0.03
        ? "text-accent-yellow"
        : "text-gray-500";

  const barColor =
    score >= 0.1
      ? "bg-accent-green"
      : score >= 0.03
        ? "bg-accent-yellow"
        : "bg-gray-600";

  const label = score >= 0.1 ? "ALPHA" : score >= 0.03 ? "WATCH" : "NOISE";

  return (
    <div className="rounded-lg border border-surface-300 bg-surface-50 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-400">DAC Score</span>
        <span className={`text-xs font-bold ${color}`}>{label}</span>
      </div>

      <div className="mt-2 flex items-end gap-1">
        <span className={`font-mono text-2xl font-bold ${color}`}>
          {score.toFixed(4)}
        </span>
      </div>

      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-300">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-gray-500">TTR</span>
          <span className="ml-1 font-mono">{ttrHours.toFixed(1)}h</span>
        </div>
        <div>
          <span className="text-gray-500">Vol Surge</span>
          <span className="ml-1 font-mono">{volumeSurge.toFixed(2)}x</span>
        </div>
      </div>
    </div>
  );
}
