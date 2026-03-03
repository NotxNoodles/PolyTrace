"use client";

import { useEffect, useState, useRef } from "react";
import type { SmartMoneyAlert } from "@/types";
import { getSmartMoneyFeed } from "@/lib/api";

const TYPE_COLORS: Record<string, string> = {
  sniper: "text-accent-red",
  specialist: "text-accent-purple",
  one_hit: "text-accent-yellow",
};

const TYPE_LABELS: Record<string, string> = {
  sniper: "SNP",
  specialist: "SPC",
  one_hit: "OHW",
};

interface Props {
  pollInterval?: number;
}

export default function SmartMoneyTicker({ pollInterval = 15000 }: Props) {
  const [items, setItems] = useState<SmartMoneyAlert[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;

    async function poll() {
      try {
        const data = await getSmartMoneyFeed(15);
        if (active) setItems(data);
      } catch {
        // silently retry on next interval
      }
    }

    poll();
    const id = setInterval(poll, pollInterval);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [pollInterval]);

  if (items.length === 0) {
    return (
      <div className="flex h-10 items-center justify-center text-xs text-gray-600">
        Waiting for smart money activity...
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden border-b border-t border-surface-300 bg-surface-50">
      <div
        ref={scrollRef}
        className="flex animate-[scroll_60s_linear_infinite] items-center gap-6 whitespace-nowrap py-2"
      >
        {[...items, ...items].map((a, i) => (
          <div key={`${a.id}-${i}`} className="flex items-center gap-2 px-2">
            <span
              className={`font-mono text-[10px] font-bold uppercase ${
                TYPE_COLORS[a.type] || "text-gray-400"
              }`}
            >
              {TYPE_LABELS[a.type] || a.type}
            </span>
            <span className="text-xs text-gray-300 max-w-[160px] truncate">
              {a.market || a.wallet.slice(0, 8)}
            </span>
            <span className="font-mono text-xs text-accent-green">
              ${a.usdc_volume?.toLocaleString()}
            </span>
            <span className="font-mono text-[10px] text-gray-600">
              {timeSince(a.timestamp)}
            </span>
          </div>
        ))}
      </div>

      <style jsx>{`
        @keyframes scroll {
          from {
            transform: translateX(0);
          }
          to {
            transform: translateX(-50%);
          }
        }
      `}</style>
    </div>
  );
}

function timeSince(isoString: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(isoString).getTime()) / 1000
  );
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
