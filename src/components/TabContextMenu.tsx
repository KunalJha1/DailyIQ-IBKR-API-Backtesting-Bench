import { useEffect, useRef } from "react";

interface TabContextMenuProps {
  x: number;
  y: number;
  onRename: () => void;
  onDuplicate: () => void;
  onClose: () => void;
}

export default function TabContextMenu({
  x,
  y,
  onRename,
  onDuplicate,
  onClose,
}: TabContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [onClose]);

  const itemClass =
    "block w-full text-left px-3 py-1.5 text-[11px] text-white/60 hover:bg-white/[0.06] hover:text-white/80 transition-colors duration-75";

  return (
    <div
      ref={ref}
      className="fixed z-[100] min-w-[120px] rounded-md border border-white/[0.08] bg-[#1C2128] py-1 shadow-xl shadow-black/40"
      style={{ left: x, top: y }}
    >
      <button className={itemClass} onClick={onRename}>
        Rename
      </button>
      <button className={itemClass} onClick={onDuplicate}>
        Duplicate
      </button>
    </div>
  );
}
