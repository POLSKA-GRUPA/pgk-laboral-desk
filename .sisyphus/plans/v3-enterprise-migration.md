# PGK Laboral Desk v3.0 — Plan Estratégico: El Mejor Software Laboral de España

> Objetivo: Transformar pgk-laboral-desk de una app Flask de 8K líneas a una plataforma enterprise
> que rivalice con conta-pgk-hispania (72K líneas) y supere a A3nom/Factorial en inteligencia normativa.

## Diagnóstico Actual

| Dimensión | conta-pgk (referencia) | laboral-desk (actual) | Gap |
|-----------|----------------------|----------------------|-----|
| LOC backend | 72K (272 archivos) | 8K (20 archivos) | 9x |
| Framework | FastAPI + React 18 + TS | Flask + Vanilla JS | Generación |
| Estructura | Modular (routes/models/services/schemas/core) | Archivos planos en raíz | Arquitectura |
| Multi-agente | 8 agentes + supervisor LangGraph | 1 agente CodeAct básico | IA |
| Infra producción | Circuit breaker, rate limiter, cache, audit trail, metrics, overwatcher | Ninguno | Resiliencia |
| Multi-tenancy | JWT + company access | Login básico sin aislamiento | Aislamiento |
| Tests | 683 líneas solo invoices | 63 tests, 7 módulos sin tests | Cobertura |
| Frontend | 43 páginas React, Ant Design | 2 HTML + 1 JS SPA | UX |
| Documentación | AGENTS.md + CLAUDE.md + GEMINI.md + skills + knowledge/ | AGENTS.md básico | Onboarding |

## Ventaja Competitiva (lo que NADIE tiene en España)

Factorial y Bizneo NO calculan nominas. A3nom y Sage calculan pero son desktop sin IA.
El hueco: **inteligencia normativa en tiempo real aplicada al cálculo laboral.**

Killer features que nadie tiene:
1. Monitor BOE + motor de impacto en nómina
2. Parser automático de convenios del BOE
3. Motor de consultas en lenguaje natural con respuestas trazables

## Estrategia: "Capa de inteligencia laboral"

No competir con A3nom en cálculo bruto. Ser el cerebro que A3nom no tiene.
Fase 1 = infra. Fase 2 = dominio profundo. Fase 3 = IA multi-agente.

---

## FASE 1: Fundación Enterprise (2-3 semanas)

### 1.1 Migrar Flask → FastAPI con estructura modular

**Objetivo**: Replicar la arquitectura de conta-pgk-hispania.

**Estructura objetivo**:
```
laboral-backend/
  app/
    __init__.py
    main.py                 # FastAPI entry point, lifespan, CORS, routers
    database.py             # SQLAlchemy async + SQLite/PostgreSQL dual-mode
    exceptions.py           # (migrar existente, ya es bueno)
    
    core/
      __init__.py
      config.py             # pydantic-settings, validación startup
      deps.py               # JWT get_current_user + company access
      security.py           # JWT creation/verification, password hashing
      middleware.py          # RequestID + SecurityHeaders + Timing
      circuit_breaker.py    # Copiar de conta-pgk (patrón idéntico)
      rate_limiter.py       # Token bucket per-user
      cache_service.py      # TTL cache con invalidation por empresa
      metrics.py            # Latencia p95 por servicio
      audit_trail.py        # Log de acciones (18+ tipos)
      overwatcher.py        # Health check de 6 subsistemas
      llm_queue.py          # Semáforos por servicio LLM
    
    models/
      __init__.py
      user.py               # User, role, company access
      employee.py           # Employee con NIF, NAF, contrato, categoría
      company.py            # Company/despacho
      convenio.py           # Convenio colectivo + tablas salariales
      consultation.py       # Consultas laborales
      alert.py              # Alertas normativas
      payroll.py            # Nóminas generadas
      contract.py           # Contratos
      dismissal.py          # Despidos/finiquitos
    
    schemas/
      __init__.py
      user.py               # UserCreate, UserResponse, TokenResponse
      employee.py           # EmployeeCreate, EmployeeResponse
      company.py            # CompanyCreate, CompanyResponse
      convenio.py           # ConvenioResponse, ConvenioDetail
      simulation.py         # SimulateRequest, SimulateResponse
      payroll.py            # NominaResponse, NominaPDFResponse
      dismissal.py          # DespidoRequest, DespidoResponse
      chat.py               # ChatRequest, ChatResponse
      alert.py              # AlertResponse
    
    routes/
      __init__.py
      health.py             # GET /api/health
      auth.py               # POST login, logout, me
      employees.py          # CRUD empleados + nómina + despido
      companies.py          # CRUD empresas (admin)
      convenios.py          # Listar, detallar, verificar vigencia
      simulation.py         # POST /api/simulate (motor determinista)
      chat.py               # POST /api/chat (parser + agente)
      payroll.py            # POST /api/nomina (PDF generation)
      dismissal.py          # POST /api/despido (cálculo extinción)
      alerts.py             # GET/POST/PUT alertas
      verification.py       # GET /api/verify-rates, verify-convenio
      boe.py                # GET /api/boe/sumario, /boe/documento
    
    services/
      __init__.py
      engine.py             # (migrar engine.py actual)
      ss_calculator.py      # (migrar ss_calculator.py actual)
      irpf_estimator.py     # (migrar irpf_estimator.py actual)
      chat_parser.py        # (migrar chat_parser.py actual)
      nomina_pdf.py         # (migrar nomina_pdf.py actual)
      client_manager.py     # (migrar client_manager.py actual)
      convenio_verifier.py  # (migrar convenio_verifier.py actual)
      rates_verifier.py     # (migrar rates_verifier.py actual)
      payroll_service.py    # Orquestar engine + SS + IRPF + PDF
    
    data/
      pgc_2008.py           # (solo si se integra con conta)
      ss_config_2026.json   # (migrar existente)
      convenio_*.json       # (migrar existentes)
    
    tests/
      conftest.py           # Fixtures compartidos
      test_health.py
      test_auth.py
      test_simulation.py
      test_employees.py
      test_chat.py
      test_dismissal.py
      test_engine.py        # (migrar existente)
      test_ss_calculator.py
      test_irpf_estimator.py
      test_chat_parser.py   # (migrar existente)

laboral-frontend/
  src/
    App.tsx                 # Shell con router, sidebar, command palette
    pages/                  # Una página por módulo
    components/             # Layout, ErrorBoundary, ChatWidget
    services/api.ts         # Cliente API tipado (copiar patrón conta)
    hooks/                  # useAuth, useApiCall
    types/                  # TypeScript interfaces
  package.json
  vite.config.ts
  tsconfig.json
```

**Dependencias nuevas**:
```
# Backend
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
alembic>=1.13
pydantic>=2.0
pydantic-settings>=2.0
python-jose[cryptography]>=3.3
passlib[bcrypt]>=1.7
httpx>=0.28
structlog>=24.0

# Frontend
react 18, typescript, vite 6, ant design 5, recharts, tailwindcss
```

**Archivos a crear**: ~60
**Archivos a migrar**: 14 (engine, ss_calculator, irpf_estimator, chat_parser, nomina_pdf, client_manager, convenio_verifier, rates_verifier, validation, exceptions, logging_config, database, boe_importer, laboral_agent)
**Estimación**: 5-7 días de implementación

### 1.2 Multi-tenancy + Auth JWT

- Copiar patrón de conta-pgk: `app/core/deps.py` con `get_current_user()` y `verify_company_access()`
- Tabla `user_company_access` para relación N:N
- Todas las queries filtran por `company_id`
- Superuser bypass para admin

### 1.3 Infra de producción

Copiar de conta-pgk (son módulos genéricos, independientes del dominio):
- `circuit_breaker.py`: Protege 5 servicios (Perplexity, Gemini, Anthropic, BOE API, SILTRA)
- `rate_limiter.py`: Token bucket por usuario por grupo de endpoints
- `cache_service.py`: TTL cache con invalidación por empresa
- `metrics.py`: Latencia p95 por servicio
- `audit_trail.py`: Log de 15+ tipos de acción
- `overwatcher.py`: Health check de DB, API keys, circuit breakers, queues

### 1.4 Frontend React

Copiar scaffolding de conta-pgk-hispania:
- `App.tsx` con router, sidebar, command palette
- `api.ts` tipado con retry automático
- `useAuth` hook con persistencia localStorage
- `useApiCall` hook genérico
- `ErrorBoundary` con retry tracking

Páginas iniciales:
1. Dashboard (resumen empresa: empleados, costes, alertas)
2. Empleados (CRUD + nómina + despido)
3. Simulador (motor determinista)
4. Chat (parser + agente)
5. Convenios (listar + vigencia)
6. Alertas (listar + descartar)
7. Configuración (empresa, usuarios)

### 1.5 CI/CD + Docker

- GitHub Actions: ruff + pytest + frontend build
- Docker multi-stage (frontend build → backend + serve SPA)
- Fly.io deployment config

---

## FASE 2: Dominio Laboral Profundo (2-3 semanas)

### 2.1 Parser automático de convenios del BOE

**Módulo nuevo**: `app/services/convenio_parser.py`

Funcionalidad:
- Descargar PDF/XML del convenio desde BOE API
- Extraer tablas salariales (grupos profesionales, niveles, salarios)
- Extraer condiciones (jornada, vacaciones, pagas extras, trienios, plus transporte)
- Extraer cláusulas especiales (turnos, nocturnidad, toxicidad)
- Generar `convenio_*.json` estructurado automáticamente
- Comparar versión anterior vs nueva y generar diff

Dependencias: `pypdf`, `defusedxml`, `httpx`, posiblemente LLM para tablas complejas

### 2.2 Monitor BOE con alertas de impacto

**Módulo nuevo**: `app/services/boe_monitor.py`

Funcionalidad:
- Polling diario del BOE sumario API (materia: "Trabajo", "Seguridad Social")
- Clasificar publicaciones: afecta nómina / afecta contratos / afecta SS / informativa
- Motor de impacto: "Esta publicación modifica X, afecta a Y empleados de tu empresa"
- Alertas automáticas por empresa con severidad y acción recomendada
- Scheduler en lifespan (igual que ASESOR)

### 2.3 Motor de nóminas completo

Mejorar `engine.py` actual:
- Soporte completo de todos los devengos (salario base, antiquüedad, plus transporte, nocturnidad, toxicidad, turnidad, pagas extras)
- Cálculo de bases de cotización (4 bases: contingencias comunes, AT/EP, desempleo, FOGASA)
- IRPF por tramos progresivos (ya implementado, verificar con 2026)
- Generación de recibo de nómina en formato legal (Orden 27/12/1994)
- Exportación a PDF (WeasyPrint) y Excel (openpyxl)
- Nóminas批量 (bulk payroll para toda la plantilla)

### 2.4 Dashboard de cumplimiento

**Módulo nuevo**: `app/services/compliance.py`

Verificaciones continuas:
- DGED (registro horario): ¿todos los empleados fichan?
- Registro retributivo (Ley de Igualdad): ¿brecha salarial por puesto?
- Vencimiento contratos temporales
- Fin período de prueba
- Reconocimientos médicos
- Calendario de prevención de riesgos
- SILTRA (TC1/TC2) filing dates
- Modelo 111/190 IRPF filing dates

Estado: rojo/amarillo/verde por empleado por área de cumplimiento.

### 2.5 Asistente de despido inteligente

Mejorar despido actual:
- Cálculo exacto de indemnización por tipo (improcedente, objetivo, disciplinario, ERE, colectivo)
- Estadísticas de tribunales por jurisdicción y tipo (datos CENDOJ)
- Generación automática de documentación:
  - Carta de despido
  - Finiquito / recibo de saldo
  - Certificado de empresa
  - Comunicación a SSL (baja en TC2)
- Consejo estratégico: "En tu jurisdicción, el 73% de los improcedentes se resuelven en conciliación"

---

## FASE 3: Capa de Inteligencia Multi-Agente (2-3 semanas)

### 3.1 Sistema multi-agente con supervisor

Replicar patrón conta-pgk `app/cfo/`:

```
laboral-backend/app/laboral_agent/
  engine.py               # Dual-mode: simple keyword + LangGraph supervisor
  router.py               # Keyword routing con normalización
  llm.py                  # Streaming client con circuit breaker
  
  supervisor/
    graph.py              # StateGraph: START -> supervisor -> [agents] -> END
    prompts.py            # Supervisor prompt con referencias ET
    routing.py            # Keyword + LLM fallback classification
  
  agents/
    base.py               # BaseAgent con tool calling loop (max 5 iterations)
    nomina_agent/         # Especialista en nóminas
    contrato_agent/       # Especialista en contratos
    convenio_agent/       # Especialista en convenios
    despido_agent/        # Especialista en despidos/finiquitos
    compliance_agent/     # Especialista en cumplimiento
    costes_agent/         # Especialista en simulación de costes
    extranjeria_agent/    # Especialista en extranjería
    ss_agent/             # Especialista en Seguridad Social
  
  tools/
    db_tools.py           # 12+ tools: simular, buscar, calcular, consultar
    fiscal_tools.py       # Herramientas fiscales (IRPF, retenciones)
    boe_tools.py          # Búsqueda en BOE
    export_tools.py       # Generación de PDFs, Excels
  
  core/
    state.py              # LaboralState (Pydantic) con LangGraph reducers
    config.py             # Config bridge
```

### 3.2 AI Safety Stack

Copiar de conta-pgk (patrones genéricos):
- `persona_blend.py`: Personas con controles de sesgo (never_invent_data, cite_sources)
- `red_team.py`: Verificación pre-acción (7 checks)
- `verdicts.py`: 5-verdict system (CONFIRMED/LIKELY_CORRECT/UNCERTAIN/LIKELY_WRONG/REJECTED)
- `domain_quality.py`: Scoring de credibilidad por dominio
- `query_normalizer.py`: Normalización de términos laborales (200+ sinónimos)

### 3.3 Motor de consultas en lenguaje natural

Integrar chat_parser.py actual con LLM:
- Parser determinista para casos simples (ya funciona bien)
- LLM fallback para consultas complejas
- Respuestas siempre trazables: citar artículo del ET, convenio, o BOE
- Streaming via SSE
- Contexto de empresa inyectado automáticamente (empleados, convenio activo, etc.)

### 3.4 Integraciones

- Export a A3nom/Sage (formato de importación compatible)
- Sync bidireccional con Factorial (API pública)
- SILTRA electrónico (certificado digital)
- Modelo 111/190 telemático (AEAT)

---

## ORDEN DE IMPLEMENTACIÓN (dependencias)

```
Semana 1: Estructura backend FastAPI + config + database + auth + middleware
Semana 2: Migrar motor (engine, ss_calculator, irpf_estimator) + routes + schemas
Semana 3: Migrar chat_parser, nomina_pdf, client_manager + tests
Semana 4: Frontend React scaffolding + páginas core (dashboard, empleados, simulador, chat)
Semana 5: Parser convenios + BOE monitor + alertas impacto
Semana 6: Dashboard cumplimiento + asistente despido inteligente
Semana 7: Multi-agente (supervisor + 4 agentes core)
Semana 8: AI safety stack + integraciones + polish
```

## MÉTRICAS DE ÉXITO

| Métrica | Actual | Target v3.0 |
|---------|--------|-------------|
| LOC backend | 8K | 40K+ |
| Tests | 63 | 300+ |
| API endpoints | 30 | 80+ |
| Convenios soportados | 2 | Todos los del BOE (parser automático) |
| Comunidades autónomas IRPF | 4 | 17 + Ceuta/Melilla |
| Frontend páginas | 2 | 12+ |
| Agentes IA | 1 (básico) | 8 especialistas + supervisor |
| Tiempo respuesta chat | N/A | <2s (simple), <10s (agente) |
| Uptime target | Manual | 99.5% (overwatcher + circuit breaker) |
