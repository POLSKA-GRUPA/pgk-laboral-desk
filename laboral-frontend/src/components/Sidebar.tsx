import React from 'react';
import { Menu } from 'antd';
import {
  DashboardOutlined,
  TeamOutlined,
  CalculatorOutlined,
  MessageOutlined,
  BookOutlined,
  BellOutlined,
  FileTextOutlined,
  WarningOutlined,
  SettingOutlined,
} from '@ant-design/icons';

interface Props {
  currentPage: string;
  onNavigate: (page: string) => void;
}

const MENU_ITEMS = [
  { key: 'dashboard', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: 'employees', icon: <TeamOutlined />, label: 'Empleados' },
  { key: 'simulation', icon: <CalculatorOutlined />, label: 'Simulador' },
  { key: 'payroll', icon: <FileTextOutlined />, label: 'Nominas' },
  { key: 'dismissal', icon: <WarningOutlined />, label: 'Despidos' },
  { key: 'chat', icon: <MessageOutlined />, label: 'Chat' },
  { key: 'convenios', icon: <BookOutlined />, label: 'Convenios' },
  { key: 'alerts', icon: <BellOutlined />, label: 'Alertas' },
  { key: 'settings', icon: <SettingOutlined />, label: 'Configuracion' },
];

export default function Sidebar({ currentPage, onNavigate }: Props) {
  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <h2>PGK Laboral</h2>
      </div>
      <Menu
        mode="inline"
        selectedKeys={[currentPage]}
        items={MENU_ITEMS}
        onClick={({ key }) => onNavigate(key)}
        style={{ border: 'none', background: 'transparent' }}
      />
    </div>
  );
}
