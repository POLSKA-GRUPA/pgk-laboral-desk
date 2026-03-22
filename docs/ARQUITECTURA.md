# Arquitectura

## Vision general

PGK Laboral Desk esta construido como aplicacion local ligera, sin dependencias de backend externo ni modelo generativo en runtime. El objetivo es que cada salida sea reproducible, trazable y auditable frente al convenio cargado.

## Componentes

### 1. Motor

Archivo: `engine.py`

Responsabilidades:

- normalizar el texto libre de entrada
- detectar categoria, jornada, modalidad, antiguedad y pagas
- decidir si hay datos suficientes para cerrar la pre-nomina
- construir la respuesta operativa
- seleccionar las condiciones del convenio relevantes para la interfaz

Principio clave:

- no inventar categorias, reglas ni importes fuera del dataset cargado

### 2. Servidor local

Archivo: `app.py`

Responsabilidades:

- servir la interfaz estatica
- exponer `GET /api/health`
- exponer `POST /api/analyze`
- desactivar cache en respuestas y assets para evitar incoherencias visuales durante trabajo interno

### 3. Interfaz

Archivos:

- `static/index.html`
- `static/styles.css`
- `static/app.js`

Responsabilidades:

- recoger la consulta de direccion
- mostrar lectura estructurada del caso
- renderizar conclusion, aclaraciones, pre-nomina y bloques convencionales
- presentar la informacion con jerarquia de decision y no como visor de datos

### 4. Datos

Archivo: `data/convenio_acuaticas_2025_2027.json`

Contenido:

- metadatos del convenio
- tablas salariales
- conceptos economicos
- articulado ya estructurado por bloques operativos

## Flujo de analisis

1. El usuario escribe una consulta libre.
2. La interfaz envia la consulta a `POST /api/analyze`.
3. El motor normaliza el texto y busca indicios de:
   - categoria
   - jornada
   - modalidad
   - antiguedad
   - prorrata de extras
4. El motor decide si puede cerrar la categoria y la jornada.
5. Si puede, calcula pre-nomina orientativa solo con devengos convencionales.
6. Devuelve:
   - estado
   - respuesta operativa
   - aclaraciones
   - lectura estructurada del caso
   - pre-nomina
   - bloques del convenio aplicables

## Criterios de calculo

- Jornada completa de referencia: `40 horas/semana`
- El calculo economico se limita a:
  - salario base
  - prorrata de extras si procede
  - antiguedad por trienios si procede
  - conceptos convencionales explicitamente incorporados

Quedan fuera:

- contingencias comunes
- desempleo
- formacion profesional
- MEI
- IRPF
- incidencias de presencia real del mes

## Extension futura

La extension natural del sistema es desacoplar el dataset de convenio y soportar varios convenios con una capa de resolucion previa de actividad, provincia y centro de trabajo.
