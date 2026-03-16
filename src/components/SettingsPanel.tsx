import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { useTws } from "../lib/tws";

const CONNECTION_LABELS: Record<string, string> = {
  "tws-live": "TWS Live",
  "tws-paper": "TWS Paper",
  "gateway-live": "Gateway Live",
  "gateway-paper": "Gateway Paper",
};

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const { status, port, clientId, connectionType, settings, updateSettings, probe } =
    useTws();
  const panelRef = useRef<HTMLDivElement>(null);

  // Escape to close
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  const statusDot =
    status === "connected"
      ? "bg-green"
      : status === "probing"
        ? "bg-amber animate-pulse"
        : "bg-red/60";

  const statusLabel =
    status === "connected" && connectionType
      ? `Connected to ${CONNECTION_LABELS[connectionType]} on :${port}`
      : status === "probing"
        ? "Probing ports..."
        : "Disconnected";

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[300] bg-black/40"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        className="fixed inset-y-0 right-0 z-[301] flex w-[380px] flex-col border-l border-white/[0.06] bg-panel"
        style={{ transition: "transform 120ms ease-out" }}
      >
        {/* Header */}
        <div className="flex h-7 shrink-0 items-center justify-between border-b border-white/[0.06] px-3">
          <span className="text-[11px] font-medium text-white/60">
            Settings
          </span>
          <button
            onClick={onClose}
            className="text-white/30 transition-colors duration-75 hover:text-white/60"
          >
            <X className="h-3.5 w-3.5" strokeWidth={1.5} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {/* Connection Section */}
          <section className="mb-6">
            <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-white/30">
              Connection
            </h3>

            {/* Status */}
            <div className="mb-3 flex items-center gap-2">
              <span
                className={`inline-block h-2 w-2 rounded-full ${statusDot}`}
              />
              <span className="font-mono text-[11px] text-white/50">
                {statusLabel}
              </span>
            </div>

            {/* Port + Client ID */}
            <div className="mb-3 flex gap-4 font-mono text-[10px] text-white/35">
              <span>
                Port:{" "}
                <span className="text-white/50">{port ?? "—"}</span>
              </span>
              <span>
                Client ID:{" "}
                <span className="text-white/50">{clientId ?? "—"}</span>
              </span>
            </div>

            {/* Probe button */}
            <button
              onClick={() => probe()}
              disabled={status === "probing"}
              className="rounded-md border border-white/[0.08] bg-base px-3 py-1 text-[11px] text-white/50 transition-colors duration-120 hover:bg-white/[0.04] hover:text-white/70 disabled:opacity-40"
            >
              {status === "probing" ? "Probing..." : "Probe Now"}
            </button>
          </section>

          {/* Trading Configuration */}
          <section>
            <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-white/30">
              Trading Configuration
            </h3>

            {/* Radio: FA Group vs Account */}
            <div className="mb-3 flex flex-col gap-2">
              <label className="flex cursor-pointer items-center gap-2 text-[11px] text-white/50">
                <input
                  type="radio"
                  name="tradingMode"
                  checked={settings.tradingMode === "fa-group"}
                  onChange={() => updateSettings({ tradingMode: "fa-group" })}
                  className="accent-blue"
                />
                Trade using FA Group
              </label>
              <label className="flex cursor-pointer items-center gap-2 text-[11px] text-white/50">
                <input
                  type="radio"
                  name="tradingMode"
                  checked={settings.tradingMode === "account"}
                  onChange={() => updateSettings({ tradingMode: "account" })}
                  className="accent-blue"
                />
                Trade using Account
              </label>
            </div>

            {/* Conditional input */}
            {settings.tradingMode === "fa-group" ? (
              <div>
                <label className="mb-1 block text-[10px] text-white/30">
                  FA Group Name
                </label>
                <input
                  type="text"
                  value={settings.faGroup}
                  onChange={(e) => updateSettings({ faGroup: e.target.value })}
                  placeholder="e.g. AllAccounts"
                  className="w-full rounded border border-white/[0.08] bg-base px-2 py-1 font-mono text-[11px] text-white/60 outline-none transition-colors duration-75 placeholder:text-white/15 focus:border-blue/40"
                />
              </div>
            ) : (
              <div>
                <label className="mb-1 block text-[10px] text-white/30">
                  Account ID
                </label>
                <input
                  type="text"
                  value={settings.accountId}
                  onChange={(e) =>
                    updateSettings({ accountId: e.target.value })
                  }
                  placeholder="e.g. DU1234567"
                  className="w-full rounded border border-white/[0.08] bg-base px-2 py-1 font-mono text-[11px] text-white/60 outline-none transition-colors duration-75 placeholder:text-white/15 focus:border-blue/40"
                />
              </div>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
