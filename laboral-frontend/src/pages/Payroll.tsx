import React, { useState } from 'react';
import { Card, Form, Input, InputNumber, Button, Descriptions, Spin, message, Alert, Table } from 'antd';
import { useApiCall } from '../hooks/useApiCall';
import { payrollAPI } from '../services/api';

export default function Payroll() {
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const generate = useApiCall(payrollAPI.generate);
  const [form] = Form.useForm();

  const handleGenerate = async (values: Record<string, unknown>) => {
    setResult(null);
    const res = await generate.execute(values);
    if (res) {
      setResult(res as unknown as Record<string, unknown>);
      message.success('Nomina generada');
    }
  };

  const devengos = result?.devengos as Record<string, unknown>[] | undefined;

  return (
    <div>
      <h2>Generacion de nominas</h2>
      <Card style={{ marginBottom: 24 }}>
        <Form form={form} layout="inline" onFinish={handleGenerate}>
          <Form.Item name="employee_id" label="Empleado" rules={[{ required: true }]}>
            <InputNumber min={1} placeholder="ID empleado" style={{ width: 120 }} />
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
      {generate.error && (
        <Alert type="error" message="Error" description={generate.error} showIcon style={{ marginBottom: 16 }} />
      )}
      {result && (
        <Card title="Resultado nomina">
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="Neto trabajador">{Number(result.neto).toFixed(2)} EUR</Descriptions.Item>
            <Descriptions.Item label="Coste empresa">{Number(result.coste_empresa).toFixed(2)} EUR</Descriptions.Item>
          </Descriptions>
          {Array.isArray(devengos) && devengos.length > 0 && (
            <Table
              style={{ marginTop: 16 }}
              size="small"
              pagination={false}
              dataSource={devengos.map((d, i) => ({ ...d, key: i }))}
              columns={[
                { title: 'Concepto', dataIndex: 'concepto', key: 'concepto' },
                { title: 'Importe', dataIndex: 'eur', key: 'eur', render: (v: number) => `${Number(v).toFixed(2)} EUR` },
                { title: 'Fuente', dataIndex: 'fuente', key: 'fuente' },
              ]}
            />
          )}
        </Card>
      )}
    </div>
  );
}
