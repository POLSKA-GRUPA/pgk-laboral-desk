import React, { useEffect } from 'react';
import { Table, Button, Tag } from 'antd';
import { useApiCall } from '../hooks/useApiCall';
import { alertsAPI } from '../services/api';

const SEVERITY_COLORS: Record<string, string> = {
  info: 'blue',
  warning: 'orange',
  critical: 'red',
};

const COLUMNS = [
  { title: 'Tipo', dataIndex: 'alert_type', key: 'alert_type' },
  { title: 'Titulo', dataIndex: 'title', key: 'title' },
  { title: 'Trabajador', dataIndex: 'worker_name', key: 'worker_name' },
  { title: 'Fecha limite', dataIndex: 'due_date', key: 'due_date' },
  {
    title: 'Severidad',
    dataIndex: 'severity',
    key: 'severity',
    render: (s: string) => <Tag color={SEVERITY_COLORS[s] || 'default'}>{s}</Tag>,
  },
  {
    title: 'Accion',
    key: 'action',
    render: (_: unknown, r: Record<string, unknown>) => (
      <Button size="small" onClick={() => alertsAPI.dismiss(r.id as number).then(() => window.location.reload())}>
        Descartar
      </Button>
    ),
  },
];

export default function Alerts() {
  const list = useApiCall(alertsAPI.list);

  useEffect(() => { list.execute(); }, []);

  return (
    <div>
      <h2>Alertas</h2>
      <Table
        columns={COLUMNS}
        dataSource={list.data || []}
        rowKey="id"
        loading={list.loading}
      />
    </div>
  );
}
