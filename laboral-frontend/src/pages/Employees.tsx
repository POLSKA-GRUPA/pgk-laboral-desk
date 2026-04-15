import React, { useEffect } from 'react';
import { Table, Button, Modal, Form, Input, Select, InputNumber, message } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useApiCall } from '../hooks/useApiCall';
import { employeesAPI } from '../services/api';
import type { Employee } from '../types';

const CONTRACT_TYPES = [
  { value: 'indefinido', label: 'Indefinido' },
  { value: 'temporal', label: 'Temporal' },
  { value: 'fijo-discontinuo', label: 'Fijo discontinuo' },
  { value: 'tiempo-parcial', label: 'Tiempo parcial' },
];

const COLUMNS = [
  { title: 'Nombre', dataIndex: 'nombre', key: 'nombre' },
  { title: 'NIF', dataIndex: 'nif', key: 'nif' },
  { title: 'Categoria', dataIndex: 'categoria', key: 'categoria' },
  { title: 'Contrato', dataIndex: 'contrato_tipo', key: 'contrato_tipo' },
  { title: 'Jornada', dataIndex: 'jornada_horas', key: 'jornada_horas', render: (v: number) => `${v}h` },
  { title: 'Estado', dataIndex: 'status', key: 'status' },
];

export default function Employees() {
  const list = useApiCall(employeesAPI.list);
  const create = useApiCall(employeesAPI.create);
  const [modalOpen, setModalOpen] = React.useState(false);
  const [form] = Form.useForm();

  useEffect(() => { list.execute(); }, []);

  const handleCreate = async (values: Record<string, unknown>) => {
    const result = await create.execute(values);
    if (result) {
      message.success('Empleado creado');
      setModalOpen(false);
      form.resetFields();
      list.execute();
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>Empleados</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          Nuevo empleado
        </Button>
      </div>
      <Table
        columns={COLUMNS}
        dataSource={list.data || []}
        rowKey="id"
        loading={list.loading}
        pagination={{ pageSize: 20 }}
      />
      <Modal title="Nuevo empleado" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="nombre" label="Nombre" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="nif" label="NIF">
            <Input />
          </Form.Item>
          <Form.Item name="categoria" label="Categoria" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="contrato_tipo" label="Tipo contrato" initialValue="indefinido">
            <Select options={CONTRACT_TYPES} />
          </Form.Item>
          <Form.Item name="jornada_horas" label="Horas semanales" initialValue={40}>
            <InputNumber min={1} max={40} />
          </Form.Item>
          <Form.Item name="fecha_inicio" label="Fecha inicio" rules={[{ required: true }]}>
            <Input placeholder="YYYY-MM-DD" />
          </Form.Item>
          <Form.Item name="salario_bruto_mensual" label="Salario bruto mensual">
            <InputNumber min={1} max={100000} style={{ width: '100%' }} addonAfter="EUR/mes" placeholder="Opcional" />
          </Form.Item>
          <Form.Item name="num_hijos" label="Num. hijos" initialValue={0}>
            <InputNumber min={0} max={20} />
          </Form.Item>
          <Form.Item name="region" label="Comunidad autonoma" initialValue="generica">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
