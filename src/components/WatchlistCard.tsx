import { useState, useRef, useCallback, useEffect } from "react";
import { X } from "lucide-react";
import ComponentLinkMenu from "./ComponentLinkMenu";
import { getChannelById } from "../lib/link-channels";
import { getQuote, getSymbolName, ALL_SYMBOLS } from "../lib/market-data";

// ─── Column definitions ────────────────────────────────────────────
interface ColDef {
  key: string;
  label: string;
  defaultWidth: number;
  minWidth: number;
  align: "left" | "right";
}

const COLUMNS: ColDef[] = [
  { key: "symbol", label: "Symbol", defaultWidth: 72, minWidth: 50, align: "left" },
  { key: "last", label: "Last", defaultWidth: 68, minWidth: 44, align: "right" },
  { key: "change", label: "Chg", defaultWidth: 58, minWidth: 40, align: "right" },
  { key: "changePct", label: "Chg%", defaultWidth: 58, minWidth: 42, align: "right" },
];

const ROW_H = 24;
const HEADER_H = 22;

// ─── Helpers ────────────────────────────────────────────────────────
function changeColor(v: number): string {
  if (v > 0) return "text-green";
  if (v < 0) return "text-red";
  return "text-white/40";
}

function changeBg(v: number): string {
  if (v > 0) return "bg-green/[0.06]";
  if (v < 0) return "bg-red/[0.06]";
  return "";
}

// ─── Context menu item classes ──────────────────────────────────────
const ctxItemClass =
  "block w-full text-left px-3 py-1.5 text-[11px] text-white/60 hover:bg-white/[0.06] hover:text-white/80 transition-colors duration-75";

// ─── Props ──────────────────────────────────────────────────────────
interface WatchlistCardProps {
  linkChannel: number | null;
  onSetLinkChannel: (channel: number | null) => void;
  onClose: () => void;
  config: Record<string, unknown>;
  onConfigChange: (config: Record<string, unknown>) => void;
  onSymbolSelect?: (symbol: string) => void;
}

export default function WatchlistCard({
  linkChannel,
  onSetLinkChannel,
  onClose,
  config,
  onConfigChange,
  onSymbolSelect,
}: WatchlistCardProps) {
  const symbols: string[] = (config.symbols as string[]) ?? [];
  const savedColWidths = config.columnWidths as number[] | undefined;
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  // ── Context menu state ──
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    globalIdx: number;
    isEmpty: boolean;
  } | null>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);

  // ── Auto-edit after insert ──
  const [editingIdx, setEditingIdx] = useState<number | null>(null);

  // ── Dismiss context menu ──
  useEffect(() => {
    if (!contextMenu) return;
    const handleClick = (e: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node))
        setContextMenu(null);
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setContextMenu(null);
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [contextMenu]);

  // ── Observe container width for multi-pane layout ──
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(([entry]) => {
      setContainerWidth(entry.contentRect.width);
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // ── Column widths (resizable) ──
  const [colWidths, setColWidths] = useState<number[]>(
    savedColWidths ?? COLUMNS.map((c) => c.defaultWidth),
  );

  // Persist column widths on change
  const persistColWidths = useCallback(
    (widths: number[]) => {
      onConfigChange({ ...config, symbols, columnWidths: widths });
    },
    [config, symbols, onConfigChange],
  );

  // ── Column resize drag ──
  const handleColResize = useCallback(
    (colIdx: number, e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const startX = e.clientX;
      const startW = colWidths[colIdx];

      const onMove = (ev: MouseEvent) => {
        const dx = ev.clientX - startX;
        const newW = Math.max(COLUMNS[colIdx].minWidth, startW + dx);
        setColWidths((prev) => {
          const next = [...prev];
          next[colIdx] = newW;
          return next;
        });
      };

      const onUp = () => {
        setColWidths((prev) => {
          persistColWidths(prev);
          return prev;
        });
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [colWidths, persistColWidths],
  );

  // ── How many panes fit side-by-side? ──
  const paneWidth = colWidths.reduce((a, b) => a + b, 0) + 8; // 8px padding
  const paneCount = Math.max(1, Math.floor(containerWidth / paneWidth));

  // ── Symbol mutations ──
  const updateSymbols = useCallback(
    (next: string[]) => {
      onConfigChange({ ...config, columnWidths: colWidths, symbols: next });
    },
    [config, colWidths, onConfigChange],
  );

  const removeSymbol = useCallback(
    (idx: number) => {
      updateSymbols(symbols.filter((_, i) => i !== idx));
    },
    [symbols, updateSymbols],
  );

  const addSymbol = useCallback(
    (sym: string) => {
      if (!sym || symbols.includes(sym)) return;
      updateSymbols([...symbols, sym]);
    },
    [symbols, updateSymbols],
  );

  const insertSymbolAt = useCallback(
    (idx: number, sym: string) => {
      const next = [...symbols];
      next.splice(idx, 0, sym);
      updateSymbols(next);
    },
    [symbols, updateSymbols],
  );

  // ── How many visible rows per pane? ──
  const bodyRef = useRef<HTMLDivElement>(null);
  const [bodyHeight, setBodyHeight] = useState(300);
  useEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    const obs = new ResizeObserver(([entry]) => {
      setBodyHeight(entry.contentRect.height);
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const rowsPerPane = Math.max(4, Math.floor((bodyHeight - HEADER_H) / ROW_H));

  // ── Include ALL symbols + at least 2 empty rows, then pad to fill visible space ──
  const minRows = symbols.length + 2;
  const totalSlots = Math.max(minRows, rowsPerPane * paneCount);
  const paddedSymbols = [
    ...symbols,
    ...Array.from({ length: Math.max(2, totalSlots - symbols.length) }, () => ""),
  ];

  // Split into panes
  const symbolsPerPane = Math.ceil(paddedSymbols.length / paneCount);
  const panes: string[][] = [];
  for (let i = 0; i < paneCount; i++) {
    panes.push(paddedSymbols.slice(i * symbolsPerPane, (i + 1) * symbolsPerPane));
  }

  const channelInfo = getChannelById(linkChannel);

  // ── Context menu actions ──
  const handleContextMenuAction = (action: "delete" | "insertAbove" | "insertBelow" | "insert") => {
    if (!contextMenu) return;
    const idx = contextMenu.globalIdx;
    switch (action) {
      case "delete":
        if (idx < symbols.length) removeSymbol(idx);
        break;
      case "insertAbove": {
        const insertIdx = Math.min(idx, symbols.length);
        insertSymbolAt(insertIdx, "");
        setEditingIdx(insertIdx);
        break;
      }
      case "insertBelow": {
        const insertIdx = Math.min(idx + 1, symbols.length + 1);
        insertSymbolAt(insertIdx, "");
        setEditingIdx(insertIdx);
        break;
      }
      case "insert": {
        const insertIdx = Math.min(idx, symbols.length);
        insertSymbolAt(insertIdx, "");
        setEditingIdx(insertIdx);
        break;
      }
    }
    setContextMenu(null);
  };

  return (
    <div
      className="flex h-full flex-col overflow-hidden border border-white/[0.06] bg-panel"
    >
      {/* Header */}
      <div className="flex h-7 shrink-0 items-center justify-between border-b border-white/[0.10] bg-base px-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-medium text-white/60">Watchlist</span>
          <span className="font-mono text-[9px] text-white/25">
            {symbols.length} symbol{symbols.length !== 1 ? "s" : ""}
          </span>
          {channelInfo && (
            <span
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: channelInfo.color }}
            />
          )}
        </div>
        <div className="flex items-center gap-0.5">
          <ComponentLinkMenu
            linkChannel={linkChannel}
            onSetLinkChannel={onSetLinkChannel}
          />
          <button
            onClick={onClose}
            className="rounded-sm p-0.5 text-white/30 transition-colors duration-75 hover:bg-white/[0.06] hover:text-red"
          >
            <X className="h-2.5 w-2.5" strokeWidth={1.5} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div ref={containerRef} className="flex flex-1 overflow-hidden">
        <div ref={bodyRef} className="flex h-full w-full">
          {panes.map((pane, paneIdx) => (
            <div
              key={paneIdx}
              className={`flex flex-1 flex-col overflow-hidden ${
                paneIdx > 0 ? "border-l border-white/[0.06]" : ""
              }`}
              style={{ minWidth: 0 }}
            >
              {/* Column headers */}
              <div
                className="flex shrink-0 items-center border-b border-white/[0.06] bg-[#0D1117]"
                style={{ height: HEADER_H }}
              >
                {COLUMNS.map((col, ci) => (
                  <div
                    key={col.key}
                    className={`relative select-none truncate px-1.5 text-[9px] font-medium uppercase tracking-wider text-white/40 ${
                      ci < COLUMNS.length - 1 ? "border-r border-white/[0.06]" : ""
                    }`}
                    style={{
                      width: colWidths[ci],
                      minWidth: col.minWidth,
                      textAlign: col.align,
                    }}
                  >
                    {col.label}
                    {/* Resize handle — overlaps the column border */}
                    <div
                      className="absolute -right-1 top-0 z-10 h-full w-2 cursor-col-resize hover:bg-blue/[0.15]"
                      onMouseDown={(e) => handleColResize(ci, e)}
                    />
                  </div>
                ))}
              </div>

              {/* Rows */}
              <div className="flex-1 overflow-y-auto">
                {pane.map((sym, rowIdx) => {
                  const globalIdx = paneIdx * symbolsPerPane + rowIdx;
                  return (
                    <WatchlistRow
                      key={`${paneIdx}-${rowIdx}`}
                      symbol={sym}
                      colWidths={colWidths}
                      globalIdx={globalIdx}
                      rowIdx={rowIdx}
                      onAdd={addSymbol}
                      onRemove={() => removeSymbol(globalIdx)}
                      onSymbolSelect={onSymbolSelect}
                      forceEdit={editingIdx === globalIdx}
                      onForceEditConsumed={() => setEditingIdx(null)}
                      onContextMenu={(x, y) =>
                        setContextMenu({
                          x,
                          y,
                          globalIdx,
                          isEmpty: !sym,
                        })
                      }
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div
          ref={contextMenuRef}
          className="fixed z-[100] min-w-[140px] rounded-md border border-white/[0.08] bg-[#1C2128] py-1 shadow-xl shadow-black/40"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          {contextMenu.isEmpty ? (
            <button className={ctxItemClass} onClick={() => handleContextMenuAction("insert")}>
              Insert Row
            </button>
          ) : (
            <>
              <button className={ctxItemClass} onClick={() => handleContextMenuAction("delete")}>
                Delete Row
              </button>
              <button className={ctxItemClass} onClick={() => handleContextMenuAction("insertAbove")}>
                Insert Row Above
              </button>
              <button className={ctxItemClass} onClick={() => handleContextMenuAction("insertBelow")}>
                Insert Row Below
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Row component ──────────────────────────────────────────────────
interface WatchlistRowProps {
  symbol: string;
  colWidths: number[];
  globalIdx: number;
  rowIdx: number;
  onAdd: (sym: string) => void;
  onRemove: () => void;
  onSymbolSelect?: (symbol: string) => void;
  forceEdit: boolean;
  onForceEditConsumed: () => void;
  onContextMenu: (x: number, y: number) => void;
}

function WatchlistRow({
  symbol,
  colWidths,
  rowIdx,
  onAdd,
  onRemove,
  onSymbolSelect,
  forceEdit,
  onForceEditConsumed,
  onContextMenu,
}: WatchlistRowProps) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [hovered, setHovered] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const rowRef = useRef<HTMLDivElement>(null);

  const quote = symbol ? getQuote(symbol) : null;
  const name = symbol ? getSymbolName(symbol) : "";

  // Focus input when editing
  useEffect(() => {
    if (editing && inputRef.current) inputRef.current.focus();
  }, [editing]);

  // Auto-enter edit mode when forceEdit is set on an empty row
  useEffect(() => {
    if (forceEdit && !symbol) {
      setEditing(true);
      onForceEditConsumed();
    }
  }, [forceEdit, symbol, onForceEditConsumed]);

  // Filter suggestions
  const q = editValue.toLowerCase();
  const suggestions = editValue
    ? ALL_SYMBOLS.filter(
        (s) =>
          s.symbol.toLowerCase().includes(q) ||
          s.name.toLowerCase().includes(q),
      ).slice(0, 6)
    : [];

  const commitSymbol = (sym: string) => {
    const upper = sym.trim().toUpperCase();
    if (upper) onAdd(upper);
    setEditing(false);
    setEditValue("");
    setShowSuggestions(false);
  };

  const handleRowContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    onContextMenu(e.clientX, e.clientY);
  };

  // Zebra striping: even rows panel bg, odd rows base/80
  const zebraClass = rowIdx % 2 === 0 ? "bg-panel" : "bg-base/80";

  // Empty row — click to type
  if (!symbol) {
    return (
      <div
        className={`flex items-center border-b border-white/[0.03] ${zebraClass} hover:bg-white/[0.05]`}
        style={{ height: ROW_H }}
        onContextMenu={handleRowContextMenu}
      >
        {editing ? (
          <div className="relative flex-1 px-1">
            <input
              ref={inputRef}
              value={editValue}
              onChange={(e) => {
                setEditValue(e.target.value);
                setShowSuggestions(true);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  const sym = suggestions.length > 0 ? suggestions[0].symbol : editValue;
                  commitSymbol(sym);
                }
                if (e.key === "Escape") {
                  setEditing(false);
                  setEditValue("");
                  setShowSuggestions(false);
                }
              }}
              onBlur={() => {
                // Delay to allow click on suggestion
                setTimeout(() => {
                  setEditing(false);
                  setEditValue("");
                  setShowSuggestions(false);
                }, 150);
              }}
              placeholder="Type symbol..."
              className="w-full bg-transparent font-mono text-[10px] text-white/70 placeholder:text-white/15 focus:outline-none"
            />
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute left-0 top-full z-[130] mt-0.5 w-[200px] rounded-md border border-white/[0.08] bg-[#1C2128] py-0.5 shadow-xl shadow-black/40">
                {suggestions.map((s) => (
                  <button
                    key={s.symbol}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      commitSymbol(s.symbol);
                    }}
                    className="flex w-full items-center gap-2 px-2 py-1 text-left transition-colors duration-75 hover:bg-white/[0.06]"
                  >
                    <span className="w-12 shrink-0 font-mono text-[10px] font-medium text-white/70">
                      {s.symbol}
                    </span>
                    <span className="truncate text-[9px] text-white/30">
                      {s.name}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <button
            onClick={() => setEditing(true)}
            className="flex h-full flex-1 items-center px-1.5"
          >
            <span className="text-[10px] text-white/10">+</span>
          </button>
        )}
      </div>
    );
  }

  // Populated row
  return (
    <div
      ref={rowRef}
      className={`group relative flex items-center border-b border-white/[0.03] transition-colors duration-75 hover:bg-white/[0.05] focus:bg-white/[0.04] focus:outline-none ${
        quote && quote.change !== 0 ? changeBg(quote.change) : zebraClass
      }`}
      style={{ height: ROW_H }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onSymbolSelect?.(symbol)}
      onContextMenu={handleRowContextMenu}
      onKeyDown={(e) => {
        if (e.key === "Delete" || e.key === "Backspace") {
          e.preventDefault();
          onRemove();
        }
      }}
      tabIndex={0}
    >
      {/* Symbol */}
      <div
        className="truncate border-r border-white/[0.06] px-1.5 font-mono text-[10px] font-medium text-white/80"
        style={{ width: colWidths[0], minWidth: COLUMNS[0].minWidth }}
      >
        {symbol}
      </div>

      {/* Last */}
      <div
        className="truncate border-r border-white/[0.06] px-1.5 text-right font-mono text-[10px] text-white/70"
        style={{ width: colWidths[1], minWidth: COLUMNS[1].minWidth }}
      >
        {quote ? quote.last.toFixed(2) : "—"}
      </div>

      {/* Change */}
      <div
        className={`truncate border-r border-white/[0.06] px-1.5 text-right font-mono text-[10px] font-medium ${
          quote ? changeColor(quote.change) : "text-white/30"
        }`}
        style={{ width: colWidths[2], minWidth: COLUMNS[2].minWidth }}
      >
        {quote
          ? `${quote.change >= 0 ? "+" : ""}${quote.change.toFixed(2)}`
          : "—"}
      </div>

      {/* Change % */}
      <div
        className={`truncate px-1.5 text-right font-mono text-[10px] font-medium ${
          quote ? changeColor(quote.changePct) : "text-white/30"
        }`}
        style={{ width: colWidths[3], minWidth: COLUMNS[3].minWidth }}
      >
        {quote
          ? `${quote.changePct >= 0 ? "+" : ""}${quote.changePct.toFixed(2)}%`
          : "—"}
      </div>

      {/* Hover tooltip */}
      {hovered && (
        <div className="pointer-events-none absolute -top-1 left-0 z-[140] -translate-y-full rounded-md border border-white/[0.08] bg-[#1C2128] px-2.5 py-1.5 shadow-xl shadow-black/40">
          <p className="font-mono text-[11px] font-semibold text-white/90">
            {symbol}
          </p>
          <p className="text-[9px] text-white/40">{name}</p>
          {!quote && (
            <p className="mt-0.5 text-[8px] text-white/20">
              Waiting for TWS data
            </p>
          )}
        </div>
      )}
    </div>
  );
}
