import React, { useEffect } from 'react';
import { Table, Tag } from 'antd';
import { useApiCall } from '../hooks/useApiCall';
import { conveniosAPI } from '../services/api';

const COLUMNS = [
  { title: 'Nombre', dataIndex: 'nombre', key: 'nombre' },
  { title: 'Codigo', dataIndex: 'codigo_convenio', key: 'codigo_convenio' },
  { title: 'Ambito', dataIndex: 'ambito_geografico', key: 'ambito_geografico' },
  { title: 'Sector', dataIndex: 'sector', key: 'sector' },
  {
    title: 'Vigencia',
    key: 'vigencia',
    render: (_: unknown, r: Record<string, string>) => `${r.vigencia_inicio || '?'} - ${r.vigencia_fin || '?'}`,
  },
  {
    title: 'Estado',
    dataIndex: 'activo',
    key: 'activo',
    render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? 'Activo' : 'Inactivo'}</Tag>,
  },
];

export default function Convenios() {
  const list = useApiCall(conveniosAPI.list);

  useEffect(() => { list.execute(); }, []);

  return (
    <div>
      <h2>Convenios Colectivos</h2>
      <Table
        columns={COLUMNS}
        dataSource={list.data || []}
        rowKey="codigo_convenio"
        loading={list.loading}
      />
    </div>
  );
}
