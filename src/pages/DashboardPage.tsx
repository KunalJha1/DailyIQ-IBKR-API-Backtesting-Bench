import { useState } from "react";
import DashboardToolbar from "../components/DashboardToolbar";

export default function DashboardPage() {
  const [locked, setLocked] = useState(true);
  const [linkChannel, setLinkChannel] = useState<number | null>(null);

  return (
    <div className="flex h-full flex-col">
      <DashboardToolbar
        locked={locked}
        onToggleLock={() => setLocked((v) => !v)}
        linkChannel={linkChannel}
        onSetLinkChannel={setLinkChannel}
        onAddComponent={() => {}}
      />
      <div className="flex flex-1 items-center justify-center">
        <p className="text-[11px] text-white/20">Dashboard</p>
      </div>
    </div>
  );
}
