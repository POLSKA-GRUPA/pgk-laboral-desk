# MEMORY.md — Memoria Persistente PGK Laboral Desk

> *Los agentes leen este archivo al arrancar para saber que ha pasado antes.*
> *Actualizarlo al final de cada sesion larga o cuando haya decisiones importantes.*
> **NOTA:** Ademas de este archivo, usar **Engram** (`engram mcp`) para memoria persistente estructurada.

---

## Resumen Ejecutivo

**Proyecto:** PGK Laboral Desk — Gestion laboral inteligente

---

## Decisiones Importantes

- [2026-04-14] **Engram configurado** como MCP para memoria persistente entre sesiones (Go + SQLite + FTS5)

---

## Lecciones Aprendidas

- Las "notas mentales" no sobreviven entre sesiones — escribir en archivos o usar Engram
- **El contexto de LLM es limitado** — cargar solo lo necesario

---

## Bucles Abiertos

<!-- Tareas pendientes, cosas a medio hacer -->

---

## Ultima Sesion

**Fecha:** 2026-04-14
**Que se hizo:**
- Configurado Engram y archivos de agente (AGENTS.md, MEMORY.md)
**Que quedo pendiente:**
- (pendiente)
