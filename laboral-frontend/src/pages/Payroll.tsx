import React from 'react';
import { Card, Form, Select, Input, Button, Descriptions, Spin, message } from 'antd';
import { useApiCall } from '../hooks/useApiCall';
import { payrollAPI } from '../services/api';

export default function Payroll() {
  const generate = useApiCall(payrollAPI.generate);
  const [form] = Form.useForm();

  const handleGenerate = async (values: Record<string, unknown>) => {
    const result = await generate.execute(values);
    if (result) message.success('Nomina generada');
  };

  return (
    <div>
      <h2>Generacion de nominas</h2>
      <Card style={{ marginBottom: 24 }}>
        <Form form={form} layout="inline" onFinish={handleGenerate}>
          <Form.Item name="employee_id" label="Empleado" rules={[{ required: true }]}>
            <Input type="number" placeholder="ID empleado" />
          </Form.Item>
          <Form.Item name="periodo" label="Periodo" rules={[{ required: true }]}>
            <Input placeholder="YYYY-MM" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={generate.loading}>
              Generar nomina
            </Button>
          </Form.Item>
        </Form>
      </Card>
      {generate.loading && <Spin size="large" />}
      {generate.data && (
        <Card title="Resultado nomina">
          <Descriptions column={2} bordered>
            <Descriptions.Item label="Neto">{Number(generate.data.neto).toFixed(2)} EUR</Descriptions.Item>
            <Descriptions.Item label="Coste empresa">{Number(generate.data.coste_empresa).toFixed(2)} EUR</Descriptions.Item>
          </Descriptions>
        </Card>
      )}
    </div>
  );
}
