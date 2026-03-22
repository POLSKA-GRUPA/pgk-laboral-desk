# PGK Laboral Desk

Aplicacion interna de apoyo laboral para direccion. Convierte una peticion en lenguaje natural en una lectura estructurada del caso, valida el encaje basico con el convenio colectivo cargado y genera una pre-nomina orientativa solo con importes y reglas trazables al convenio.

Estado actual: prototipo funcional de escritorio, centrado en el convenio colectivo estatal de mantenimiento y conservacion de instalaciones acuaticas.

## Objetivo de negocio

- Reducir tiempo de analisis preliminar en contratacion.
- Unificar criterio interno sobre categoria, jornada, modalidad y base retributiva.
- Generar una respuesta operativa trazable antes de pasar a revision juridico-laboral final.
- Separar la capa de convenio de la capa de Seguridad Social, IRPF, extranjeria y fiscalidad internacional.

## Alcance actual

- Interpreta consultas en lenguaje natural.
- Detecta categoria profesional probable dentro del convenio cargado.
- Detecta jornada, pagas extra, antiguedad y modalidad contractual.
- Advierte cuando el fijo-discontinuo no puede cerrarse con los datos aportados.
- Devuelve condiciones relevantes del convenio por bloques tematicos.
- Genera una pre-nomina orientativa del mes activo solo con devengos convencionales.

## Fuera de alcance en esta version

- Calculo de deducciones de Seguridad Social.
- Calculo de IRPF.
- Gestion documental de extranjeria.
- Multi-convenio.
- Persistencia de expedientes.
- Validacion formal para emision automatica de contrato o nomina definitiva.

## Arquitectura

- `engine.py`: motor determinista de lectura y calculo.
- `app.py`: servidor HTTP local y API JSON minima.
- `static/index.html`: interfaz principal.
- `static/styles.css`: sistema visual de direccion.
- `static/app.js`: consumo de API y renderizado del dashboard.
- `data/convenio_acuaticas_2025_2027.json`: base convencional estructurada.
- `test_engine.py`: pruebas del motor.

Documentacion complementaria:

- [Arquitectura](docs/ARQUITECTURA.md)
- [Operacion y limites](docs/OPERACION_Y_LIMITES.md)

## Requisitos

- Python 3.11 o superior
- `pytest` para ejecutar pruebas
- macOS si se quiere usar `start.command`

## Arranque local

```bash
cd "/Users/kenyi/barra programa convenios/pgk-laboral-assistant"
python3 app.py
```

O bien:

```bash
./start.command
```

La aplicacion queda disponible en `http://127.0.0.1:8765`.

## Pruebas

```bash
cd "/Users/kenyi/barra programa convenios/pgk-laboral-assistant"
python3 -m pytest test_engine.py -q
python3 -m py_compile app.py engine.py
```

## API local

### Salud

```http
GET /api/health
```

Respuesta:

```json
{"ok": true}
```

### Analisis

```http
POST /api/analyze
Content-Type: application/json
```

Cuerpo:

```json
{"query": "Quiero contratar un socorrista nivel B fijo discontinuo a 40 horas semanales para verano."}
```

## Datos y trazabilidad

- Convenio cargado: `data/convenio_acuaticas_2025_2027.json`
- Origen de datos: paquete BOE trabajado internamente a partir del documento `BOE-A-2026-5849`
- Las respuestas del motor se apoyan en articulos y anexos ya estructurados dentro del JSON

## Criterio juridico-operativo

Esta herramienta no sustituye la validacion profesional final. La salida debe entenderse como:

- lectura preliminar del caso
- pre-dictamen laboral interno
- pre-nomina orientativa

La decision final sobre contrato, nomina, extranjeria, Seguridad Social y fiscalidad debe cerrarse en expediente profesional separado.

## Hoja de ruta recomendada

1. Soporte multi-convenio.
2. Parametrizacion de cotizacion e IRPF.
3. Generacion de oferta y borrador contractual.
4. Expediente de extranjeria enlazado.
5. Historial de consultas y exportacion PDF.
