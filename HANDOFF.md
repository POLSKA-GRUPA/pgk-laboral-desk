# PGK Laboral Desk — Documento de Handoff

**Fecha**: 22 de marzo de 2026
**Repo**: `POLSKA-GRUPA/pgk-laboral-desk` (privado)
**Producción**: https://laboral.polskagrupakonsultingowa.com
**Servidor**: 209.74.72.83 (Ubuntu 24.04, Docker Swarm + Traefik + Dokploy)

---

## Qué es esto

Aplicación interna de PGK (asesoría laboral) para:
- Calcular pre-nóminas orientativas basadas en convenios colectivos
- Gestionar clientes (empresas) y asignarles su convenio
- Verificar vigencia de convenios vía Perplexity API

## Estado actual — qué funciona

### Backend (Python/Flask) — FUNCIONA
- **Motor de cálculo** (`engine.py`): simula coste de contratación con SS, IRPF, devengos
- **SS Calculator** (`ss_calculator.py`): tasas 2026, 11 grupos cotización, recargo contratos ≤30 días
- **IRPF Estimator** (`irpf_estimator.py`): escalas estatal + 4 autonómicas (Madrid, Cataluña, Andalucía, Valencia)
- **Multi-convenio**: el engine carga cualquier JSON de convenio y adapta pagas (14 o 15)
- **Alta clientes** (`client_manager.py`): CRUD SQLite, validación CIF/NIF/NIE
- **Verificador convenios** (`convenio_verifier.py`): Perplexity API, solo advisory
- **Importador BOE** (`boe_importer.py`): descarga y parsea XML de convenios estatales
- **Chat parser** (`chat_parser.py`): interpreta consultas en lenguaje natural (preexistente)
- **56 tests pasan** (offline + integración BOE + integración Perplexity)

### API endpoints — FUNCIONAN
- `POST /api/auth/login` y `/api/auth/logout`
- `GET /api/categories`, `/api/contract-types`
- `POST /api/simulate` — simulación con convenio por defecto (acuáticas)
- `POST /api/chat` — consulta conversacional
- `GET /api/convenios` — lista convenios disponibles
- `POST /api/clients` — alta cliente (solo admin)
- `GET /api/clients` — lista clientes (solo admin)
- `POST /api/clients/<id>/simulate` — simula con el convenio del cliente
- `POST /api/verify-convenio` — verificación Perplexity
- `GET /api/health`

### Convenios cargados
1. **Acuáticas** (`data/convenio_acuaticas_2025_2027.json`) — estatal, 14 pagas, 24 categorías
2. **Oficinas y Despachos Alicante** (`data/convenio_oficinas_despachos_alicante_2024_2026.json`) — provincial, 15 pagas (incluye paga de marzo), 22 categorías

### Frontend — NECESITA TRABAJO
- `static/index.html`: página de login (funciona, tiene estilos inline)
- `static/panel.html`: dashboard post-login con chat + formulario + resultado
- `static/styles.css`: estilos para la vieja consulta + estilos del panel (añadidos)
- `static/app.js`: lógica frontend para chat, formulario, alertas, historial

**Problemas conocidos del frontend**:
- El panel NO tiene sección para gestionar clientes (alta, listado)
- No hay selector de convenio — siempre carga el de acuáticas por defecto
- No hay pantalla de verificación de convenio
- El formulario tiene hardcodeado "14 pagas" en los radio buttons
- Falta integración del endpoint `/api/clients/<id>/simulate` en el frontend
- Los estilos del panel se añadieron rápido y pueden no cubrir todos los estados

## Estructura de archivos

```
pgk-laboral-assistant/
├── app.py                  # Flask server, rutas API
├── engine.py               # Motor de cálculo laboral (multi-convenio)
├── ss_calculator.py        # Seguridad Social 2026
├── irpf_estimator.py       # IRPF con escalas autonómicas
├── database.py             # SQLite: users, consultations, alerts
├── client_manager.py       # SQLite: clients (empresas)
├── convenio_verifier.py    # Perplexity API (advisory)
├── boe_importer.py         # Importador XML del BOE
├── chat_parser.py          # NLP básico para consultas
├── data/
│   ├── convenio_acuaticas_2025_2027.json
│   ├── convenio_oficinas_despachos_alicante_2024_2026.json
│   ├── ss_config.json          # Tasas SS 2026 + grupos + recargo
│   ├── categorias_detalle.json
│   └── empresa_mpc.json
├── static/
│   ├── index.html    # Login
│   ├── panel.html    # Dashboard
│   ├── styles.css    # CSS (viejo + panel)
│   └── app.js        # JS frontend
├── tests/
│   ├── test_engine.py
│   ├── test_boe_importer.py
│   ├── test_client_manager.py
│   └── test_chat_parser.py
├── Dockerfile
├── .github/workflows/deploy.yml
├── requirements.txt
└── pyproject.toml
```

## Cómo funciona el engine multi-convenio

El `engine.py` detecta automáticamente el número de pagas del convenio:
- Lee `resumen_operativo.pagas_extras` del JSON (2 para acuáticas, 3 para oficinas)
- Calcula `_convenio_pagas = pagas_extras + 12` (14 o 15)
- Acepta `monthly_14_payments_eur` O `monthly_15_payments_eur` en el JSON de salarios
- Si solo tiene `annual_eur`, divide entre `_convenio_pagas`

Para cargar un convenio específico:
```python
engine = LaboralEngine.from_convenio_id("convenio_oficinas_despachos_alicante_2024_2026")
```

## Cómo añadir un nuevo convenio

1. Crear `data/convenio_<nombre>_<vigencia>.json` siguiendo el schema de los existentes
2. Campos obligatorios:
   - `convenio.nombre`, `convenio.codigo`, `convenio.vigencia_desde_ano`, `convenio.vigencia_hasta_ano`
   - `resumen_operativo.pagas_extras` (2 si junio+diciembre, 3 si también marzo)
   - `salarios_por_categoria[]` con `category`, `annual_eur`, y opcionalmente `monthly_XX_payments_eur`
   - `sections[]` con items `{label, detail, source}`
3. El engine lo detecta automáticamente al listar convenios

## Deploy

### Infraestructura
- **Servidor**: 209.74.72.83 (root)
- **Stack**: Docker Swarm + Traefik (gestionado por Dokploy)
- **Servicio**: `laboral-pgk` en red `dokploy-network`
- **Volumen**: `laboral-pgk-data` montado en `/data` (SQLite persistente)
- **Traefik config**: `/etc/dokploy/traefik/dynamic/laboral-pgk.yml`
- **Código en servidor**: `/opt/laboral-pgk/` (git clone del repo)
- **Dominio**: `laboral.polskagrupakonsultingowa.com` (SSL Let's Encrypt)

### CI/CD
GitHub Actions (`.github/workflows/deploy.yml`): en cada push a `main`:
1. SSH al servidor
2. `git pull origin main`
3. `docker build -t laboral-pgk:latest .`
4. `docker service update --image laboral-pgk:latest --force laboral-pgk`

Secrets configurados en GitHub: `SERVER_HOST`, `SERVER_PASSWORD`

### Deploy manual
```bash
ssh root@209.74.72.83
cd /opt/laboral-pgk
git pull origin main
docker build -t laboral-pgk:latest .
docker service update --image laboral-pgk:latest --force laboral-pgk
```

## Variables de entorno (producción)
- `FLASK_SECRET_KEY` — secret para sesiones Flask
- `PERPLEXITY_API_KEY` — para verificación de convenios (pplx-...)
- `ENVIRONMENT=production`

## Usuarios de prueba
- **Admin PGK**: `pgk` / `pgk2025` (role: admin)
- **Cliente MPC**: `mpc` / `mpc2025` (role: client)

Creados automáticamente por `database.py:init_db()`.

## Bugs encontrados y corregidos en esta sesión

1. **Engine hardcodeado a acuáticas** — `app.py` línea 36 tenía `engine = LaboralEngine.from_json_file()` que siempre cargaba acuáticas. CORREGIDO: ahora usa `_get_engine()` que carga dinámicamente según el `convenio_id` del usuario en sesión.
2. **Usuario pgk tenía convenio de acuáticas** — `database.py` sembraba pgk con `convenio_acuaticas_2025_2027`. CORREGIDO: ahora pgk tiene `convenio_oficinas_despachos_alicante_2024_2026` + UPDATE automático si ya existía.
3. **CSS del panel inexistente** — `panel.html` usaba clases (`.topbar`, `.card`, `.chat-card`, `.btn-primary`, etc.) que no existían en `styles.css`. CORREGIDO: añadidos ~380 líneas de CSS.
4. **index.html no era login** — servía la vieja página de consulta sin formulario de login. CORREGIDO: reemplazada por página de login con branding PGK.
5. **`/api/simulate` no pasaba `region` ni `contract_days`** — el backend los soportaba pero el endpoint no los leía del request. CORREGIDO.
6. **CI/CD no funcionaba en primer push** — el repo era privado y el servidor no tenía autenticación git. CORREGIDO: se configuró con token GitHub existente.
7. **Deploy no era desde GitHub** — se hizo rsync directo en vez de git clone. CORREGIDO: ahora el servidor tiene git clone y el CI/CD hace git pull.

## Qué falta por hacer

### Prioritario
1. **Frontend del panel de clientes**: el panel NO tiene UI para gestionar clientes (alta, listado, selección de convenio). Los endpoints API existen pero no hay interfaz.
2. **El panel.html necesita una revisión de diseño seria** — los estilos se añadieron rápido y hay inconsistencias visuales.
3. **El formulario hardcodea "14 pagas" en los radio buttons** — debería leer del convenio cuántas pagas tiene.
4. **`app.js` no envía `region` ni `contract_days`** — el backend ya los soporta pero el JS no los incluye en las llamadas.

### Medio plazo
5. **Parser genérico de convenios** (`convenio_parser.py`): que tome texto de cualquier fuente (PDF, BOE, BOPA) y genere el JSON estructurado.
6. **Más convenios**: cada convenio nuevo es un JSON en `data/`.
7. **Gunicorn en producción** — ahora usa Flask dev server (WARNING visible en logs).

### Mejoras
8. Migración de SQLite a PostgreSQL si crece
9. Tests de integración del frontend
10. La verificación Perplexity debería mostrarse al dar de alta un convenio nuevo

## Tests

```bash
# Todos los tests offline (56)
python3 -m pytest -v -m "not integration"

# Incluir integración (BOE + Perplexity, requiere red + API key)
PERPLEXITY_API_KEY=pplx-... python3 -m pytest -v
```
