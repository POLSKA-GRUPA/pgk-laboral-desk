import React, { useState, useEffect } from 'react';
import { Card, Form, Select, Input, InputNumber, Button, Descriptions, Spin, message, Alert } from 'antd';
import { useApiCall } from '../hooks/useApiCall';
import { dismissalAPI, referenceAPI } from '../services/api';

export default function Dismissal() {
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [despidoTypes, setDespidoTypes] = useState<{ value: string; label: string }[]>([]);
  const calc = useApiCall(dismissalAPI.calculate);
  const tipos = useApiCall(referenceAPI.tiposDespido);
  const [form] = Form.useForm();

  useEffect(() => {
    tipos.execute().then((res) => {
      if (res && Array.isArray(res)) {
        setDespidoTypes(res as { value: string; label: string }[]);
      }
    });
  }, []);

  const handleCalculate = async (values: Record<string, unknown>) => {
    setResult(null);
    const res = await calc.execute(values);
    if (res) {
      setResult(res as unknown as Record<string, unknown>);
      message.success('Calculo completado');
    }
  };

  const finiquito = result?.finiquito as Record<string, unknown> | undefined;
  const escenarios = result?.escenarios as Record<string, unknown> | undefined;
  const consejo = result?.consejo as string[] | undefined;

  return (
    <div>
      <h2>Calculadora de despido</h2>
      <Card style={{ marginBottom: 24 }}>
        <Form form={form} layout="inline" onFinish={handleCalculate} initialValues={{ tipo_despido: 'improcedente' }}>
          <Form.Item name="tipo_despido" rules={[{ required: true }]}>
            <Select
              options={despidoTypes}
              placeholder="Tipo despido"
              style={{ width: 220 }}
              loading={tipos.loading}
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </Form.Item>
          <Form.Item name="fecha_inicio" rules={[{ required: true }]}>
            <Input placeholder="Fecha inicio (YYYY-MM-DD)" />
          </Form.Item>
          <Form.Item name="salario_bruto_mensual" rules={[{ required: true }]}>
            <InputNumber min={1} placeholder="Salario" style={{ width: 150 }} addonAfter="EUR/mes" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={calc.loading}>Calcular</Button>
          </Form.Item>
        </Form>
      </Card>
      {calc.loading && <Spin size="large" />}
      {calc.error && (
        <Alert type="error" message="Error" description={calc.error} showIcon style={{ marginBottom: 16 }} />
      )}
      {result && (
        <>
          <Card title="Resultado del despido">
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="Tipo">{result.tipo_despido_label as string}</Descriptions.Item>
              <Descriptions.Item label="Antiguedad">{Number(result.antiguedad_anos).toFixed(2)} anos ({result.antiguedad_dias as number} dias)</Descriptions.Item>
              <Descriptions.Item label="Salario bruto mensual">{Number(result.salario_bruto_mensual_eur).toFixed(2)} EUR</Descriptions.Item>
              <Descriptions.Item label="Salario diario">{Number(result.salario_diario_eur).toFixed(2)} EUR</Descriptions.Item>
              <Descriptions.Item label="Indemnizacion">{Number(result.indemnizacion_eur).toFixed(2)} EUR</Descriptions.Item>
              <Descriptions.Item label="Total (indemnizacion + finiquito)">{Number(result.total_eur).toFixed(2)} EUR</Descriptions.Item>
            </Descriptions>
            {result.indemnizacion_calculo && (
              <p style={{ marginTop: 8, color: '#888', fontSize: 12 }}>{result.indemnizacion_calculo as string}</p>
            )}
          </Card>

          {finiquito && (
            <Card title="Finiquito desglosado" style={{ marginTop: 16 }}>
              <Descriptions column={2} bordered size="small">
                <Descriptions.Item label="Salario dias pendientes">{Number(finiquito.salario_dias_pendientes_eur).toFixed(2)} EUR ({finiquito.salario_dias_pendientes_n as number} dias)</Descriptions.Item>
                <Descriptions.Item label="Parte proporcional pagas extra">{Number(finiquito.parte_proporcional_pagas_eur).toFixed(2)} EUR</Descriptions.Item>
                <Descriptions.Item label="Vacaciones pendientes">{Number(finiquito.vacaciones_pendientes_eur).toFixed(2)} EUR ({finiquito.vacaciones_pendientes_dias as number} dias)</Descriptions.Item>
                <Descriptions.Item label="Preaviso pendiente">{Number(finiquito.preaviso_pendiente_eur).toFixed(2)} EUR</Descriptions.Item>
                <Descriptions.Item label="Total finiquito">{Number(finiquito.total_finiquito_eur).toFixed(2)} EUR</Descriptions.Item>
              </Descriptions>
            </Card>
          )}

          {escenarios && (
            <Card title="Comparativa escenarios" style={{ marginTop: 16 }}>
              <Descriptions column={3} bordered size="small">
                <Descriptions.Item label="Objetivo">{Number(escenarios.objetivo_eur).toFixed(2)} EUR</Descriptions.Item>
                <Descriptions.Item label="Improcedente">{Number(escenarios.improcedente_eur).toFixed(2)} EUR</Descriptions.Item>
                <Descriptions.Item label="Fin temporal">{Number(escenarios.fin_temporal_eur).toFixed(2)} EUR</Descriptions.Item>
              </Descriptions>
            </Card>
          )}

          {consejo && consejo.length > 0 && (
            <Card style={{ marginTop: 16 }} type="inner" title="Consejo estrategico">
              <ul style={{ paddingLeft: 20, margin: 0 }}>
                {consejo.map((c: string, i: number) => (
                  <li key={i} style={{ marginBottom: 8 }}>{c}</li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
