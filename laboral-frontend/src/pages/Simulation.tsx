import React, { useState, useEffect } from 'react';
import { Card, Form, Select, InputNumber, Button, Descriptions, Spin, Divider } from 'antd';
import { useApiCall } from '../hooks/useApiCall';
import { simulationAPI, referenceAPI } from '../services/api';

const REGIONS = [
  { value: 'generica', label: 'Generica' },
  { value: 'madrid', label: 'Madrid' },
  { value: 'cataluna', label: 'Cataluna' },
  { value: 'andalucia', label: 'Andalucia' },
  { value: 'valencia', label: 'C. Valenciana' },
];

export default function Simulation() {
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [categories, setCategories] = useState<{ value: string; label: string }[]>([]);
  const sim = useApiCall(simulationAPI.run);
  const cats = useApiCall(referenceAPI.categories);
  const [form] = Form.useForm();

  useEffect(() => {
    cats.execute().then((res) => {
      if (res && Array.isArray(res)) {
        setCategories(res as { value: string; label: string }[]);
      }
    });
  }, []);

  const handleSimulate = async (values: Record<string, unknown>) => {
    const res = await sim.execute(values);
    if (res) setResult(res as unknown as Record<string, unknown>);
  };

  return (
    <div>
      <h2>Simulador de coste laboral</h2>
      <Card style={{ marginBottom: 24 }}>
        <Form form={form} layout="inline" onFinish={handleSimulate} initialValues={{ contract_type: 'indefinido', weekly_hours: 40, region: 'generica' }}>
          <Form.Item name="category" rules={[{ required: true }]}>
            <Select
              options={categories}
              placeholder="Categoria"
              style={{ width: 200 }}
              loading={cats.loading}
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </Form.Item>
          <Form.Item name="contract_type">
            <Select style={{ width: 150 }} options={[
              { value: 'indefinido', label: 'Indefinido' },
              { value: 'temporal', label: 'Temporal' },
              { value: 'fijo-discontinuo', label: 'Fijo discontinuo' },
            ]} />
          </Form.Item>
          <Form.Item name="weekly_hours">
            <InputNumber min={1} max={40} addonAfter="h/semana" />
          </Form.Item>
          <Form.Item name="region">
            <Select options={REGIONS} style={{ width: 150 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={sim.loading}>Calcular</Button>
          </Form.Item>
        </Form>
      </Card>
      {sim.loading && <Spin size="large" />}
      {result && (
        <Card title="Resultado">
          <Descriptions column={2} bordered>
            <Descriptions.Item label="Categoria">{result.categoria}</Descriptions.Item>
            <Descriptions.Item label="Salario bruto mensual">{Number(result.salario_bruto_mensual).toFixed(2)} EUR</Descriptions.Item>
            <Descriptions.Item label="Coste empresa/mes">{Number(result.coste_total_empresa_mes_eur).toFixed(2)} EUR</Descriptions.Item>
            <Descriptions.Item label="Coste empresa/ano">{Number(result.coste_total_empresa_anual_eur).toFixed(2)} EUR</Descriptions.Item>
            <Descriptions.Item label="Neto trabajador">{Number(result.neto_trabajador_mes_eur).toFixed(2)} EUR</Descriptions.Item>
          </Descriptions>
        </Card>
      )}
    </div>
  );
}
