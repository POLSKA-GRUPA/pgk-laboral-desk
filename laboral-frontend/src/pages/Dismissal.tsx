import React from 'react';
import { Card, Form, Select, Input, InputNumber, Button, Descriptions, Spin, message } from 'antd';
import { useApiCall } from '../hooks/useApiCall';
import { dismissalAPI } from '../services/api';

const DESPIDO_TYPES = [
  { value: 'improcedente', label: 'Improcedente' },
  { value: 'objetivo', label: 'Objetivo' },
  { value: 'disciplinario', label: 'Disciplinario' },
  { value: 'mutuo_acuerdo', label: 'Mutuo acuerdo' },
  { value: 'ere', label: 'ERE' },
  { value: 'fin_contrato_temporal', label: 'Fin contrato temporal' },
];

export default function Dismissal() {
  const calc = useApiCall(dismissalAPI.calculate);
  const [form] = Form.useForm();

  const handleCalculate = async (values: Record<string, unknown>) => {
    const result = await calc.execute(values);
    if (result) message.success('Calculo completado');
  };

  return (
    <div>
      <h2>Calculadora de despido</h2>
      <Card style={{ marginBottom: 24 }}>
        <Form form={form} layout="inline" onFinish={handleCalculate} initialValues={{ tipo_despido: 'improcedente' }}>
          <Form.Item name="tipo_despido" rules={[{ required: true }]}>
            <Select options={DESPIDO_TYPES} style={{ width: 200 }} />
          </Form.Item>
          <Form.Item name="fecha_inicio" rules={[{ required: true }]}>
            <Input placeholder="Fecha inicio (YYYY-MM-DD)" />
          </Form.Item>
          <Form.Item name="salario_bruto_mensual" rules={[{ required: true }]}>
            <InputNumber min={0} addonAfter="EUR/mes" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={calc.loading}>Calcular</Button>
          </Form.Item>
        </Form>
      </Card>
      {calc.loading && <Spin size="large" />}
      {calc.data && (
        <Card title="Resultado">
          <Descriptions column={2} bordered>
            <Descriptions.Item label="Tipo">{calc.data.tipo}</Descriptions.Item>
            <Descriptions.Item label="Indemnizacion">{Number(calc.data.indemnizacion_eur).toFixed(2)} EUR</Descriptions.Item>
            <Descriptions.Item label="Dias indemnizacion">{calc.data.dias_indemnizacion}</Descriptions.Item>
            <Descriptions.Item label="Salario diario">{Number(calc.data.salario_diario).toFixed(2)} EUR</Descriptions.Item>
          </Descriptions>
          {calc.data.consejo && (
            <Card style={{ marginTop: 16 }} type="inner" title="Consejo estrategico">
              {calc.data.consejo}
            </Card>
          )}
        </Card>
      )}
    </div>
  );
}
