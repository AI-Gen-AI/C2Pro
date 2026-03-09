# 📅 C2Pro - Cronograma Maestro MVP Fase 1
## Guía de Importación a Notion

**Versión:** 1.0  
**Fecha:** 08 de Enero de 2026  
**Cobertura:** Sprint 2 → Sprint 6 (Semanas 2-10)

---

## 📊 Resumen del Cronograma

| Métrica | Valor |
|---------|-------|
| **Total Tareas** | 116 |
| **Story Points** | 267 |
| **Tareas P0 (Críticas)** | 86 (74%) |
| **Tareas P1 (Altas)** | 27 (23%) |
| **Tareas P2 (Medias)** | 3 (3%) |
| **Tareas Alto Riesgo** | 28 |
| **Sprints** | 5 |
| **Semanas** | 9 |
| **Dominios** | 13 |

---

## 📁 Archivos Incluidos

### 1. CSV para Notion (`C2PRO_CRONOGRAMA_MAESTRO_v1.0.csv`)
- **Formato:** CSV estándar UTF-8
- **Columnas:** 17 campos
- **Uso:** Importación directa a Notion Database

### 2. Excel Profesional (`C2PRO_CRONOGRAMA_MAESTRO_v1.0.xlsx`)
- **Hojas incluidas:**
  - 📊 Resumen Ejecutivo
  - 📋 Backlog Completo
  - 🔄 Sprint 2, 3, 4, 5, 6 (una hoja por sprint)
  - 📊 Datos Gantt
  - 🔗 Dependencias
  - 🏷️ Por Dominio
  - ⚠️ Riesgos
  - 📅 Timeline Semanal
- **Uso:** Análisis avanzado, reportes ejecutivos, backup

---

## 🔧 Instrucciones de Importación a Notion

### Paso 1: Crear Base de Datos
1. En Notion, crear una nueva página
2. Escribir `/database` y seleccionar "Database - Full page"
3. Nombrar: "C2Pro - Backlog MVP"

### Paso 2: Importar CSV
1. Click en "..." → "Import" → "CSV"
2. Seleccionar `C2PRO_CRONOGRAMA_MAESTRO_v1.0.csv`
3. Notion creará automáticamente las columnas

### Paso 3: Configurar Propiedades
Ajustar los tipos de campo en Notion:

| Campo | Tipo Notion | Notas |
|-------|-------------|-------|
| ID | Text (Title) | Campo principal |
| Nombre | Text | - |
| Sprint | Select | Valores: Sprint 2-6 |
| Semana | Select | Valores: Semana 2-10 |
| Fecha_Inicio | Date | Formato YYYY-MM-DD |
| Fecha_Fin | Date | Formato YYYY-MM-DD |
| Duracion_Dias | Number | Decimal permitido |
| Prioridad | Select | P0=Rojo, P1=Amarillo, P2=Verde |
| Estado | Status | Pendiente/En Progreso/Completado |
| Dominio | Multi-select | 13 valores |
| CTO_Gate | Select | Gate 1-8, N/A |
| Dependencias | Text | IDs separados por ; |
| Asignado | Person | O Text si no hay usuarios |
| Criterio_Aceptacion | Text | - |
| Riesgo | Select | Bajo/Medio/Alto/Crítico |
| Entregable | Text | Path del archivo |
| Story_Points | Number | Entero |

### Paso 4: Crear Vistas Útiles

**Vista 1: Board por Sprint**
- View type: Board
- Group by: Sprint
- Sort: Prioridad (P0 primero)

**Vista 2: Timeline (Gantt)**
- View type: Timeline
- Timeline by: Fecha_Inicio → Fecha_Fin
- Group by: Sprint

**Vista 3: Por Prioridad**
- View type: Board
- Group by: Prioridad
- Filter: Estado = Pendiente

**Vista 4: Calendario**
- View type: Calendar
- Date: Fecha_Inicio
- Color: Prioridad

**Vista 5: CTO Gates**
- View type: Table
- Filter: CTO_Gate ≠ N/A
- Group by: CTO_Gate

---

## 📋 Estructura de Sprints

### Sprint 2 (Semana 2: 09-11 Ene 2026)
**Foco:** Schemas, Cache, CI/CD, Golden Dataset
- 16 tareas | 35 SP
- Entregables clave:
  - Schemas Pydantic completos
  - Redis cache implementado
  - CI/CD GitHub Actions
  - Golden Dataset v1.0

### Sprint 3 (Semanas 3-4: 13-24 Ene 2026)
**Foco:** Parsers, Coherence Engine, AI Integration
- 27 tareas | 72 SP
- Entregables clave:
  - Parsers PDF/Excel/BC3
  - ClauseExtractorAgent
  - 10 reglas de coherencia
  - Coherence Score calibrado

### Sprint 4 (Semanas 5-6: 27 Ene - 05 Feb 2026)
**Foco:** Stakeholders, RACI, UI Mínima
- 30 tareas | 76 SP
- Entregables clave:
  - StakeholderExtractorAgent
  - RACIGeneratorAgent
  - Dashboard con Score Gauge
  - Evidence Viewer

### Sprint 5 (Semanas 7-8: 09-18 Feb 2026)
**Foco:** Seguridad, Optimización, Testing
- 27 tareas | 53 SP
- Entregables clave:
  - Cifrado R2 AES-256
  - Tests E2E Playwright
  - Load tests k6
  - Deploy producción pipeline

### Sprint 6 (Semanas 9-10: 23 Feb - 05 Mar 2026)
**Foco:** Hardening, Pilotos
- 16 tareas | 31 SP
- Entregables clave:
  - Security testing final
  - Deploy producción
  - 3-5 pilotos onboarded
  - Feedback recopilado

---

## 🔒 CTO Gates - Tareas Asociadas

| Gate | Descripción | Tareas | Estado |
|------|-------------|--------|--------|
| **Gate 1** | Multi-tenant RLS | CE-S9-004 | ✅ Validado |
| **Gate 2** | Identity Model | - | ✅ Validado |
| **Gate 3** | MCP Security | - | ✅ Validado |
| **Gate 4** | Legal Traceability | CE-S3-001 a CE-S6-012 | ✅ Validado |
| **Gate 5** | Coherence Score | CE-S4-005 a CE-S4-008 | 🟡 En Progreso |
| **Gate 6** | Human-in-the-loop | CE-S5-003, CE-S6-005-007 | 🟡 En Progreso |
| **Gate 7** | Observability | CE-S5-012-014, CE-S7-003 | 🟡 En Progreso |
| **Gate 8** | Document Security | CE-S7-001-002 | 🟡 En Progreso |

---

## 🏷️ Distribución por Dominio

| Dominio | Tareas | Story Points | % Total |
|---------|--------|--------------|---------|
| AI | 24 | 78 | 29% |
| Backend | 22 | 48 | 18% |
| Frontend | 12 | 32 | 12% |
| Testing | 14 | 30 | 11% |
| API | 12 | 20 | 7% |
| DevOps | 11 | 17 | 6% |
| Security | 6 | 14 | 5% |
| Documentation | 5 | 9 | 3% |
| Infrastructure | 3 | 8 | 3% |
| Product | 4 | 11 | 4% |
| Otros | 3 | 0 | 0% |

---

## ⚠️ Tareas de Alto Riesgo (28 tareas)

Priorizar monitoreo en:
- **CE-S3-004:** Anonymizer Service PII
- **CE-S3-005:** ClauseExtractorAgent
- **CE-S4-001:** AI Service + Claude API
- **CE-S4-003/004:** WBS/BOM Generator Agents
- **CE-S4-005:** 8 Reglas Coherencia
- **CE-S5-001:** StakeholderExtractor
- **CE-S5-003:** RACIGeneratorAgent
- **CE-S7-001:** Cifrado Documentos
- **CE-S9-001/004:** Security Testing Final

---

## 📈 Métricas de Seguimiento Sugeridas

### Velocity
- **Target semanal:** ~30 SP
- **Target por sprint:** Variable según duración

### Burndown
- Tracking diario de tareas completadas
- Alerta si retraso >2 días en P0

### Quality
- Coverage target: >80%
- Accuracy target: >85%

---

## 📝 Notas de Uso

1. **Dependencias:** El campo `Dependencias` usa IDs separados por `;`
   - Ejemplo: `CE-S3-001;CE-S3-002;CE-S3-003`

2. **Fechas:** Todas las fechas en formato ISO (YYYY-MM-DD)

3. **Story Points:** Fibonacci simplificado (1, 2, 3, 5, 8)

4. **Prioridades:**
   - **P0:** Bloqueante para MVP, debe completarse
   - **P1:** Alta prioridad, completar si posible
   - **P2:** Deseable, puede diferirse

5. **Actualizaciones:** Este cronograma debe actualizarse semanalmente
   - Ajustar fechas según progreso real
   - Añadir nuevas tareas descubiertas
   - Marcar completadas

---

## 🔄 Control de Versiones

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0 | 2026-01-08 | Versión inicial completa |

---

**Generado por:** Claude AI  
**Fecha:** 08 de Enero de 2026  
**Proyecto:** C2Pro - Contract Intelligence Platform

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
