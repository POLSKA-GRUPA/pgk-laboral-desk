import React, { useEffect, useState } from 'react';
import { Card, Form, Input, Button, message, Spin } from 'antd';
import { authAPI } from '../services/api';

export default function Settings() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    authAPI.me().then((res) => {
      const u = res.data;
      form.setFieldsValue({
        empresa_nombre: u.empresa_nombre || '',
        empresa_cif: u.empresa_cif || '',
        empresa_domicilio: u.empresa_domicilio || '',
        empresa_ccc: u.empresa_ccc || '',
      });
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });
  }, [form]);

  const handleSave = async (values: Record<string, string>) => {
    setSaving(true);
    try {
      await authAPI.updateMe(values);
      message.success('Configuracion guardada');
    } catch {
      message.error('Error al guardar la configuracion');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div>
      <h2>Configuracion</h2>
      <Card>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="empresa_nombre" label="Nombre empresa">
            <Input />
          </Form.Item>
          <Form.Item name="empresa_cif" label="CIF">
            <Input />
          </Form.Item>
          <Form.Item name="empresa_domicilio" label="Domicilio">
            <Input />
          </Form.Item>
          <Form.Item name="empresa_ccc" label="Codigo Cuenta Cotizacion">
            <Input />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={saving}>Guardar</Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
