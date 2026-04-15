"""Tests para los 5 calculadores laborales: IRPF, SS, Finiquito, RETA, Nómina."""

import sys

import pytest

sys.path.insert(0, "/tmp/pgk-laboral-desk/laboral-backend")

from datetime import date
from decimal import Decimal

from app.services.finiquito_calculator import FiniquitoCalculator
from app.services.irpf_calculator import IRPFCalculator
from app.services.reta_calculator import RETACalculator
from app.services.ss_calculator import SSCalculator

# === IRPF ===


class TestIRPF:
    def setup_method(self):
        self.calc = IRPFCalculator()

    def test_salario_bajo_exento(self):
        r = self.calc.calcular_retencion_mensual(900, 14, "soltero", 0, "madrid")
        assert r["exento"] is True
        assert r["retencion_mensual"] == 0.0

    def test_salario_medio_soltero(self):
        r = self.calc.calcular_retencion_mensual(2000, 14, "soltero", 0, "madrid")
        assert not r["exento"]
        assert r["tipo_retencion_pct"] > 0
        assert r["retencion_mensual"] > 0
        assert r["retencion_mensual"] < 700  # sanity

    def test_salario_con_hijos_reduce_retencion(self):
        sin_hijos = self.calc.calcular_retencion_mensual(2500, 14, "soltero", 0, "madrid")
        con_hijos = self.calc.calcular_retencion_mensual(2500, 14, "soltero", 2, "madrid")
        assert con_hijos["tipo_retencion_pct"] < sin_hijos["tipo_retencion_pct"]

    def test_salario_alto(self):
        r = self.calc.calcular_retencion_mensual(8000, 14, "casado_un_perceptor", 1, "madrid")
        assert r["tipo_retencion_pct"] > 30
        assert len(r["desglose_tramos"]) >= 4

    def test_neto_coherente(self):
        r = self.calc.calcular_neto(2000, 14, "soltero", 0, "madrid")
        assert r["salario_neto_mensual"] < 2000
        assert r["salario_neto_mensual"] > 1200
        assert abs(r["salario_neto_anual"] - r["salario_neto_mensual"] * 14) < 0.02

    def test_temporal_mayor_retencion(self):
        indef = self.calc.calcular_neto(2000, 14, "soltero", 0, "madrid", contrato_temporal=False)
        temp = self.calc.calcular_neto(2000, 14, "soltero", 0, "madrid", contrato_temporal=True)
        assert temp["tipo_ss"] > indef["tipo_ss"]

    def test_minimo_personal(self):
        r = self.calc._calcular_minimo_total("soltero", 0, 0)
        assert r == Decimal("5550")

    def test_minimo_con_hijos(self):
        r = self.calc._calcular_minimo_total("soltero", 2, 0)
        assert r == Decimal("5550") + Decimal("2400") + Decimal("2700")

    def test_reduccion_trabajo_renta_baja(self):
        # 2026: rend <= 14.852 → 7.302€; 15.000 está en tramo b)
        # 7.302 - 1,75 * (15.000 - 14.852) = 7.302 - 259.00 = 7.043,00
        r = self.calc._reduccion_trabajo(Decimal("15000"))
        assert r == Decimal("7043.00")

    def test_reduccion_trabajo_renta_alta(self):
        r = self.calc._reduccion_trabajo(Decimal("30000"))
        assert r == Decimal("0")


# === SS ===


class TestSS:
    def setup_method(self):
        self.calc = SSCalculator()

    def test_ss_trabajador_indefinido(self):
        r = self.calc.calculate(2000, "indefinido")
        assert r.trab_total > 0
        # 2026: CC 4.70% + Desempleo indef 1.55% + FP 0.10% + MEI 0.15% = 6.50%
        # 2000 * 0.065 = 130.0
        assert abs(r.trab_total - 130.0) < 2.0

    def test_ss_trabajador_temporal(self):
        r = self.calc.calculate(2000, "temporal")
        r_indef = self.calc.calculate(2000, "indefinido")
        assert r.trab_total >= r_indef.trab_total

    def test_ss_empresa(self):
        r = self.calc.calculate(2000, "indefinido")
        assert r.emp_total > 500
        assert r.emp_at_ep > 0

    def test_ss_empresa_construccion(self):
        r = self.calc.calculate(2000, "indefinido", at_ep_pct=4.3)
        r_normal = self.calc.calculate(2000, "indefinido")
        assert r.emp_at_ep > r_normal.emp_at_ep

    def test_coste_total_empresa(self):
        r = self.calc.calculate(2000, "indefinido")
        total_cost = 2000 + r.emp_total
        assert total_cost > 2500

    def test_base_topes(self):
        r = self.calc.calculate(800)
        assert r.base_cotizacion >= 1424.5  # base mínima 2026

    def test_grupo_cotizacion(self):
        grupo = self.calc._resolve_grupo("Técnico Titulado.")
        assert grupo != ""

    def test_recargo_contrato_corto(self):
        r = self.calc.calculate(2000, contract_days=15)
        assert r.recargo_contrato_corto > 0

    def test_recargo_no_aplica(self):
        r = self.calc.calculate(2000, contract_days=60)
        assert r.recargo_contrato_corto == 0.0


# === FINIQUITO ===


class TestFiniquito:
    def setup_method(self):
        self.calc = FiniquitoCalculator()

    def test_finiquito_improcedente(self):
        r = self.calc.calcular(
            2000,
            date(2022, 1, 15),
            date(2025, 4, 14),
            "improcedente",
            dias_vacaciones_pendientes=5,
            num_pagas=14,
        )
        assert r["indemnizacion"]["dias_por_ano"] == 33
        assert r["indemnizacion"]["importe"] > 0
        assert r["indemnizacion"]["exenta_irpf"] is True
        assert r["total_neto"] > 0
        assert r["vacaciones_pendientes_valor"] > 0

    def test_finiquito_objetivo(self):
        r = self.calc.calcular(1800, date(2023, 6, 1), date(2025, 4, 14), "objetivo", num_pagas=14)
        assert r["indemnizacion"]["dias_por_ano"] == 20
        assert r["indemnizacion"]["tope_meses"] == 12

    def test_finiquito_dimision_sin_indemnizacion(self):
        r = self.calc.calcular(2000, date(2023, 1, 1), date(2025, 4, 14), "dimision", num_pagas=14)
        assert r["indemnizacion"]["importe"] == 0.0

    def test_indemnizacion_tope_24_meses(self):
        r = self.calc.calcular(
            3000, date(2000, 1, 1), date(2025, 4, 14), "improcedente", num_pagas=14
        )
        assert r["indemnizacion"]["tope_aplicado"] is True
        assert r["indemnizacion"]["importe"] <= 3000 * 24

    def test_vacaciones_siempre_cotizan(self):
        r = self.calc.calcular(
            2000, date(2024, 1, 1), date(2025, 4, 14), "improcedente", dias_vacaciones_pendientes=10
        )
        assert r["base_ss"] > 0
        assert r["ss_trabajador"] > 0

    def test_tramos_reforma_2012(self):
        r = self.calc.calcular(
            2000, date(2010, 6, 1), date(2025, 4, 14), "improcedente", num_pagas=14
        )
        ind = r["indemnizacion"]
        assert ind["tipo_calculo"] == "tramos_reforma_2012"
        assert "tramo_antes_2012" in ind
        assert "tramo_despues_2012" in ind


# === RETA ===


class TestRETA:
    def setup_method(self):
        self.calc = RETACalculator()

    def test_tarifa_plana(self):
        r = self.calc.calcular_cuota(800, es_nuevo_autonomo=True, meses_alta=3)
        assert r["es_tarifa_plana"] is True
        assert r["cuota_mensual"] == 80.0

    def test_tramo_bajo(self):
        r = self.calc.calcular_cuota(600)
        assert not r["es_tarifa_plana"]
        assert r["cuota_mensual"] > 200
        assert r["cuota_mensual"] < 250

    def test_tramo_alto(self):
        r = self.calc.calcular_cuota(5000)
        assert r["cuota_mensual"] > 300

    def test_cuota_con_gastos(self):
        sin_gastos = self.calc.calcular_cuota(2000)
        con_gastos = self.calc.calcular_cuota(2000, gastos_deducibles_mensuales=500)
        assert con_gastos["cuota_mensual"] <= sin_gastos["cuota_mensual"]

    def test_comparativa_autonomo_asalariado(self):
        r = self.calc.comparar_con_asalariado(2000)
        assert r["autonomo"]["cuota_ss_mensual"] > r["asalariado"]["ss_trabajador_mensual"]
        assert r["diferencia"]["autonomo_paga_mas_mensual"] > 0

    def test_base_elegida_respetar_topes(self):
        r = self.calc.calcular_cuota(1500, base_elegida=5000)
        assert r["base_cotizacion_mensual"] <= r["base_maxima_tramo"]

    def test_tramo_correcto(self):
        r = self.calc.calcular_cuota(2000)
        assert "T" in r["tramo"]


# === NOMINA (integración) ===


class TestNomina:
    def setup_method(self):
        from app.services.nomina_calculator import NominaCalculator

        self.calc = NominaCalculator()

    def test_nomina_basica(self):
        r = self.calc.calcular_nomina(2000, 14, "soltero", 0, "madrid")
        assert r["devengos"]["total_devengado"] > 0
        assert r["deducciones"]["total_deducciones"] > 0
        assert r["liquido_percibir"] > 0
        assert r["liquido_percibir"] < 2000
        assert r["coste_empresa"]["coste_total_mensual"] > 2000

    def test_nomina_con_extras(self):
        r = self.calc.calcular_nomina(
            2000,
            14,
            "casado_un_perceptor",
            2,
            "madrid",
            plus_transporte_mensual=100,
            horas_extras_mensual=200,
        )
        assert r["devengos"]["horas_extras"] == 200.0
        assert r["devengos"]["plus_transporte_exento"] == 100.0
        assert r["liquido_percibir"] > 0

    def test_nomina_temporal_mas_ss(self):
        indef = self.calc.calcular_nomina(2000, tipo_contrato="indefinido")
        temp = self.calc.calcular_nomina(2000, tipo_contrato="temporal")
        assert (
            temp["deducciones"]["total_ss_trabajador"]
            >= indef["deducciones"]["total_ss_trabajador"]
        )

    def test_bases_nomina_presentes(self):
        r = self.calc.calcular_nomina(2000)
        assert "base_cc" in r["bases"]
        assert "base_irpf" in r["bases"]
        assert r["bases"]["base_irpf"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
