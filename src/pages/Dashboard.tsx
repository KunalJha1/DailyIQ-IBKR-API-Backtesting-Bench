import { useAuth } from "../lib/auth";
import { useTabs, type TabType } from "../lib/tabs";
import TabBar from "../components/TabBar";
import DashboardPage from "./DashboardPage";
import ChartPage from "./ChartPage";
import OptionsPage from "./OptionsPage";
import BacktestPage from "./BacktestPage";
import SimulationsPage from "./SimulationsPage";
import HeatmapPage from "./HeatmapPage";
import MarketBiasPage from "./MarketBiasPage";

const pageByType: Record<TabType, React.FC> = {
  dashboard: DashboardPage,
  chart: ChartPage,
  options: OptionsPage,
  backtest: BacktestPage,
  simulations: SimulationsPage,
  heatmap: HeatmapPage,
  bias: MarketBiasPage,
};

export default function Dashboard() {
  const { session } = useAuth();
  const { tabs, activeTabId } = useTabs();
  const user = session?.user;
  const firstName =
    user?.user_metadata?.full_name?.split(" ")[0] ||
    user?.email?.split("@")[0] ||
    "User";

  const activeTab = tabs.find((t) => t.id === activeTabId);
  const ActivePage = activeTab ? pageByType[activeTab.type] : null;

  return (
    <div className="flex h-screen flex-col bg-base">
      {/* Top bar */}
      <header className="titlebar-drag flex h-7 shrink-0 items-center justify-between border-b border-white/[0.06] bg-base px-3 pl-[78px]">
        <div className="titlebar-no-drag">
          <button className="text-[11px] font-light text-white/30 transition-all duration-100 hover:text-white/80">
            Settings
          </button>
        </div>

        <p className="titlebar-no-drag text-[11px] font-light tracking-wide text-white/40">
          Hi, <span className="text-white/70">{firstName}</span>
        </p>
      </header>

      {/* Tab bar */}
      <TabBar />

      {/* Page content */}
      <main className="flex-1 overflow-hidden">
        {ActivePage && <ActivePage />}
      </main>

      {/* Bottom status bar */}
      <footer className="flex h-6 shrink-0 items-center justify-between border-t border-white/[0.06] bg-base px-3 text-[10px] tracking-wide">
        <p className="font-light text-white/20">
          For research purposes only. Questions?{" "}
          <a
            href="mailto:dailyiqme@gmail.com"
            className="text-white/30 underline decoration-white/10 underline-offset-2 transition-colors duration-100 hover:text-white/50"
          >
            dailyiqme@gmail.com
          </a>
        </p>

        <div className="flex items-center gap-3 font-mono text-[10px] text-white/30">
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-red/60" />
            <span>Disconnected</span>
          </div>
          <span className="text-white/10">|</span>
          <span>
            Port <span className="text-white/15">—</span>
          </span>
          <span className="text-white/10">|</span>
          <span>
            Client ID <span className="text-white/15">—</span>
          </span>
        </div>
      </footer>
    </div>
  );
}
