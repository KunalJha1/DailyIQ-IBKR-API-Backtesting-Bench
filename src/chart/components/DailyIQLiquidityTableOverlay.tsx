import { useState, type PointerEvent as ReactPointerEvent } from 'react';
import { GripHorizontal, Lock, Unlock } from 'lucide-react';
import type { TechnicalTableWidgetState } from '../../lib/chart-state';
import type { LiquidityTableSnapshot } from '../../lib/table-overlay';
import { TECH_TABLE_HEADER_HEIGHT } from '../../lib/table-overlay';
import type { TechnicalTableResizeCorner } from './DailyIQTechnicalTableOverlay';

interface Props {
  snapshot: LiquidityTableSnapshot | null;
  widget: TechnicalTableWidgetState;
  dragging: boolean;
  resizing: boolean;
  minWidth?: number;
  maxWidth?: number;
  minHeight?: number;
  maxHeight?: number;
  onHeaderPointerDown: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onHeaderPointerMove: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onHeaderPointerUp: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onHeaderPointerCancel: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onResizePointerDown: (corner: TechnicalTableResizeCorner, event: ReactPointerEvent<HTMLDivElement>) => void;
  onResizePointerMove: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onResizePointerUp: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onResizePointerCancel: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onToggleLock: () => void;
}

export default function DailyIQLiquidityTableOverlay({
  snapshot,
  widget,
  dragging,
  resizing,
  minWidth = 400,
  maxWidth = 680,
  minHeight = 270,
  maxHeight = 520,
  onHeaderPointerDown,
  onHeaderPointerMove,
  onHeaderPointerUp,
  onHeaderPointerCancel,
  onResizePointerDown,
  onResizePointerMove,
  onResizePointerUp,
  onResizePointerCancel,
  onToggleLock,
}: Props) {
  const [headerHovered, setHeaderHovered] = useState(false);
  const rows = snapshot?.rows ?? [
    { highLabel: 'DH', highPrice: NaN, highSwept: false, highTarget: NaN, lowLabel: 'DL', lowPrice: NaN, lowSwept: false, lowTarget: NaN },
    { highLabel: 'PDH', highPrice: NaN, highSwept: false, highTarget: NaN, lowLabel: 'PDL', lowPrice: NaN, lowSwept: false, lowTarget: NaN },
    { highLabel: 'WH', highPrice: NaN, highSwept: false, highTarget: NaN, lowLabel: 'WL', lowPrice: NaN, lowSwept: false, lowTarget: NaN },
    { highLabel: 'MH', highPrice: NaN, highSwept: false, highTarget: NaN, lowLabel: 'ML', lowPrice: NaN, lowSwept: false, lowTarget: NaN },
    { highLabel: '52WH', highPrice: NaN, highSwept: false, highTarget: NaN, lowLabel: '52WL', lowPrice: NaN, lowSwept: false, lowTarget: NaN },
  ];
  const showHeader = !widget.locked || headerHovered;
  const widthScale = (widget.width - minWidth) / (maxWidth - minWidth);
  const heightScale = (widget.height - minHeight) / (maxHeight - minHeight);
  const tableScale = Math.max(0, Math.min(1, (widthScale + heightScale) / 2));
  const titleFontSize = 9 + (tableScale * 3);
  const topHeaderFontSize = 9 + (tableScale * 2);
  const columnHeaderFontSize = 8 + (tableScale * 3);
  const bodyFontSize = 9 + (tableScale * 3);
  const headerPadY = 4 + (tableScale * 3);
  const headerPadX = 6 + (tableScale * 4);
  const bodyPadY = 3 + (tableScale * 3);
  const bodyPadX = 5 + (tableScale * 4);
  const headerCellPadding = `${headerPadY}px ${headerPadX}px`;
  const bodyCellPadding = `${bodyPadY}px ${bodyPadX}px`;
  const lockButtonSize = 16 + (tableScale * 8);
  const gripSize = 12 + (tableScale * 6);
  const handleSize = 14 + (tableScale * 8);
  const resizeHandleInset = 3 + (tableScale * 2);
  const closePrice = snapshot?.close ?? NaN;
  const nearPct = snapshot?.nearPct ?? 0.005;
  const highlightNearLevels = snapshot?.highlightNearLevels ?? true;
  const atrDaily = snapshot?.atrDaily ?? NaN;
  const targetAtrMult = snapshot?.targetAtrMult ?? 1;
  const cornerHandles: Array<{ corner: TechnicalTableResizeCorner; cursor: string; style: { left?: number; right?: number; top?: number; bottom?: number } }> = [
    { corner: 'top-left', cursor: 'nwse-resize', style: { left: 0, top: 0 } },
    { corner: 'top-right', cursor: 'nesw-resize', style: { right: 0, top: 0 } },
    { corner: 'bottom-left', cursor: 'nesw-resize', style: { left: 0, bottom: 0 } },
    { corner: 'bottom-right', cursor: 'nwse-resize', style: { right: 0, bottom: 0 } },
  ];

  const isNear = (level: number) => highlightNearLevels && Number.isFinite(level) && level !== 0 && Number.isFinite(closePrice) && Math.abs(closePrice - level) / Math.abs(level) <= nearPct;
  const priceText = (value: number) => Number.isFinite(value) ? value.toFixed(2) : '--';
  const atrText = Number.isFinite(atrDaily) ? atrDaily.toFixed(2) : '--';
  const targetAtrText = `${targetAtrMult.toFixed(2)} ATR`;
  const sweepText = (didSweep: boolean, bullSide: boolean) => didSweep ? (bullSide ? 'Swept ↑' : 'Swept ↓') : 'Not Swept';
  const sweepBg = (didSweep: boolean, bullSide: boolean) => !didSweep ? '#2D2D3C' : bullSide ? '#00C853' : '#FF3D71';
  const targetBg = (didSweep: boolean, bullSide: boolean) => !didSweep ? '#2D2D3C' : bullSide ? '#00C853' : '#FF3D71';
  const sweepTextColor = (didSweep: boolean, bullSide: boolean) => didSweep && bullSide ? '#000000' : '#FFFFFF';
  const levelBg = (near: boolean) => near ? '#FF8C00' : '#141821';
  const priceBg = (near: boolean) => near ? '#FFB43C' : '#232332';
  const cellTextColor = (near: boolean) => near ? '#000000' : '#FFFFFF';

  return (
    <div
      onPointerEnter={() => setHeaderHovered(true)}
      onPointerLeave={() => setHeaderHovered(false)}
      style={{
        position: 'absolute', left: widget.x, top: widget.y, zIndex: 18, pointerEvents: 'auto',
        border: '1px solid rgba(255,255,255,0.12)', backgroundColor: 'rgba(0,0,0,0.92)',
        borderRadius: 8, overflow: 'hidden',
        boxShadow: dragging || resizing ? '0 16px 36px rgba(0,0,0,0.52)' : '0 10px 24px rgba(0,0,0,0.42)',
        width: widget.width, height: widget.height, display: 'flex', flexDirection: 'column',
        transition: dragging || resizing ? 'none' : 'box-shadow 120ms ease-out',
      }}
    >
      <div
        onPointerDown={widget.locked ? undefined : onHeaderPointerDown}
        onPointerMove={widget.locked ? undefined : onHeaderPointerMove}
        onPointerUp={widget.locked ? undefined : onHeaderPointerUp}
        onPointerCancel={widget.locked ? undefined : onHeaderPointerCancel}
        style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: TECH_TABLE_HEADER_HEIGHT, zIndex: 2,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 8px 0 6px', borderBottom: '1px solid rgba(255,255,255,0.12)',
          fontSize: titleFontSize, fontFamily: '"JetBrains Mono", monospace', color: '#E6EDF3',
          userSelect: 'none', WebkitUserSelect: 'none',
          background: widget.locked ? '#000000' : dragging
            ? 'linear-gradient(180deg, rgba(39,56,82,0.98) 0%, rgba(19,28,43,0.98) 100%)'
            : 'linear-gradient(180deg, rgba(28,33,40,0.98) 0%, rgba(15,23,32,0.98) 100%)',
          cursor: widget.locked ? 'default' : dragging ? 'grabbing' : 'grab',
          touchAction: widget.locked ? undefined : 'none',
          opacity: showHeader ? 1 : 0, pointerEvents: showHeader ? 'auto' : 'none',
          transform: showHeader ? 'translateY(0)' : 'translateY(-100%)',
          transition: 'opacity 120ms ease-out, transform 120ms ease-out',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
          {!widget.locked && (
            <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: gripSize, height: gripSize, borderRadius: 4, color: dragging ? '#C7D2FE' : '#8B949E', background: dragging ? 'rgba(140,180,255,0.16)' : 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', flexShrink: 0 }}>
              <GripHorizontal size={Math.max(8, gripSize - 6)} strokeWidth={1.7} />
            </span>
          )}
          <span style={{ color: '#8B949E' }}>Liquidity Sweep Table</span>
        </div>
        <button
          type="button"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => { e.stopPropagation(); onToggleLock(); }}
          style={{ border: '1px solid rgba(255,255,255,0.12)', borderRadius: 4, background: 'transparent', color: '#E6EDF3', width: lockButtonSize, height: lockButtonSize, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1, fontSize: 11 + tableScale, fontFamily: '"JetBrains Mono", monospace', padding: 0, cursor: 'pointer' }}
          title={widget.locked ? 'Unlock placement' : 'Lock placement'}
        >
          {widget.locked ? <Lock size={12} strokeWidth={1.5} /> : <Unlock size={12} strokeWidth={1.5} />}
        </button>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', position: 'relative', backgroundColor: '#1E2232', userSelect: 'none', WebkitUserSelect: 'none' }}>
        <table style={{ width: '100%', height: '100%', borderCollapse: 'separate', borderSpacing: 0, tableLayout: 'fixed', fontSize: bodyFontSize, fontFamily: '"JetBrains Mono", monospace', color: '#E6EDF3', backgroundColor: '#1E2232' }}>
          <colgroup>
            <col style={{ width: '15%' }} /><col style={{ width: '12%' }} /><col style={{ width: '12%' }} /><col style={{ width: '11%' }} />
            <col style={{ width: '15%' }} /><col style={{ width: '12%' }} /><col style={{ width: '12%' }} /><col style={{ width: '11%' }} />
          </colgroup>
          <thead>
            <tr>
              <th style={{ padding: headerCellPadding, borderBottom: '1px solid rgba(255,255,255,0.14)', backgroundColor: '#3A3F52', color: '#FFFFFF', textAlign: 'center', fontWeight: 600, fontSize: topHeaderFontSize, whiteSpace: 'nowrap' }}>ATR</th>
              <th style={{ padding: headerCellPadding, borderBottom: '1px solid rgba(255,255,255,0.14)', backgroundColor: '#FACC15', color: '#000000', textAlign: 'center', fontWeight: 600, fontSize: topHeaderFontSize, whiteSpace: 'nowrap' }}>{atrText}</th>
              <th style={{ padding: headerCellPadding, borderBottom: '1px solid rgba(255,255,255,0.14)', backgroundColor: 'transparent' }} />
              <th style={{ padding: headerCellPadding, borderBottom: '1px solid rgba(255,255,255,0.14)', backgroundColor: 'transparent' }} />
              <th style={{ padding: headerCellPadding, borderBottom: '1px solid rgba(255,255,255,0.14)', backgroundColor: '#3A3F52', color: '#FFFFFF', textAlign: 'center', fontWeight: 600, fontSize: topHeaderFontSize, whiteSpace: 'nowrap' }}>ATR</th>
              <th style={{ padding: headerCellPadding, borderBottom: '1px solid rgba(255,255,255,0.14)', backgroundColor: '#FACC15', color: '#000000', textAlign: 'center', fontWeight: 600, fontSize: topHeaderFontSize, whiteSpace: 'nowrap' }}>{atrText}</th>
              <th style={{ padding: headerCellPadding, borderBottom: '1px solid rgba(255,255,255,0.14)', backgroundColor: 'transparent' }} />
              <th style={{ padding: headerCellPadding, borderBottom: '1px solid rgba(255,255,255,0.14)', backgroundColor: 'transparent' }} />
            </tr>
            <tr>
              {['LEVEL (H)', 'PRICE', 'SWEEP?', 'TP', 'LEVEL (L)', 'PRICE', 'SWEEP?', 'TP'].map((head) => (
                <th key={head} style={{ padding: headerCellPadding, borderBottom: '1px solid rgba(255,255,255,0.14)', backgroundColor: '#1E2232', color: '#FFFFFF', textAlign: 'center', fontWeight: 600, fontSize: columnHeaderFontSize, whiteSpace: 'nowrap' }}>{head}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const highNear = isNear(row.highPrice);
              const lowNear = isNear(row.lowPrice);
              return (
                <tr key={`${row.highLabel}-${row.lowLabel}`}>
                  <td style={{ padding: bodyCellPadding, backgroundColor: levelBg(highNear), color: cellTextColor(highNear), textAlign: 'center', whiteSpace: 'nowrap' }}>{row.highLabel}</td>
                  <td style={{ padding: bodyCellPadding, backgroundColor: priceBg(highNear), color: cellTextColor(highNear), textAlign: 'center', whiteSpace: 'nowrap' }}>{priceText(row.highPrice)}</td>
                  <td style={{ padding: bodyCellPadding, backgroundColor: sweepBg(row.highSwept, false), color: sweepTextColor(row.highSwept, false), textAlign: 'center', whiteSpace: 'nowrap' }}>{sweepText(row.highSwept, false)}</td>
                  <td style={{ padding: bodyCellPadding, backgroundColor: targetBg(row.highSwept, false), color: '#FFFFFF', textAlign: 'center', whiteSpace: 'pre-line', lineHeight: 1.15 }}>{`${priceText(row.highTarget)}\n${targetAtrText}`}</td>
                  <td style={{ padding: bodyCellPadding, backgroundColor: levelBg(lowNear), color: cellTextColor(lowNear), textAlign: 'center', whiteSpace: 'nowrap' }}>{row.lowLabel}</td>
                  <td style={{ padding: bodyCellPadding, backgroundColor: priceBg(lowNear), color: cellTextColor(lowNear), textAlign: 'center', whiteSpace: 'nowrap' }}>{priceText(row.lowPrice)}</td>
                  <td style={{ padding: bodyCellPadding, backgroundColor: sweepBg(row.lowSwept, true), color: sweepTextColor(row.lowSwept, true), textAlign: 'center', whiteSpace: 'nowrap' }}>{sweepText(row.lowSwept, true)}</td>
                  <td style={{ padding: bodyCellPadding, backgroundColor: targetBg(row.lowSwept, true), color: row.lowSwept ? '#000000' : '#FFFFFF', textAlign: 'center', whiteSpace: 'pre-line', lineHeight: 1.15 }}>{`${priceText(row.lowTarget)}\n${targetAtrText}`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {!widget.locked && (
        <>
          {cornerHandles.map(({ corner, cursor, style }) => (
            <div
              key={corner}
              onPointerDown={(e) => onResizePointerDown(corner, e)}
              onPointerMove={onResizePointerMove}
              onPointerUp={onResizePointerUp}
              onPointerCancel={onResizePointerCancel}
              title={`Resize table from ${corner}`}
              style={{ position: 'absolute', width: handleSize, height: handleSize, cursor, touchAction: 'none', ...style }}
            >
              <div style={{ position: 'absolute', inset: 4, insetInline: resizeHandleInset, insetBlock: resizeHandleInset, borderRadius: 4, border: '1px solid rgba(255,255,255,0.18)', background: 'rgba(255,255,255,0.08)' }} />
            </div>
          ))}
        </>
      )}
    </div>
  );
}
