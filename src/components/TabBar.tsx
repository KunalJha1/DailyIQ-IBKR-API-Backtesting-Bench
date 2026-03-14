import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type DragEvent,
} from "react";
import { X, Plus } from "lucide-react";
import { useTabs, tabPresets, type TabType } from "../lib/tabs";
import TabContextMenu from "./TabContextMenu";

export default function TabBar() {
  const {
    tabs,
    activeTabId,
    setActiveTab,
    addTab,
    closeTab,
    renameTab,
    duplicateTab,
    reorderTabs,
  } = useTabs();

  // Drag reorder state
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  // Context menu state
  const [menu, setMenu] = useState<{
    tabId: string;
    x: number;
    y: number;
  } | null>(null);

  // "+" dropdown state
  const [showAdd, setShowAdd] = useState(false);
  const [addPos, setAddPos] = useState<{ x: number; y: number } | null>(null);
  const addRef = useRef<HTMLDivElement>(null);

  // Inline rename state
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const renameRef = useRef<HTMLInputElement>(null);

  // Close add dropdown on click-outside / Escape
  const dropdownRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!showAdd) return;
    const handleClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        addRef.current && !addRef.current.contains(target) &&
        dropdownRef.current && !dropdownRef.current.contains(target)
      )
        setShowAdd(false);
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowAdd(false);
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [showAdd]);

  const handleDragStart = useCallback(
    (e: DragEvent, index: number) => {
      setDragIndex(index);
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", tabs[index].id);
    },
    [tabs],
  );

  const handleDragOver = useCallback(
    (e: DragEvent, index: number) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      if (dragIndex !== null && index !== dragIndex) {
        setDragOverIndex(index);
      }
    },
    [dragIndex],
  );

  const handleDrop = useCallback(
    (e: DragEvent, toIndex: number) => {
      e.preventDefault();
      if (dragIndex !== null && dragIndex !== toIndex) {
        reorderTabs(dragIndex, toIndex);
      }
      setDragIndex(null);
      setDragOverIndex(null);
    },
    [dragIndex, reorderTabs],
  );

  const handleDragEnd = useCallback(() => {
    setDragIndex(null);
    setDragOverIndex(null);
  }, []);

  const handleContextMenu = useCallback(
    (e: React.MouseEvent, tabId: string) => {
      e.preventDefault();
      setMenu({ tabId, x: e.clientX, y: e.clientY });
    },
    [],
  );

  const startRename = useCallback((tabId: string) => {
    setRenamingId(tabId);
    setMenu(null);
    requestAnimationFrame(() => renameRef.current?.select());
  }, []);

  const commitRename = useCallback(
    (tabId: string, value: string) => {
      renameTab(tabId, value);
      setRenamingId(null);
    },
    [renameTab],
  );

  const handleAddTab = useCallback(
    (type: TabType) => {
      addTab(type);
      setShowAdd(false);
    },
    [addTab],
  );

  return (
    <div className="flex h-8 shrink-0 items-end border-b border-white/[0.06] bg-base">
      <div className="flex h-full items-stretch overflow-x-auto">
        {tabs.map((tab, index) => {
          const isActive = tab.id === activeTabId;
          const isDragOver = dragOverIndex === index;

          return (
            <div
              key={tab.id}
              draggable={renamingId !== tab.id}
              onDragStart={(e) => handleDragStart(e, index)}
              onDragOver={(e) => handleDragOver(e, index)}
              onDrop={(e) => handleDrop(e, index)}
              onDragEnd={handleDragEnd}
              onContextMenu={(e) => handleContextMenu(e, tab.id)}
              onClick={() => setActiveTab(tab.id)}
              className={`group relative flex h-full cursor-pointer items-center gap-1.5 border-r border-white/[0.04] px-3 transition-colors duration-75 ${
                isActive
                  ? "bg-panel text-white/80"
                  : "text-white/35 hover:bg-white/[0.03] hover:text-white/55"
              } ${isDragOver ? "border-l-2 border-l-blue" : ""}`}
              style={{ minWidth: 80, maxWidth: 160 }}
            >
              {/* Active tab indicator */}
              {isActive && (
                <div className="absolute inset-x-0 top-0 h-[1px] bg-blue" />
              )}

              {/* Tab title or rename input */}
              {renamingId === tab.id ? (
                <input
                  ref={renameRef}
                  defaultValue={tab.title}
                  className="w-full bg-transparent text-[11px] text-white/80 outline-none"
                  onBlur={(e) => commitRename(tab.id, e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter")
                      commitRename(tab.id, e.currentTarget.value);
                    if (e.key === "Escape") setRenamingId(null);
                  }}
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <span className="truncate text-[11px]">{tab.title}</span>
              )}

              {/* Close button */}
              {tabs.length > 1 && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    closeTab(tab.id);
                  }}
                  className={`ml-auto flex h-4 w-4 shrink-0 items-center justify-center rounded-sm transition-colors duration-75 ${
                    isActive
                      ? "text-white/25 hover:bg-white/[0.08] hover:text-white/60"
                      : "text-transparent group-hover:text-white/20 group-hover:hover:bg-white/[0.08] group-hover:hover:text-white/60"
                  }`}
                >
                  <X className="h-2.5 w-2.5" strokeWidth={1.5} />
                </button>
              )}
            </div>
          );
        })}

        {/* Add tab button */}
        <div ref={addRef}>
          <button
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              setAddPos({ x: rect.left, y: rect.bottom + 4 });
              setShowAdd((v) => !v);
            }}
            className="flex h-full w-8 items-center justify-center text-white/20 transition-colors duration-75 hover:text-white/50"
          >
            <Plus className="h-3 w-3" strokeWidth={1.5} />
          </button>
        </div>
      </div>

      {/* Add tab dropdown — rendered fixed to avoid overflow clipping */}
      {showAdd && addPos && (
        <div
          ref={dropdownRef}
          className="fixed z-[100] min-w-[160px] rounded-md border border-white/[0.08] bg-[#1C2128] py-1 shadow-xl shadow-black/40"
          style={{ left: addPos.x, top: addPos.y }}
        >
          {tabPresets.map((preset) => (
            <button
              key={preset.type}
              onClick={() => handleAddTab(preset.type)}
              className="block w-full px-3 py-1.5 text-left text-[11px] text-white/60 transition-colors duration-75 hover:bg-white/[0.06] hover:text-white/80"
            >
              {preset.title}
            </button>
          ))}
        </div>
      )}

      {/* Context menu */}
      {menu && (
        <TabContextMenu
          x={menu.x}
          y={menu.y}
          onRename={() => startRename(menu.tabId)}
          onDuplicate={() => {
            duplicateTab(menu.tabId);
            setMenu(null);
          }}
          onClose={() => setMenu(null)}
        />
      )}
    </div>
  );
}
