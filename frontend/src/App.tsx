import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { RecentSidebar } from "./components/RecentSidebar";
import { useMemeUi } from "./context/MemeUiContext";
import { FeedPage } from "./pages/FeedPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LandingPage } from "./pages/LandingPage";
import { WorkspacePage } from "./pages/WorkspacePage";

function AppShell() {
  const { pathname } = useLocation();
  const showRecentSidebar = pathname === "/workspace";
  const { feedTick, toast } = useMemeUi();
  return (
    <div className="ref-stack">
      <Header />
      <div className={showRecentSidebar ? "ref-body ref-body--sidebar" : "ref-body"}>
        <Outlet />
      </div>
      <Footer
        feedTick={feedTick}
        className={showRecentSidebar ? "ref-footer--sidebar" : undefined}
      />
      {showRecentSidebar ? <RecentSidebar tick={feedTick} /> : null}
      {toast ? <div className="sm-toast">{toast}</div> : null}
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/workspace" element={<WorkspacePage />} />
        <Route path="/feed" element={<FeedPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/" element={<LandingPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
