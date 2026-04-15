import { memo, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, GripVertical, Search, X } from "lucide-react";
import ComponentLinkMenu from "./ComponentLinkMenu";
import SymbolSearchModal from "./SymbolSearchModal";
import { linkBus } from "../lib/link-bus";
import {
  useOptionsChain,
  useOptionsSummary,
  type OptionsChainRow,
  type OptionSide,
} from "../lib/use-options-data";
import { useOptionsAnalytics } from "../lib/use-options-analytics";

// ── Helpers ────────────────────────────────────────────────────────────────────

function fp(v: number | null | undefined, d = 2): string {
  if (v == null) return "—";
  return v.toFixed(d);
}

function fIv(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function fSign(v: number | null | undefined, d = 2): string {
  if (v == null) return "—";
  const s = (v * 100).toFixed(d);
  return `±${s}%`;
}

function fDte(v: number | null | undefined, d = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toFixed(d);
}

/** Nearest ATM row */
function atmRow(rows: OptionsChainRow[], spot: number): OptionsChainRow | null {
  if (!rows.length) return null;
  return rows.reduce((best, r) =>
    Math.abs(r.strike - spot) < Math.abs(best.strike - spot) ? r : best,
  rows[0]);
}

function mid(side: OptionSide | null): number | null {
  if (!side) return null;
  if (side.bid != null && side.ask != null) return (side.bid + side.ask) / 2;
  return side.bid ?? side.ask ?? null;
}

// ── Props ──────────────────────────────────────────────────────────────────────

interface OptionsSnapshotCardProps {
  linkChannel: number | null;
  onSetLinkChannel: (channel: number | null) => void;
  onClose: () => void;
  config: Record<string, unknown>;
  onConfigChange: (config: Record<string, unknown>) => void;
}

// ── Stat tile ──────────────────────────────────────────────────────────────────

interface StatTileProps {
  label: string;
  value: string;
  sub?: string;
  color?: string;
  accentBorder?: string;
  wide?: boolean;
}

function StatTile({ label, value, sub, color = "text-white/90", accentBorder }: StatTileProps) {
  return (
    <div
      className="flex min-w-0 flex-col justify-between border border-white/[0.06] px-2.5 py-2"
      style={{
        backgroundColor: "#161B22",
        borderRadius: 4,
        borderLeft: accentBorder ? `2px solid ${accentBorder}` : undefined,
      }}
    >
      <span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-white">
        {label}
      </span>
      <span className={`mt-1 font-mono text-[13px] font-semibold tabular-nums ${color}`}>
        {value}
      </span>
      {sub && (
        <span className="mt-0.5 font-mono text-[9px] text-white/35 tabular-nums">{sub}</span>
      )}
    </div>
  );
}

// ── Expiry pill row ────────────────────────────────────────────────────────────

interface ExpiryPickerProps {
  months: { monthLabel: string; expirations: { expiration: number; label: string }[] }[];
  selected: number | null;
  onSelect: (exp: number) => void;
}

function ExpiryPicker({ months, selected, onSelect }: ExpiryPickerProps) {
  const allExps = useMemo(
    () => months.flatMap((m) => m.expirations),
    [months],
  );

  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const selectedLabel =
    allExps.find((e) => e.expiration === selected)?.label ?? "Select expiry";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex h-5 items-center gap-1 border border-white/[0.10] bg-[#1C2128] px-2 text-[10px] text-white/70 transition-colors duration-75 hover:border-white/20 hover:text-white/90"
        style={{ borderRadius: 4 }}
      >
        <span className="font-mono">{selectedLabel}</span>
        <ChevronDown className="h-2.5 w-2.5 shrink-0 text-white/40" strokeWidth={2} />
      </button>

      {open && (
        <div
          className="absolute left-0 top-full z-[200] mt-1 max-h-52 w-56 overflow-y-auto border border-white/[0.10] bg-[#1C2128] py-1 shadow-xl shadow-black/40 [&::-webkit-scrollbar]:hidden"
          style={{ borderRadius: 4, scrollbarWidth: "none" }}
        >
          {months.map((month) => (
            <div key={month.monthLabel}>
              <div className="px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-white/35">
                {month.monthLabel}
              </div>
              {month.expirations.map((exp) => (
                <button
                  key={exp.expiration}
                  onClick={() => { onSelect(exp.expiration); setOpen(false); }}
                  className={`flex w-full items-center px-2.5 py-1 text-left font-mono text-[10px] transition-colors duration-75 ${
                    exp.expiration === selected
                      ? "bg-[#1A56DB]/20 text-[#1A56DB]"
                      : "text-white/70 hover:bg-white/[0.04] hover:text-white/90"
                  }`}
                >
                  {exp.label}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

function OptionsSnapshotCard({
  linkChannel,
  onSetLinkChannel,
  onClose,
  config,
  onConfigChange,
}: OptionsSnapshotCardProps) {
  const symbol =
    typeof config.symbol === "string" ? config.symbol.trim().toUpperCase() : "";
  const configuredExpiry =
    typeof config.expiration === "number" ? config.expiration : null;

  const [searchOpen, setSearchOpen] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  // Link channel subscription
  useEffect(() => {
    if (!linkChannel) return;
    return linkBus.subscribe(linkChannel, (sym) => {
      onConfigChange({ ...config, symbol: sym });
    });
  }, [linkChannel, config, onConfigChange]);

  const { summary } = useOptionsSummary(symbol);
  const spot = summary?.underlyingPrice ?? null;

  // Flatten all expirations; default to the nearest one
  const allExps = useMemo(
    () => (summary?.months ?? []).flatMap((m) => m.expirations),
    [summary?.months],
  );

  const nearestExp = allExps[0]?.expiration ?? null;
  const selectedExpiry = configuredExpiry ?? nearestExp;

  const { chain } = useOptionsChain(symbol, selectedExpiry);
  const analytics = useOptionsAnalytics(chain ?? null, null, spot);

  // ── Derived metrics ──────────────────────────────────────────────────────────

  const atm = useMemo(() => {
    if (!chain?.rows.length || spot == null) return null;
    return atmRow(chain.rows, spot);
  }, [chain?.rows, spot]);

  const atmCallMid = mid(atm?.call ?? null);
  const atmPutMid  = mid(atm?.put  ?? null);
  const straddlePrice =
    atmCallMid != null && atmPutMid != null ? atmCallMid + atmPutMid : null;

  const atmIv =
    atm?.call?.impliedVolatility ?? atm?.put?.impliedVolatility ?? null;

  const dte =
    atm?.call?.daysToExpiration ?? atm?.put?.daysToExpiration ?? null;

  // Put/Call OI ratio across the whole chain
  const pcRatio = useMemo(() => {
    const rows = chain?.rows ?? [];
    let totalCallOI = 0;
    let totalPutOI  = 0;
    for (const r of rows) {
      totalCallOI += r.call?.openInterest ?? 0;
      totalPutOI  += r.put?.openInterest  ?? 0;
    }
    if (totalCallOI === 0) return null;
    return totalPutOI / totalCallOI;
  }, [chain?.rows]);

  // Max pain: strike with highest combined OI loss for option buyers
  const maxPain = useMemo(() => {
    const rows = chain?.rows ?? [];
    if (!rows.length) return null;
    let bestStrike: number | null = null;
    let bestLoss = Infinity;
    for (const target of rows) {
      let totalLoss = 0;
      for (const r of rows) {
        const callLoss = Math.max(0, r.strike - target.strike) * (r.call?.openInterest ?? 0);
        const putLoss  = Math.max(0, target.strike - r.strike) * (r.put?.openInterest  ?? 0);
        totalLoss += callLoss + putLoss;
      }
      if (totalLoss < bestLoss) {
        bestLoss = totalLoss;
        bestStrike = target.strike;
      }
    }
    return bestStrike;
  }, [chain?.rows]);

  // ── UI state ─────────────────────────────────────────────────────────────────

  const commitSymbol = (sym: string) => {
    onConfigChange({ ...config, symbol: sym, expiration: null });
    if (linkChannel) linkBus.publish(linkChannel, sym);
  };

  const commitExpiry = (exp: number) => {
    onConfigChange({ ...config, expiration: exp });
  };

  const hasData = !!symbol && spot != null;

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-full flex-col overflow-hidden border border-white/[0.06] bg-[#161B22]">
      {/* Header */}
      <div
        className="flex h-8 shrink-0 items-center justify-between gap-1 border-b border-white/[0.06] bg-[#0D1117] px-2"
        data-drag-handle
      >
        <div className="flex min-w-0 items-center gap-1.5">
          <GripVertical
            className="h-3 w-3 shrink-0 cursor-grab text-white/20 active:cursor-grabbing"
            strokeWidth={2}
          />
          <button
            onClick={() => setSearchOpen((v) => !v)}
            className="flex h-5 min-w-0 items-center gap-1 border border-white/[0.08] bg-[#1C2128] px-1.5 text-left transition-colors duration-75 hover:border-white/15"
            style={{ borderRadius: 4 }}
          >
            <Search className="h-2.5 w-2.5 shrink-0 text-white/35" strokeWidth={2} />
            <span className="truncate font-mono text-[10px] font-semibold tracking-wide text-white/80">
              {symbol || "Symbol…"}
            </span>
          </button>
          <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-white/25">
            Options Snapshot
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <ComponentLinkMenu linkChannel={linkChannel} onSetLinkChannel={onSetLinkChannel} />
          <button
            onClick={onClose}
            className="flex h-5 w-5 items-center justify-center text-white/25 transition-colors duration-75 hover:text-white/60"
          >
            <X className="h-3 w-3" strokeWidth={2} />
          </button>
        </div>
      </div>

      {/* No symbol empty state */}
      {!symbol && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2">
          <span className="text-[10px] text-white/20">No symbol selected</span>
          <button
            onClick={() => setSearchOpen(true)}
            className="border border-white/[0.10] bg-[#1C2128] px-3 py-1.5 text-[10px] text-white/50 transition-colors duration-75 hover:text-white/80"
            style={{ borderRadius: 4 }}
          >
            Search symbol
          </button>
        </div>
      )}

      {/* Body */}
      {symbol && (
        <div ref={bodyRef} className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2 [&::-webkit-scrollbar]:hidden" style={{ scrollbarWidth: "none" }}>
          {/* Expiry selector + spot */}
          <div className="flex items-center justify-between gap-2">
            {allExps.length > 0 ? (
              <ExpiryPicker
                months={summary?.months ?? []}
                selected={selectedExpiry}
                onSelect={commitExpiry}
              />
            ) : (
              <span className="font-mono text-[10px] text-white/25">No expirations</span>
            )}
            <span className="font-mono text-[11px] tabular-nums text-[#00C853]/90">
              {spot != null ? `$${fp(spot)}` : "—"}
            </span>
          </div>

          {/* Implied move — hero stat */}
          {analytics.impliedMoveToExpiry != null && (
            <div
              className="flex items-center justify-between border border-[#8B5CF6]/20 bg-[#8B5CF6]/[0.06] px-3 py-2.5"
              style={{ borderRadius: 4 }}
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-white">
                  Impl. Move to Exp
                </span>
                {dte != null && (
                  <span className="text-[9px] text-white/30 font-mono">{fDte(dte)}d remaining</span>
                )}
              </div>
              <span className="font-mono text-[20px] font-semibold tabular-nums text-[#8B5CF6]">
                {fSign(analytics.impliedMoveToExpiry)}
              </span>
            </div>
          )}

          {/* 2-col stat grid */}
          <div className="grid grid-cols-2 gap-1.5">
            {/* Support */}
            <StatTile
              label="Support"
              value={analytics.support != null ? `$${fp(analytics.support)}` : "—"}
              sub={
                analytics.support != null && spot != null
                  ? `${(((analytics.support - spot) / spot) * 100).toFixed(1)}% away`
                  : undefined
              }
              color={analytics.support != null ? "text-[#00C853]" : "text-white/20"}
              accentBorder={analytics.support != null ? "#00C853" : undefined}
            />

            {/* Resistance */}
            <StatTile
              label="Resistance"
              value={analytics.resistance != null ? `$${fp(analytics.resistance)}` : "—"}
              sub={
                analytics.resistance != null && spot != null
                  ? `+${(((analytics.resistance - spot) / spot) * 100).toFixed(1)}% away`
                  : undefined
              }
              color={analytics.resistance != null ? "text-[#FF3D71]" : "text-white/20"}
              accentBorder={analytics.resistance != null ? "#FF3D71" : undefined}
            />

            {/* ATM IV */}
            <StatTile
              label="ATM IV"
              value={fIv(atmIv)}
              color={
                atmIv == null
                  ? "text-white/20"
                  : atmIv >= 0.5
                    ? "text-[#F59E0B]"
                    : "text-white/80"
              }
            />

            {/* Straddle */}
            <StatTile
              label="ATM Straddle"
              value={straddlePrice != null ? `$${fp(straddlePrice)}` : "—"}
              sub={
                straddlePrice != null && spot != null
                  ? `${((straddlePrice / spot) * 100).toFixed(2)}% of spot`
                  : undefined
              }
              color="text-[#8B5CF6]/80"
            />

            {/* Put/Call ratio */}
            <StatTile
              label="P/C OI Ratio"
              value={pcRatio != null ? pcRatio.toFixed(2) : "—"}
              sub={
                pcRatio != null
                  ? pcRatio > 1.2
                    ? "bearish lean"
                    : pcRatio < 0.8
                      ? "bullish lean"
                      : "neutral"
                  : undefined
              }
              color={
                pcRatio == null
                  ? "text-white/20"
                  : pcRatio > 1.2
                    ? "text-[#FF3D71]"
                    : pcRatio < 0.8
                      ? "text-[#00C853]"
                      : "text-[#F59E0B]"
              }
            />

            {/* Max pain */}
            <StatTile
              label="Max Pain"
              value={maxPain != null ? `$${fp(maxPain)}` : "—"}
              sub={
                maxPain != null && spot != null
                  ? `${((maxPain - spot) / spot >= 0 ? "+" : "")}${(((maxPain - spot) / spot) * 100).toFixed(1)}% vs spot`
                  : undefined
              }
              color="text-[#F59E0B]"
            />

            {/* Best covered call */}
            {analytics.bestCoveredCall != null && (
              <StatTile
                label="Best Cov. Call"
                value={`$${fp(analytics.bestCoveredCall)}`}
                sub="highest scored CC strike"
                color="text-[#F59E0B]"
                accentBorder="#F59E0B"
              />
            )}

            {/* DTE */}
            <StatTile
              label="DTE"
              value={fDte(dte)}
              sub={dte != null ? "days to expiry" : undefined}
              color="text-white/70"
            />
          </div>

          {/* No data notice */}
          {!hasData && symbol && (
            <div className="flex flex-1 items-center justify-center">
              <span className="text-[10px] text-white/20">Fetching options data…</span>
            </div>
          )}
        </div>
      )}

      {/* Symbol search modal */}
      <SymbolSearchModal
        isOpen={searchOpen}
        onClose={() => setSearchOpen(false)}
        onSelectSymbol={(sym: string) => {
          commitSymbol(sym);
          setSearchOpen(false);
        }}
      />
    </div>
  );
}

export default memo(OptionsSnapshotCard);
