export interface User {
  id: number;
  username: string;
  email?: string;
  full_name: string;
  empresa_nombre: string;
  empresa_cif: string;
  convenio_id: string;
  role: 'admin' | 'client';
  is_active: boolean;
}

export interface Employee {
  id: number;
  nombre: string;
  nif: string;
  naf: string;
  categoria: string;
  contrato_tipo: string;
  jornada_horas: number;
  fecha_inicio: string;
  fecha_fin?: string;
  salario_bruto_mensual?: number;
  num_hijos: number;
  region: string;
  status: 'activo' | 'baja';
}

export interface SimulationResult {
  categoria: string;
  salario_bruto_mensual: number;
  coste_total_empresa_mes_eur: number;
  coste_total_empresa_anual_eur: number;
  neto_trabajador_mes_eur: number;
  desglose_ss: Record<string, unknown>;
  desglose_irpf: Record<string, unknown>;
  traces: string[];
}

export interface Convenio {
  id: number;
  nombre: string;
  codigo_convenio: string;
  ambito_geografico: string;
  vigencia_inicio?: string;
  vigencia_fin?: string;
  sector: string;
  activo: boolean;
}

export interface Alert {
  id: number;
  alert_type: string;
  title: string;
  description: string;
  due_date: string;
  worker_name: string;
  severity: 'info' | 'warning' | 'critical';
  status: 'pending' | 'resolved';
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface NominaResult {
  employee_id: number;
  periodo: string;
  devengos: Record<string, unknown>;
  deducciones: Record<string, unknown>;
  neto: number;
  coste_empresa: number;
}

export interface DismissalResult {
  tipo: string;
  indemnizacion_eur: number;
  dias_indemnizacion: number;
  salario_diario: number;
  detalle: Record<string, unknown>;
  consejo?: string;
}

export interface HealthCheck {
  ok: boolean;
  version: string;
  checks: Record<string, { ok: boolean }>;
}
