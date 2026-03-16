import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import AuthLayout from "./layouts/AuthLayout";
import LoginLanding from "./pages/auth/LoginLanding";
import SignIn from "./pages/auth/SignIn";
import SignUp from "./pages/auth/SignUp";
import Terms from "./pages/auth/Terms";
import Dashboard from "./pages/Dashboard";
import { LayoutProvider, useLayout } from "./lib/layout";
import { TwsProvider } from "./lib/tws";
import { TabProvider } from "./lib/tabs";

function LayoutGate({ children }: { children: React.ReactNode }) {
  const { ready } = useLayout();
  if (!ready) return null;
  return <>{children}</>;
}

function AppRoutes() {
  const { session, loading } = useAuth();

  if (loading) return null;

  if (session) {
    return (
      <LayoutProvider>
        <TwsProvider>
          <LayoutGate>
              <TabProvider>
                <Routes>
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="*" element={<Navigate to="/dashboard" replace />} />
                </Routes>
              </TabProvider>
          </LayoutGate>
        </TwsProvider>
      </LayoutProvider>
    );
  }

  return (
    <Routes>
      <Route element={<AuthLayout />}>
        <Route path="/" element={<LoginLanding />} />
        <Route path="/signin" element={<SignIn />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/terms" element={<Terms />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
