import { useRef, useState, useCallback, type ReactNode } from "react";
import type { LayoutComponent } from "../lib/layout-types";

interface GridLayoutProps {
  columns: number;
  rowHeight: number;
  components: LayoutComponent[];
  locked: boolean;
  onMoveComponent: (id: string, x: number, y: number) => void;
  onResizeComponent: (id: string, w: number, h: number) => void;
  renderComponent: (comp: LayoutComponent) => ReactNode;
}

export default function GridLayout({
  columns,
  rowHeight,
  components,
  locked,
  onMoveComponent,
  onResizeComponent,
  renderComponent,
}: GridLayoutProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Drag state
  const [dragging, setDragging] = useState<string | null>(null);
  const [dragPreview, setDragPreview] = useState<{ x: number; y: number } | null>(null);

  // Resize state
  const [resizing, setResizing] = useState<string | null>(null);
  const [resizePreview, setResizePreview] = useState<{ w: number; h: number } | null>(null);

  // Free-form (Ctrl/Cmd drag) state
  const [freeFormActive, setFreeFormActive] = useState(false);

  const getColWidth = useCallback(() => {
    if (!containerRef.current) return 0;
    return containerRef.current.clientWidth / columns;
  }, [columns]);

  // --- Drag handlers ---
  const handleDragStart = useCallback(
    (e: React.MouseEvent, comp: LayoutComponent) => {
      if (locked) return;
      e.preventDefault();
      e.stopPropagation();
      setDragging(comp.id);
      setDragPreview({ x: comp.x, y: comp.y });
      setFreeFormActive(e.ctrlKey || e.metaKey);

      const startX = e.clientX;
      const startY = e.clientY;

      const onMove = (ev: MouseEvent) => {
        const colW = getColWidth();
        if (!colW) return;
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;
        const isFreeForm = ev.ctrlKey || ev.metaKey;
        setFreeFormActive(isFreeForm);

        let newX: number, newY: number;
        if (isFreeForm) {
          newX = Math.max(0, Math.min(columns - comp.w, comp.x + dx / colW));
          newY = Math.max(0, comp.y + dy / rowHeight);
        } else {
          newX = Math.max(0, Math.min(columns - comp.w, comp.x + Math.round(dx / colW)));
          newY = Math.max(0, comp.y + Math.round(dy / rowHeight));
        }
        setDragPreview({ x: newX, y: newY });
      };

      const onUp = (ev: MouseEvent) => {
        const colW = getColWidth();
        if (colW) {
          const dx = ev.clientX - startX;
          const dy = ev.clientY - startY;
          const isFreeForm = ev.ctrlKey || ev.metaKey;

          let newX: number, newY: number;
          if (isFreeForm) {
            newX = Math.max(0, Math.min(columns - comp.w, comp.x + dx / colW));
            newY = Math.max(0, comp.y + dy / rowHeight);
          } else {
            newX = Math.max(0, Math.min(columns - comp.w, comp.x + Math.round(dx / colW)));
            newY = Math.max(0, comp.y + Math.round(dy / rowHeight));
          }
          onMoveComponent(comp.id, newX, newY);
        }
        setDragging(null);
        setDragPreview(null);
        setFreeFormActive(false);
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [locked, columns, rowHeight, getColWidth, onMoveComponent],
  );

  // --- Resize handlers ---
  const handleResizeStart = useCallback(
    (e: React.MouseEvent, comp: LayoutComponent) => {
      if (locked) return;
      e.preventDefault();
      e.stopPropagation();
      setResizing(comp.id);
      setResizePreview({ w: comp.w, h: comp.h });
      setFreeFormActive(e.ctrlKey || e.metaKey);

      const startX = e.clientX;
      const startY = e.clientY;

      const onMove = (ev: MouseEvent) => {
        const colW = getColWidth();
        if (!colW) return;
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;
        const isFreeForm = ev.ctrlKey || ev.metaKey;
        setFreeFormActive(isFreeForm);

        let newW: number, newH: number;
        if (isFreeForm) {
          newW = Math.max(2, Math.min(columns - comp.x, comp.w + dx / colW));
          newH = Math.max(3, comp.h + dy / rowHeight);
        } else {
          newW = Math.max(2, Math.min(columns - comp.x, comp.w + Math.round(dx / colW)));
          newH = Math.max(3, comp.h + Math.round(dy / rowHeight));
        }
        setResizePreview({ w: newW, h: newH });
      };

      const onUp = (ev: MouseEvent) => {
        const colW = getColWidth();
        if (colW) {
          const dx = ev.clientX - startX;
          const dy = ev.clientY - startY;
          const isFreeForm = ev.ctrlKey || ev.metaKey;

          let newW: number, newH: number;
          if (isFreeForm) {
            newW = Math.max(2, Math.min(columns - comp.x, comp.w + dx / colW));
            newH = Math.max(3, comp.h + dy / rowHeight);
          } else {
            newW = Math.max(2, Math.min(columns - comp.x, comp.w + Math.round(dx / colW)));
            newH = Math.max(3, comp.h + Math.round(dy / rowHeight));
          }
          onResizeComponent(comp.id, newW, newH);
        }
        setResizing(null);
        setResizePreview(null);
        setFreeFormActive(false);
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [locked, columns, rowHeight, getColWidth, onResizeComponent],
  );

  const maxRow = components.reduce((max, c) => {
    const h = resizing === c.id && resizePreview ? resizePreview.h : c.h;
    const y = dragging === c.id && dragPreview ? dragPreview.y : c.y;
    return Math.max(max, y + h);
  }, 0);
  const minRows = Math.max(maxRow + 2, Math.ceil(400 / rowHeight));

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full overflow-auto"
      style={{ minHeight: minRows * rowHeight }}
    >
      {/* Grid lines when unlocked */}
      {!locked && (
        <div className="pointer-events-none absolute inset-0" aria-hidden>
          {/* Column lines */}
          {Array.from({ length: columns + 1 }, (_, i) => (
            <div
              key={`col-${i}`}
              className="absolute top-0 h-full"
              style={{
                left: `${(i / columns) * 100}%`,
                width: 1,
                background:
                  i === 0 || i === columns
                    ? "transparent"
                    : "rgba(255,255,255,0.03)",
              }}
            />
          ))}
          {/* Row lines */}
          {Array.from({ length: minRows + 1 }, (_, i) => (
            <div
              key={`row-${i}`}
              className="absolute left-0 w-full"
              style={{
                top: i * rowHeight,
                height: 1,
                background: i === 0 ? "transparent" : "rgba(255,255,255,0.03)",
              }}
            />
          ))}
        </div>
      )}

      {/* Components */}
      {components.map((comp) => {
        const isDragging = dragging === comp.id;
        const isResizing = resizing === comp.id;
        const posX = isDragging && dragPreview ? dragPreview.x : comp.x;
        const posY = isDragging && dragPreview ? dragPreview.y : comp.y;
        const w = isResizing && resizePreview ? resizePreview.w : comp.w;
        const h = isResizing && resizePreview ? resizePreview.h : comp.h;

        return (
          <div
            key={comp.id}
            className={`absolute ${isDragging || isResizing ? "z-50" : "z-10"} ${
              isDragging ? "opacity-80" : ""
            }`}
            style={{
              left: `${(posX / columns) * 100}%`,
              top: posY * rowHeight,
              width: `${(w / columns) * 100}%`,
              height: h * rowHeight,
            }}
          >
            {/* Drag handle — whole component header area, but we let the
                component itself handle clicks on buttons. The outer div
                handles mousedown for drag only when unlocked. */}
            <div
              className={`h-full w-full ${!locked ? "cursor-grab" : ""} ${
                isDragging ? "cursor-grabbing" : ""
              }`}
              onMouseDown={(e) => {
                // Don't start drag if clicking on interactive elements
                const target = e.target as HTMLElement;
                if (target.closest("button, input, [data-no-drag]")) return;
                handleDragStart(e, comp);
              }}
            >
              {renderComponent(comp)}
            </div>

            {/* Resize handle — bottom-right corner, only when unlocked */}
            {!locked && (
              <div
                className="absolute bottom-0 right-0 z-[60] h-3 w-3 cursor-se-resize"
                onMouseDown={(e) => handleResizeStart(e, comp)}
              >
                {/* Visual indicator */}
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 12 12"
                  className="text-white/20"
                >
                  <path
                    d="M10 2L2 10M10 6L6 10M10 10L10 10"
                    stroke="currentColor"
                    strokeWidth="1"
                    fill="none"
                  />
                </svg>
              </div>
            )}

            {/* Unlocked outline */}
            {!locked && !isDragging && !isResizing && (
              <div className="pointer-events-none absolute inset-0 border border-dashed border-white/[0.08]" />
            )}
            {/* Active drag/resize outline — amber for free-form, blue for snap */}
            {(isDragging || isResizing) && (
              <div
                className={`pointer-events-none absolute inset-0 border-2 ${
                  freeFormActive ? "border-amber/40" : "border-blue/40"
                }`}
              />
            )}
          </div>
        );
      })}

      {/* Empty state */}
      {components.length === 0 && (
        <div className="flex h-full min-h-[400px] items-center justify-center">
          <p className="text-[11px] text-white/20">
            Click "Add Component" to get started
          </p>
        </div>
      )}
    </div>
  );
}
