import React from 'react';
import { Button, Space } from 'antd';
import { LogoutOutlined, UserOutlined } from '@ant-design/icons';
import type { User } from '../types';

interface Props {
  user: User | null;
  onLogout: () => void;
}

export default function TopBar({ user, onLogout }: Props) {
  return (
    <div className="topbar">
      <div className="topbar-title">PGK Laboral Desk v3.0</div>
      <Space>
        <span><UserOutlined /> {user?.full_name || user?.username}</span>
        <Button type="text" icon={<LogoutOutlined />} onClick={onLogout}>
          Salir
        </Button>
      </Space>
    </div>
  );
}
