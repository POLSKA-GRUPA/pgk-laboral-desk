# Operación y límites

> Revisado: 2026‑04‑22.

## Cómo usar la herramienta

Dos modos de uso:

### 1. Agente IA (si hay API key de LLM configurada)

Consulta en lenguaje natural. El agente decide qué tools llamar:

```text
Quiero contratar un socorrista Nivel B fijo-discontinuo a 40h/semana para la temporada de verano, en Madrid, con 3 años de antigüedad.
```

El agente ejecutará internamente, por ejemplo:

```python
simular_contrato(
    categoria="Nivel B.",
    tipo_contrato="fijo-discontinuo",
    horas_semanales=40,
    antiguedad_anos=3,
    region="madrid",
)
```

y devolverá coste total, bruto mensual, neto mensual, SS empresa, SS
trabajador, IRPF retenido y lectura estructurada del caso.

### 2. Modo determinista (sin LLM)

La consulta debe incluir idealmente:

- puesto o categoría,
- jornada (horas semanales o tipo),
- modalidad (indefinido, temporal, fijo‑discontinuo, sustitución),
- temporada o periodo de actividad si hay fijo‑discontinuo,
- antigüedad o trienios,
- prorrata o no de pagas extra.

Ejemplo válido:

```text
Quiero contratar un socorrista nivel B fijo-discontinuo a 40 horas semanales para la temporada de verano.
```

Ejemplo incompleto:

```text
Socorrista media jornada fijo-discontinuo
```

En el segundo caso el parser responde, pero pedirá aclaraciones porque no
puede cerrar categoría exacta ni periodo real de actividad.

### 3. MCP (cuando el PR esté mergeado)

Cualquier host MCP (Claude Desktop, Cursor, Windsurf, ChatGPT Desktop) puede
llamar directamente a las tools:

- `laboral_calcular_nomina(salario_bruto_anual, categoria?, pagas_extra?)`
- `laboral_consultar_convenio(convenio, categoria?)`
- `laboral_calcular_ss(base_cotizacion, tipo_contrato)`
- `laboral_estimar_irpf(salario_bruto_anual, situacion_familiar, hijos?,
  discapacidad?)`

Ver `docs/MCP_INTEGRATION.md` (pendiente) para el snippet `claude_desktop_config.json`.

---

## Cómo leer la salida

### 1. Lo que he entendido

Resumen estructurado del caso que el motor/agente interpretó:

- categoría profesional detectada (o opciones si ambigua),
- modalidad contractual,
- jornada,
- trienios,
- pagas extras del convenio (2 ó 3, determina 14 ó 15 pagas totales),
- región IRPF,
- punto sensible o ambigüedad relevante.

### 2. Conclusión del caso

Respuesta operativa prioritaria para dirección:

- si hay encaje provisional,
- si faltan datos,
- si puede emitirse pre‑nómina orientativa.

### 3. Pre‑nómina orientativa

Cifras base del mes activo:

- bruto mensual (12 meses o prorrateo a 14/15),
- Seguridad Social trabajador,
- Seguridad Social empresa,
- retención IRPF,
- neto estimado,
- coste total empresa/mes.

**No es una nómina definitiva.** No incluye horas extras reales, ausencias,
bajas, complementos no convencionales ni regularizaciones de IRPF.

### 4. Condiciones aplicables

Bloques jurídico‑laborales relevantes del convenio ya ordenados para consulta
(artículos de jornada, antigüedad, extras, descansos, permisos, etc.).

### 5. Traza (cuando se use el agente)

Código Python que el LLM ejecutó, tools llamadas, resultado de cada tool,
respuesta final. Útil para auditoría y para que dirección pueda reabrir la
conversación meses después.

> **Estado:** el audit trail persistente en BBDD (tabla `agent_runs`) es un
> trabajo pendiente de la hoja de ruta. Hoy la traza vive en la sesión HTTP.

---

## Límites jurídicos

La herramienta **no debe usarse por sí sola** para:

- emitir nómina definitiva con cotización real firmada,
- cerrar contrato internacional,
- validar permisos de trabajo,
- resolver cotización o fiscalidad transfronteriza,
- sustituir el análisis del Estatuto de los Trabajadores o normativa superior,
- tomar decisiones de despido colectivo / ERE sin asesoramiento profesional.

El LLM puede redactar la respuesta, pero **nunca produce los números**: todos
salen del motor determinista y de `data/`. Si el motor no tiene el dato, la
respuesta es *"faltan datos"*, no una cifra inventada.

---

## Límites técnicos actuales

- **Convenios cargados:** 2 (acuáticas estatal 2025‑2027, oficinas y despachos
  Alicante 2024‑2026). Añadir más es cuestión de volcar BOE → JSON.
- **Comunidades autónomas (IRPF):** 4 (Madrid, Cataluña, Andalucía, Valencia).
- **Persistencia:** SQLite single‑node, backup vía volumen Docker. Migración a
  PostgreSQL prevista cuando el volumen de consultas lo requiera.
- **Audit trail del agente:** aún no persiste en BBDD. Pendiente.
- **MCP:** schema definido, servidor pendiente de cablear (PR en curso).
- **v2 vs v3:** la capa IA sólo está cableada en v2 Flask. v3 FastAPI (el que
  corre en producción) atiende HTTP pero no expone agente ni MCP hoy.
- **Auth:** login básico + JWT (v3). Sin SSO, sin 2FA.
- **Rate‑limit del LLM:** depende del proveedor. Gemini free tier tiene
  cuotas. Anthropic tiene límites por minuto. Si se rebasan, el sistema
  degrada a `chat_parser.py` determinista.

---

## Recomendación de uso interno

Secuencia correcta:

1. Dirección formula la necesidad (contratación, despido, simulación).
2. La herramienta da lectura, condicionamiento y base económica.
3. El equipo laboral valida:
   - convenio aplicable,
   - modalidad correcta,
   - jornada y calendario,
   - impacto de Seguridad Social e IRPF,
   - ayudas/bonificaciones aplicables.
4. Si hay componente internacional, se abre expediente separado de
   extranjería y fiscalidad.
5. Se emite la nómina/contrato/finiquito definitivo por vía profesional
   (firma + registro).

## Errores comunes a evitar

- **Tomar el número bruto de pre‑nómina como si fuera el bruto de nómina
  firmada.** Las regularizaciones de IRPF de final de año, las bajas y las
  horas extras reales hacen que diverja.
- **Asumir que el agente IA conoce la última reforma.** El agente sólo sabe
  lo que hay en `data/knowledge_base/` y los convenios cargados. Si cambia un
  RDL, hay que actualizar los JSON antes.
- **Confundir "estimación IRPF del motor" con "liquidación definitiva de la
  declaración anual".** Son cosas distintas.
- **Usar `convenio_verifier.py` (Perplexity) como fuente autoritativa.** Es
  **advisory**: sirve para detectar que un convenio lleva años sin publicarse
  en BOE y probablemente esté vencido, no para certificar vigencia.
