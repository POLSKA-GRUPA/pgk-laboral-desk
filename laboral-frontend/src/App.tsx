import React, { useState } from 'react';
import { ConfigProvider, theme as antdTheme } from 'antd';
import esES from 'antd/locale/es_ES';
import { useAuth } from './hooks/useAuth';
import ErrorBoundary from './components/ErrorBoundary';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import Dashboard from './pages/Dashboard';
import Employees from './pages/Employees';
import Simulation from './pages/Simulation';
import Chat from './pages/Chat';
import Convenios from './pages/Convenios';
import Alerts from './pages/Alerts';
import Payroll from './pages/Payroll';
import Dismissal from './pages/Dismissal';
import Settings from './pages/Settings';
import { LoginForm } from './components/LoginForm';
import './styles/index.css';

const PAGES: Record<string, React.FC> = {
  dashboard: Dashboard,
  employees: Employees,
  simulation: Simulation,
  chat: Chat,
  convenios: Convenios,
  alerts: Alerts,
  payroll: Payroll,
  dismissal: Dismissal,
  settings: Settings,
};

export default function App() {
  const { user, loading, isAuthenticated, login, logout } = useAuth();
  const [currentPage, setCurrentPage] = useState('dashboard');

  if (loading) {
    return <div className="app-loading">Cargando...</div>;
  }

  if (!isAuthenticated) {
    return (
      <ConfigProvider locale={esES}>
        <LoginForm onLogin={login} />
      </ConfigProvider>
    );
  }

  const PageComponent = PAGES[currentPage] || Dashboard;

  return (
    <ConfigProvider
      locale={esES}
      theme={{
        algorithm: antdTheme.darkAlgorithm,
        token: {
          colorPrimary: '#DCCBB3',
          colorBgContainer: '#0D4F4F',
          colorBgElevated: '#0D4F4F',
          colorBgLayout: '#092E2E',
          colorText: '#F2F1ED',
          colorBorder: '#1A6B6B',
          borderRadius: 8,
        },
      }}
    >
      <div className="app-layout">
        <Sidebar currentPage={currentPage} onNavigate={setCurrentPage} />
        <div className="app-main">
          <TopBar user={user} onLogout={logout} />
          <div className="app-content">
            <ErrorBoundary key={currentPage}>
              <PageComponent />
            </ErrorBoundary>
          </div>
        </div>
      </div>
    </ConfigProvider>
  );
}

export { PAGES };
