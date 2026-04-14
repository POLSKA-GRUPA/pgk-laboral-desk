import React from 'react';
import { Card, Form, Input, Button, message } from 'antd';

export default function Settings() {
  const handleSave = (values: Record<string, string>) => {
    message.success('Configuracion guardada');
  };

  return (
    <div>
      <h2>Configuracion</h2>
      <Card>
        <Form layout="vertical" onFinish={handleSave} initialValues={{ empresa_nombre: '', empresa_cif: '' }}>
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
            <Button type="primary" htmlType="submit">Guardar</Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
