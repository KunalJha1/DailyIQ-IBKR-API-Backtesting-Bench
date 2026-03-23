import { useRef, useEffect, useCallback, useState } from 'react';
import { ChartEngine } from '../core/ChartEngine';
import type { OHLCVBar, ChartType, Timeframe, ScriptResult, ChartBrandingMode, ChartLayout, DrawingTool } from '../types';
import { Minus, TrendingUp, Trash2 } from 'lucide-react';

interface ChartCanvasProps {
  bars: OHLCVBar[];
  symbol?: string;
  chartType: ChartType;
  timeframe: Timeframe;
  engineRef: React.MutableRefObject<ChartEngine | null>;
  activeScripts?: Map<string, ScriptResult>;
  liveMode?: boolean;
  stopperPx?: number;
  onStopperPxChange?: (px: number) => void;
  brandingMode?: ChartBrandingMode;
  onViewportChange?: (startIdx: number, endIdx: number) => void;
  onLayoutChange?: (layout: ChartLayout) => void;
  children?: React.ReactNode;
}

export default function ChartCanvas({
  bars,
  symbol,
  chartType,
  timeframe,
  engineRef,
  activeScripts,
  liveMode = false,
  stopperPx = 0,
  onStopperPxChange,
  brandingMode = 'none',
  onViewportChange,
  onLayoutChange,
  children,
}: ChartCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeTool, setActiveTool] = useState<DrawingTool>('none');

  // Initialize engine
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const engine = new ChartEngine(canvas);
    engineRef.current = engine;
    engine.setDrawingTool('none');

    return () => {
      engine.destroy();
      engineRef.current = null;
    };
  }, [engineRef]);

  // ResizeObserver
  const handleResize = useCallback(() => {
    const container = containerRef.current;
    const engine = engineRef.current;
    if (!container || !engine) return;

    const width = container.offsetWidth;
    const height = container.offsetHeight;
    engine.resize(width, height);
    onLayoutChange?.(engine.getLayout());
  }, [engineRef, onLayoutChange]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const ro = new ResizeObserver(handleResize);
    ro.observe(container);
    handleResize();

    return () => ro.disconnect();
  }, [handleResize]);

  // Update data
  useEffect(() => {
    engineRef.current?.setData(bars);
    const engine = engineRef.current;
    if (engine) onLayoutChange?.(engine.getLayout());
  }, [bars, engineRef, onLayoutChange]);

  // Update chart type
  useEffect(() => {
    engineRef.current?.setChartType(chartType);
  }, [chartType, engineRef]);

  // Update timeframe
  useEffect(() => {
    engineRef.current?.setTimeframe(timeframe);
  }, [timeframe, engineRef]);

  useEffect(() => {
    engineRef.current?.setBrandingMode(brandingMode);
  }, [brandingMode, engineRef]);

  useEffect(() => {
    engineRef.current?.setBrandingSymbol(symbol ?? '');
  }, [symbol, engineRef]);

  // Wire viewport change callback
  useEffect(() => {
    engineRef.current?.setOnViewportChange(onViewportChange ?? null);
  }, [onViewportChange, engineRef]);

  // Update live mode / stopper
  useEffect(() => {
    const engine = engineRef.current;
    if (!engine) return;
    engine.setLiveMode(liveMode);
    engine.setStopperPx(stopperPx);
    onLayoutChange?.(engine.getLayout());
  }, [liveMode, stopperPx, engineRef, onLayoutChange]);

  // Update script results (multi-script)
  useEffect(() => {
    const engine = engineRef.current;
    if (!engine) return;

    engine.clearAllScripts();
    if (activeScripts) {
      for (const [id, result] of activeScripts) {
        engine.setScriptResult(id, result);
      }
    }
    onLayoutChange?.(engine.getLayout());
  }, [activeScripts, engineRef, onLayoutChange]);

  const handleSelectTool = useCallback((tool: DrawingTool) => {
    const nextTool = activeTool === tool ? 'none' : tool;
    setActiveTool(nextTool);
    engineRef.current?.setDrawingTool(nextTool);
  }, [activeTool, engineRef]);

  const handleClearDrawings = useCallback(() => {
    engineRef.current?.clearDrawings();
    setActiveTool('none');
    engineRef.current?.setDrawingTool('none');
  }, [engineRef]);

  const toolButtonClass = (tool: DrawingTool) => [
    'w-9 h-9 rounded-md border transition-colors flex items-center justify-center',
    activeTool === tool
      ? 'bg-blue/20 border-blue text-blue'
      : 'bg-base/80 border-border-default text-text-secondary hover:bg-hover hover:text-text-primary',
  ].join(' ');

  return (
    <div ref={containerRef} className="flex-1 relative overflow-hidden">
      <canvas
        ref={canvasRef}
        className="absolute inset-0"
        style={{ cursor: activeTool === 'none' ? 'crosshair' : 'copy' }}
      />
      <div className="absolute left-3 top-3 z-20 flex flex-col gap-2 rounded-lg border border-border-default bg-base/90 p-2 shadow-lg backdrop-blur-sm">
        <button
          type="button"
          className={toolButtonClass('trendline')}
          onClick={() => handleSelectTool('trendline')}
          title="Trendline"
        >
          <Minus size={16} />
        </button>
        <button
          type="button"
          className={toolButtonClass('fibRetracement')}
          onClick={() => handleSelectTool('fibRetracement')}
          title="Fibonacci retracement"
        >
          <TrendingUp size={16} />
        </button>
        <button
          type="button"
          className="w-9 h-9 rounded-md border border-border-default bg-base/80 text-text-secondary hover:bg-hover hover:text-red flex items-center justify-center transition-colors"
          onClick={handleClearDrawings}
          title="Clear drawings"
        >
          <Trash2 size={16} />
        </button>
      </div>
      {children}
      {liveMode && (
        <div
          className="absolute right-2 bottom-1 flex items-center gap-2"
          style={{
            height: 20,
            padding: '0 6px',
            backgroundColor: 'rgba(13,17,23,0.7)',
            border: '1px solid rgba(33,38,45,0.7)',
            borderRadius: 4,
            backdropFilter: 'blur(2px)',
          }}
        >
          <span className="text-[9px] font-mono text-text-muted">Stop</span>
          <input
            type="range"
            min={0}
            max={200}
            step={2}
            value={stopperPx}
            onChange={(e) => onStopperPxChange?.(Number(e.target.value))}
            style={{ width: 90 }}
          />
          <span className="text-[9px] font-mono text-text-muted">{stopperPx}px</span>
        </div>
      )}
    </div>
  );
}
