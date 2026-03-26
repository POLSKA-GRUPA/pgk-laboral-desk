# PGK Laboral Desk

Aplicacion interna de apoyo laboral para direccion. Convierte una peticion en lenguaje natural en una lectura estructurada del caso, valida el encaje basico con el convenio colectivo cargado y genera una pre-nomina orientativa solo con importes y reglas trazables al convenio.

Estado actual: aplicacion funcional multi-convenio con calculo completo de SS, IRPF y despido.

## Objetivo de negocio

- Reducir tiempo de analisis preliminar en contratacion.
- Unificar criterio interno sobre categoria, jornada, modalidad y base retributiva.
- Generar una respuesta operativa trazable antes de pasar a revision juridico-laboral final.
- Separar la capa de convenio de la capa de Seguridad Social, IRPF, extranjeria y fiscalidad internacional.

## Alcance actual

- Interpreta consultas en lenguaje natural (sin IA externa, solo reglas + keywords).
- Detecta categoria profesional probable dentro del convenio cargado.
- Detecta jornada, pagas extra, antiguedad y modalidad contractual.
- Calcula Seguridad Social (empresa + trabajador) con tasas 2026.
- Estima IRPF con escalas estatal + autonomica (Madrid, Cataluna, Andalucia, Valencia).
- Calcula coste de despido/extincion con consejo estrategico.
- Genera pre-nomina orientativa en PDF/HTML.
- Soporte multi-convenio (acuaticas, oficinas y despachos, etc.).
- Gestion de plantilla de trabajadores con alertas automaticas.

## Arquitectura

```
pgk-laboral-desk/
|-- app.py                  Flask server + API JSON (879 lines)
|-- engine.py               Motor determinista de calculo laboral
|-- ss_calculator.py        Cotizaciones Seguridad Social 2026
|-- irpf_estimator.py       Estimacion IRPF estatal + autonomico
|-- chat_parser.py          Parser conversacional (reglas + keywords)
|-- database.py             Gestion SQLite (users, employees, alerts)
|-- nomina_pdf.py           Generacion de pre-nomina PDF/HTML
|-- client_manager.py       Gestion multi-cliente/multi-convenio
|-- convenio_verifier.py    Verificacion de vigencia via Perplexity
|-- rates_verifier.py       Verificacion de tasas SS/IRPF/SMI
|-- exceptions.py           Jerarquia de excepciones del dominio
|-- validation.py           Validacion de entradas de la API
|-- logging_config.py       Logging estructurado (JSON/human)
|-- test_engine.py          Suite de tests (30+ tests)
|-- data/
|   |-- convenio_*.json     Convenios colectivos estructurados
|   |-- ss_config.json      Configuracion tasas SS 2026
|   +-- categorias_detalle.json
|-- static/                 Frontend (HTML/CSS/JS)
+-- .github/workflows/
    |-- ci.yml              Lint + tests (Python 3.11/3.12)
    +-- deploy.yml          Deploy via SSH
```

Documentacion complementaria:

- [Arquitectura](docs/ARQUITECTURA.md)
- [Operacion y limites](docs/OPERACION_Y_LIMITES.md)

## Requisitos

- Python 3.11 o superior
- Dependencias de sistema para WeasyPrint (libpango, libgdk-pixbuf)

## Desarrollo

```bash
# Instalar dependencias
pip install -r requirements.txt -r requirements-dev.txt

# Arrancar servidor
python app.py --debug

# Ejecutar tests
python -m pytest test_engine.py -v

# Lint
pip install ruff
ruff check .
ruff format --check .
```

La aplicacion queda disponible en `http://127.0.0.1:8765`.

## API

### Health check

```http
GET /api/health
```

Respuesta:

```json
{
  "ok": true,
  "version": "0.2.0",
  "checks": {
    "convenios": {"ok": true, "count": 2},
    "database": {"ok": true}
  }
}
```

### Simulacion de coste

```http
POST /api/simulate
Content-Type: application/json
```

```json
{
  "category": "Nivel B.",
  "contract_type": "indefinido",
  "weekly_hours": 40,
  "region": "madrid"
}
```

### Chat conversacional

```http
POST /api/chat
Content-Type: application/json
```

```json
{"message": "Quiero contratar un socorrista nivel B fijo discontinuo a 40 horas semanales para verano."}
```

### Calculo de despido

```http
POST /api/despido
Content-Type: application/json
```

```json
{
  "tipo_despido": "improcedente",
  "fecha_inicio": "2023-01-15",
  "salario_bruto_mensual": 1500
}
```

## Datos y trazabilidad

- Convenios cargados en `data/convenio_*.json`
- Origen de datos: paquete BOE trabajado internamente
- Tasas SS 2026 en `data/ss_config.json` (verificadas via Perplexity)
- Las respuestas del motor se apoyan en articulos y anexos ya estructurados dentro del JSON

## Criterio juridico-operativo

Esta herramienta no sustituye la validacion profesional final. La salida debe entenderse como:

- lectura preliminar del caso
- pre-dictamen laboral interno
- pre-nomina orientativa

La decision final sobre contrato, nomina, extranjeria, Seguridad Social y fiscalidad debe cerrarse en expediente profesional separado.

## Hoja de ruta

1. Generacion de oferta y borrador contractual.
2. Expediente de extranjeria enlazado.
3. Exportacion masiva de nominas.
4. Dashboard de costes por departamento.
5. Integracion con sistema contable.
