import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { Header } from "./components/Header";
import { RecentSidebar } from "./components/RecentSidebar";
import { useMemeUi } from "./context/MemeUiContext";
import { FeedPage } from "./pages/FeedPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LandingPage } from "./pages/LandingPage";
import { WorkspacePage } from "./pages/WorkspacePage";

function AppShell() {
  const { feedTick } = useMemeUi();
  return (
    <div className="ref-stack">
      <Header />
      <div className="ref-body">
        <Outlet />
      </div>
      <RecentSidebar tick={feedTick} />
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
