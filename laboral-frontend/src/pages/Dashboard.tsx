import React from 'react';
import { Card, Row, Col, Statistic } from 'antd';
import { TeamOutlined, DollarOutlined, BellOutlined, BookOutlined } from '@ant-design/icons';
import { useApiCall } from '../hooks/useApiCall';
import { employeesAPI, alertsAPI, conveniosAPI } from '../services/api';

interface EmployeeData {
  salario_bruto_mensual?: number;
  [key: string]: unknown;
}

export default function Dashboard() {
  const employees = useApiCall(employeesAPI.list);
  const alerts = useApiCall(alertsAPI.list);
  const convenios = useApiCall(conveniosAPI.list);

  React.useEffect(() => {
    employees.execute();
    alerts.execute();
    convenios.execute();
  }, []);

  const costeMensual = React.useMemo(() => {
    if (!employees.data || !Array.isArray(employees.data)) return 0;
    return (employees.data as EmployeeData[]).reduce(
      (sum, emp) => sum + (emp.salario_bruto_mensual ?? 0),
      0
    );
  }, [employees.data]);

  return (
    <div>
      <h2>Dashboard</h2>
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card>
            <Statistic title="Empleados activos" value={employees.data?.length ?? 0} prefix={<TeamOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Coste mensual" value={costeMensual.toFixed(2)} prefix={<DollarOutlined />} suffix="EUR" />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Alertas pendientes" value={alerts.data?.length ?? 0} prefix={<BellOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Convenios" value={convenios.data?.length ?? 0} prefix={<BookOutlined />} />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
