# C2PRO - Especificación Técnica

## Contract Intelligence Platform

**Versión:** 1.0.0  
**Fecha:** 29 de Diciembre de 2024  
**Autor:** Jesús - Strategic Procurement Director  
**Estado:** MVP - Fase 1  
**Clasificación:** CONFIDENCIAL

---

## Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Arquitectura del Sistema](#2-arquitectura-del-sistema)
3. [Seguridad y Compliance](#3-seguridad-y-compliance)
4. [Modelo de Datos](#4-modelo-de-datos)
5. [API Reference](#5-api-reference)
6. [Sistema de IA](#6-sistema-de-inteligencia-artificial)
7. [Roadmap](#7-roadmap-de-implementación)
8. [Análisis de Costes](#8-análisis-de-costes)
9. [Análisis de Riesgos](#9-análisis-de-riesgos)
10. [Anexos](#10-anexos)

---

## 1. Resumen Ejecutivo

C2Pro es una plataforma SaaS de inteligencia contractual y optimización de compras diseñada para empresas de construcción, ingeniería e industria. El sistema realiza **auditoría tridimensional automática** cruzando:

- **Contrato** → Cláusulas, plazos, penalizaciones
- **Cronograma** → Actividades, hitos, dependencias
- **Presupuesto** → Partidas, mediciones, precios

### 1.1 Problema que Resolvemos

El **15-30% de los sobrecostes** en proyectos de construcción e ingeniería se deben a la desconexión entre estos tres documentos:

- ❌ Penalizaciones por incumplimiento de plazos contractuales
- ❌ Sobrecostes por partidas no alineadas con el contrato
- ❌ Pérdida de oportunidades de revisión de precios
- ❌ Falta de trazabilidad entre documentos

### 1.2 Propuesta de Valor

> **"C2Pro es el único sistema que cruza automáticamente contrato, cronograma y presupuesto para detectar incoherencias antes de que cuesten dinero."**

| Diferenciador | Beneficio |
|---------------|-----------|
| Cruce tridimensional automático | Detecta incoherencias en minutos, no días |
| IA especializada en construcción | Entiende cláusulas, plazos y partidas del sector |
| Alertas proactivas | Previene problemas antes de que ocurran |
| Generación de Plan de Compras | De auditoría pasiva a copiloto activo |

### 1.3 Mercado Objetivo

**Segmento inicial:** Empresas medianas (50-250 empleados, 15-100M€ facturación) en España y LATAM que gestionan proyectos >500K€.

---

## 2. Arquitectura del Sistema

La arquitectura sigue el principio **"Simple, Seguro, Suficiente"** - optimizada para un fundador solo con capacidad de escalar.

### 2.1 Stack Tecnológico

| Capa | Tecnología | Justificación |
|------|------------|---------------|
| **Frontend** | Next.js 14 + Tailwind + shadcn/ui | SSR, excelente DX, deploy en Vercel |
| **Backend** | FastAPI + Pydantic v2 | Async, validación automática, OpenAPI |
| **Base de Datos** | Supabase PostgreSQL | RLS nativo, backups automáticos, PITR |
| **Cache** | Upstash Redis | Serverless, pay-per-request |
| **Storage** | Cloudflare R2 | S3-compatible, sin egress fees |
| **IA** | Claude API (Sonnet 3.5) | Mejor calidad para documentos largos |
| **Observabilidad** | Sentry + Structlog + UptimeRobot | Errores, logs, uptime |

### 2.2 Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    CAPA DE PRESENTACIÓN                     │
│    Next.js 14 + Tailwind + shadcn/ui (Deploy: Vercel)      │
└─────────────────────────────────────────────────────────────┘
                              │ HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    CAPA DE APLICACIÓN                       │
│         FastAPI + Pydantic v2 (Deploy: Railway)            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │  Auth   │ │  Docs   │ │Analysis │ │   AI    │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
└─────────────────────────────────────────────────────────────┘
          │              │              │
          ▼              ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │PostgreSQL│  │  Redis   │  │    R2    │
    │(Supabase)│  │(Upstash) │  │(Cloudflr)│
    └──────────┘  └──────────┘  └──────────┘
                              │
                              ▼
                     ┌──────────────┐
                     │  Claude API  │
                     │  (Anthropic) │
                     └──────────────┘
```

### 2.3 Principios de Diseño

1. **Monolito Modular:** Un solo servicio bien estructurado, no microservicios
2. **Seguridad por Diseño:** Multi-tenancy con RLS, anonymization de PII
3. **Costes Optimizados:** Uso de free tiers y servicios serverless (~$120-230/mes)
4. **IA como Core:** Claude API con model routing y budget control

---

## 3. Seguridad y Compliance

### 3.1 Multi-tenancy (Aislamiento de Datos)

Cada cliente (tenant) solo puede acceder a sus propios datos mediante **Row Level Security (RLS)**:

```sql
-- Política de aislamiento
CREATE POLICY tenant_isolation ON projects
    FOR ALL
    USING (tenant_id = auth.jwt() ->> 'tenant_id');
```

**Implementación:**
- ✅ RLS habilitado en todas las tablas con datos de tenant
- ✅ Middleware obligatorio que extrae tenant_id del JWT
- ✅ Tests automatizados de aislamiento entre tenants
- ✅ Logging de intentos de acceso no autorizado

### 3.2 Protección de PII en IA

Antes de enviar texto a Claude API:

1. **Anonymization:** Detección y reemplazo de patrones de PII con placeholders
2. **DPA firmado:** Data Processing Agreement con Anthropic
3. **Minimización:** Solo se envía texto necesario, no documentos completos
4. **Logging:** Registro de tipos de PII detectados (sin valores)

### 3.3 Backups y Recovery

| Aspecto | Configuración |
|---------|---------------|
| Frecuencia | Backups diarios automáticos (Supabase Pro) |
| Retención | 7 días de backups + PITR |
| Ubicación | AWS EU (eu-west-1) - Cumple GDPR |
| RPO | 24 horas (backup diario) o minutos (PITR) |
| RTO | ~30 minutos (restore desde Supabase) |
| Verificación | Test de restore mensual documentado |

### 3.4 Compliance

- **GDPR:** Data residency en EU, DPA con proveedores, derecho al olvido
- **LOPDGDD:** Cumplimiento normativa española de protección de datos
- **SOC2:** Roadmap para certificación en Año 2+

---

## 4. Modelo de Datos

### 4.1 Entidades Principales

| Entidad | Descripción | Campos Clave |
|---------|-------------|--------------|
| **Tenant** | Cliente/Organización | id, name, subscription_plan, settings |
| **User** | Usuario del sistema | id, tenant_id, email, role, last_login |
| **Project** | Proyecto a analizar | id, tenant_id, name, type, status, coherence_score |
| **Document** | Documento subido | id, project_id, type, storage_url |
| **Analysis** | Resultado de análisis | id, project_id, type, status, result_json |
| **Alert** | Alerta detectada | id, project_id, severity, type, message |
| **Extraction** | Datos extraídos por IA | id, document_id, data_json, confidence |

### 4.2 Diagrama ER

```
Tenant (1) ──< (N) Project (1) ──< (N) Document
                    │
                    └──< (N) Analysis
                    │
                    └──< (N) Alert
```

---

## 5. API Reference

API REST documentada con OpenAPI 3.1. Autenticación mediante JWT (Supabase Auth).

### 5.1 Endpoints Principales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/projects` | Listar proyectos del tenant |
| POST | `/api/projects` | Crear nuevo proyecto |
| GET | `/api/projects/{id}` | Obtener detalle de proyecto |
| POST | `/api/documents/upload` | Subir documento a proyecto |
| POST | `/api/analysis/run` | Ejecutar análisis de coherencia |
| GET | `/api/analysis/{id}` | Obtener resultado de análisis |
| GET | `/api/projects/{id}/alerts` | Listar alertas del proyecto |
| PATCH | `/api/alerts/{id}/resolve` | Marcar alerta como resuelta |

### 5.2 Autenticación

```
Authorization: Bearer <jwt_token>
```

El JWT es emitido por Supabase Auth y contiene el tenant_id en los claims.

### 5.3 Rate Limiting

- **General:** 60 requests/minuto por tenant
- **Endpoints de AI:** 10 requests/minuto por tenant
- Respuesta 429 con header `Retry-After` cuando se excede

---

## 6. Sistema de Inteligencia Artificial

### 6.1 Flujo de Procesamiento

1. **Ingesta:** Usuario sube documento (PDF, Excel, BC3)
2. **Parsing:** Extracción de texto/datos según formato
3. **Anonymization:** Detección y reemplazo de PII
4. **Extracción IA:** Claude extrae cláusulas, hitos, partidas
5. **Cruce:** Motor de coherencia cruza los 3 documentos
6. **Alertas:** Generación de alertas por incoherencias
7. **Scoring:** Cálculo del Coherence Score (0-100)

### 6.2 Model Routing

| Tarea | Modelo | Coste | Uso |
|-------|--------|-------|-----|
| Clasificación simple | Claude Haiku | $0.25/1M tokens | ¿Necesita búsqueda? |
| Extracción estándar | Claude Sonnet | $3/1M tokens | Cláusulas, fechas |
| Análisis complejo | Claude Sonnet | $3/1M tokens | Coherencia, alertas |

### 6.3 Control de Costes

- Budget mensual por tenant: **50€** por defecto
- Alerta al **80%** de consumo
- Bloqueo (con mensaje) al **100%**
- Cache de respuestas para evitar re-procesamiento

### 6.4 Prompts Versionados

Los prompts se versionan en código para trazabilidad:
- `contract_extraction v1.0, v1.1...`
- `schedule_extraction v1.0...`
- `coherence_analysis v1.0...`

---

## 7. Roadmap de Implementación

### 7.1 Fases del MVP (12 semanas)

| Semanas | Fase | Entregables |
|---------|------|-------------|
| 1-2 | **Fundación** | Setup proyecto, Supabase + RLS, Auth, Middleware, Sentry |
| 3-4 | **Documentos** | Upload a R2, Parsers (PDF, Excel, BC3), UI de upload |
| 5-6 | **IA Core** | Anonymizer, AI Service, Prompts v1, Cost Controller, Cache |
| 7-8 | **Coherencia** | Motor de cruce, Generación de alertas, Coherence Score |
| 9-10 | **UI/UX** | Dashboard, Lista proyectos, Detalle, Alertas, Export PDF |
| 11-12 | **Hardening** | Tests seguridad, Tests AI, Load testing, Deploy prod, Pilots |

### 7.2 Fases Futuras

**Fase 2 - Copiloto de Compras (Semanas 13-20):**
- Generación automática de Plan de Compras
- Generación de borradores de RFQ
- Comparador contrato-factura
- Alertas proactivas de cumplimiento

**Fase 3 - Control de Ejecución (Semanas 21-28):**
- Ingesta de avance real
- Comparador planificado vs real
- Alertas predictivas
- API REST documentada

---

## 8. Análisis de Costes

### 8.1 Costes de Infraestructura

| Servicio | MVP (0-10 clientes) | Growth (50 clientes) |
|----------|---------------------|----------------------|
| Vercel (Frontend) | $0 | $20/mes |
| Railway (Backend) | $5/mes | $25/mes |
| Supabase (DB) | $0 | $25/mes |
| Upstash (Redis) | $0 | $10/mes |
| Cloudflare R2 | $0 | $15/mes |
| Claude API | ~$100/mes | ~$400/mes |
| Sentry | $0 | $0 |
| Dominio | €10/año | €10/año |
| **TOTAL** | **~$120/mes** | **~$500/mes** |

### 8.2 Unit Economics

| Métrica | Año 1 | Año 3 |
|---------|-------|-------|
| ARPU (mensual) | €600 | €900 |
| CAC | €3,000 | €4,000 |
| LTV | €18,000 | €32,400 |
| LTV:CAC | 6:1 | 8:1 |
| Churn mensual | <3% | <2% |

---

## 9. Análisis de Riesgos

| Riesgo | Prob. | Impacto | Mitigación |
|--------|-------|---------|------------|
| Data breach entre tenants | Baja | **Crítico** | RLS + Middleware + Tests automatizados |
| Costes AI descontrolados | Media | Alto | Budget caps + Model routing + Cache |
| Claude API outage | Media | Alto | Circuit breaker + Fallback a Haiku + Cache |
| Calidad de extracción baja | Media | Alto | Golden dataset + Evaluación continua |
| Free tier limits alcanzados | Media | Medio | Monitoreo de uso + Plan de migración |
| No conseguir primeros clientes | Media | **Crítico** | Red profesional + Pilots gratuitos |
| Competidor lanza antes | Media | Alto | Foco en nicho España + Relación con clientes |

---

## 10. Anexos

### 10.1 Glosario

| Término | Definición |
|---------|------------|
| **RLS** | Row Level Security - Mecanismo de PostgreSQL para filtrar filas por usuario |
| **Tenant** | Cliente/organización en un sistema multi-tenant |
| **PII** | Personally Identifiable Information - Datos que identifican a una persona |
| **Coherence Score** | Indicador 0-100 que mide la alineación entre documentos del proyecto |
| **BC3** | Formato estándar español para presupuestos de construcción (FIEBDC) |
| **RPO/RTO** | Recovery Point/Time Objective - Métricas de recuperación |

### 10.2 Referencias

- Anthropic Claude API Documentation: https://docs.anthropic.com
- Supabase Documentation: https://supabase.com/docs
- FastAPI Documentation: https://fastapi.tiangolo.com
- Next.js Documentation: https://nextjs.org/docs
- FIEBDC-3 (BC3) Specification: https://www.fiebdc.es

### 10.3 Historial de Versiones

| Versión | Fecha | Autor | Cambios |
|---------|-------|-------|---------|
| 1.0.0 | 29/12/2024 | Jesús | Documento inicial |

---

<div align="center">

**— Fin del Documento —**

*C2Pro - Contract Intelligence Platform*  
*© 2024 Todos los derechos reservados*

</div>

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
