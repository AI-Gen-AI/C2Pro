# Plan de Saneamiento y Evolución Arquitectónica de C2Pro (v2.0)

## Filosofía
Este plan representa nuestra hoja de ruta para transformar la base de código de C2Pro en un activo estratégico. Nuestra arquitectura objetivo es un **Monolito Modular**, donde cada módulo representa un Bounded Context de negocio, diseñado bajo principios de **Arquitectura Hexagonal/Limpia**. Priorizamos la claridad, la estabilidad y la capacidad de evolución sobre la adopción prematura de patrones de sistemas distribuidos.

## Roadmap por Fases
- **Fase 1 (Fundación):** Puntos 1-4. El objetivo es establecer la estructura del Monolito Modular y los patrones de desarrollo correctos. **No se inicia trabajo en nuevas funcionalidades hasta que la fundación esté sólidamente en marcha.**
- **Fase 2 (Capacidades Críticas):** Puntos 5-8. Con la fundación en su sitio, implementamos las capacidades de IA, observabilidad y componentes de negocio de manera robusta.
- **Fase 3 (Escalado y Madurez):** Puntos 9-11. Reforzamos nuestros contratos, estrategia de pruebas y documentación para escalar el equipo y el producto.

---
## 1. Fundación: Monolito Modular y DDD
- **Responsable**: Arquitecto Principal + Tech Lead
- **Logros Esperados**: Estructura de código única, sin ambigüedad, que refleje el negocio. Reduce drásticamente el tiempo de onboarding y la duplicación de código. Se establece la base para toda la evolución futura.
- **Tareas**:
  - **1.1. Oficializar la arquitectura de Monolito Modular**: Crear un ADR (Architectural Decision Record) que formalice esta elección.
  - **1.2. Definir los Módulos (Bounded Contexts)**: Mapear y crear la estructura de directorios para los módulos principales (ej: `documents`, `analysis`, `stakeholders`, `procurement`, `security`).
  - **1.3. Establecer la Política de Comunicación Inter-Módulo**: Formalizar la regla de que los módulos **solo** pueden comunicarse a través de interfaces públicas (Puertos) definidas en la capa de aplicación del módulo invocado. Prohibir importaciones directas a modelos, repositorios o servicios internos de otros módulos.
  - **1.4. Consolidar Código Duplicado**: Migrar la lógica dispersa (en `agents/`, `routers/`, etc.) a sus respectivos nuevos módulos.

---

## 2. Patrones de Diseño: Arquitectura Limpia/Hexagonal por Módulo
- **Responsable**: Backend Lead + Arquitecto
- **Logros Esperados**: Cumplimiento estricto de la "Dependency Rule". Lógica de negocio pura, desacoplada del framework, la base de datos y la UI. Testabilidad unitaria completa del dominio y la aplicación.
- **Tareas**:
  - **2.1. Implementar la Capa de Dominio**: Crear `domain/entities` (clases de negocio puras, sin decoradores de ORM) y `domain/value_objects` (Price, ClauseCode, CoherenceScore) con validación inmutable.
  - **2.2. Definir Puertos (Interfaces)**: En cada módulo, definir los `ports` para repositorios (`IRepository`) y servicios externos.
  - **2.3. Implementar Adaptadores**: Implementar los `adapters` en una capa de infraestructura, manteniendo el ORM (SQLAlchemy) y otros detalles de implementación aislados del dominio.
  - **2.4. Mover lógica a Casos de Uso (Application Services)**: Refactorizar los routers para que sean "delgados", delegando toda la lógica de orquestación a `application/use_cases`. Estos casos de uso son los únicos que interactúan con los repositorios y otros servicios.

---
## 3. Seguridad Multitenant: Defensa en Profundidad
- **Responsable**: Security Lead + Backend Lead
- **Logros Esperados**: Garantizar la separación de datos entre tenants a nivel de aplicación y de base de datos, eliminando el riesgo de fugas de información.
- **Tareas**:
  - **3.1. Implementar Middleware de Tenant Obligatorio**: Toda petición a la API debe pasar por un middleware que verifique y cargue el `tenant_id` en el contexto de la sesión, fallando si no está presente.
  - **3.2. Inyectar `tenant_id` en Repositorios**: Modificar los `adapters` de repositorios para que todos los queries (lectura y escritura) incluyan un filtro `WHERE tenant_id = ?` de forma automática y no opcional.
  - **3.3. Sincronizar Políticas de RLS**: Crear scripts (IaC) para generar y aplicar políticas de Row-Level Security en la base de datos que reflejen la lógica de autorización de la aplicación, como una segunda barrera de defensa.

---
## 4. Orquestación y Diseño de Agentes IA
- **Responsable**: AI Lead + Arquitecto Principal
- **Logros Esperados**: Un sistema de IA robusto, observable, controlable y económicamente viable. Swap de proveedor de LLM sin tocar el dominio.
- **Tareas**:
  - **4.1. Formalizar el Patrón de Orquestación (LangGraph)**: El flujo de análisis de documentos se implementará como un grafo de estados (LangGraph) en el módulo `analysis`. El estado (`AnalysisState`) será el "Blackboard" que contenga toda la información del análisis.
  - **4.2. Definir Interfaces de "Tool" y "Agente"**: Un "Agente" es un nodo en el grafo que orquesta "Tools". Un "Tool" es la implementación concreta de una capacidad (ej: un `adapter` que llama a Claude API, o una función determinística).
  - **4.3. Implementar Nodos de Validación**: Después de cada nodo que utilice un LLM para extracción de datos, añadir un nodo de validación determinístico que verifique el schema, formato y coherencia de los datos antes de continuar el flujo.
  - **4.4. Implementar Gestión y Versionado de Prompts**: Crear un sistema centralizado para gestionar las plantillas de prompts, permitiendo su versionado, carga dinámica y A/B testing. La `prompt_version` debe ser parte del `AnalysisState`.

---
## 5. Control de Costos y Resiliencia de IA
- **Responsable**: Platform Lead + AI Lead
- **Logros Esperados**: Gobierno de costos en tiempo real y un sistema que se degrada graciosamente en lugar de fallar catastróficamente.
- **Tareas**:
  - **5.1. Implementar Trazabilidad de Costos Acumulados**: Envolver los nodos de LangGraph para calcular el costo de cada llamada a LLM y sumarlo al `AnalysisState`.
  - **5.2. Implementar "Budget Circuit Breaker"**: Usar un `conditional_edge` en LangGraph para detener o desviar un flujo si el `run_cost` del `AnalysisState` supera un umbral del presupuesto del tenant.
  - **5.3. Implementar "Retry/Failure Circuit Breakers" por Tool**: En los `adapters` que llaman a APIs externas (Claude), implementar lógica de reintentos (con exponential backoff) y un circuit breaker para evitar llamadas repetidas a un servicio que está fallando.

---
## 6. Componentes de Dominio Clave
- **Responsable**: Product + Backend Lead
- **Logros Esperados**: Implementación pragmática de la lógica de negocio más compleja, evitando la sobre-ingeniería.
- **Tareas**:
  - **6.1. Refactorizar Coherence Engine**: Asegurar que la lógica de cálculo de coherencia resida en un `Domain Service` (`CoherenceScoringService`) y utilice el `Value Object` `CoherenceScore`.
  - **6.2. Abstraer Graph RAG**: Definir una interfaz `IGraphRepository` en la capa de dominio. La implementación inicial usará NetworkX como `adapter`, permitiendo una migración futura a Neo4j u otra base de datos de grafos sin cambiar la lógica de la aplicación.

---
## 7. Contrato API y Front-Back
- **Responsable**: Frontend Lead + API Lead + DevOps
- **Logros Esperados**: Contrato de API explícito y validado automáticamente, reduciendo bugs de integración.
- **Tareas**:
  - **7.1. Automatizar Generación de OpenAPI**: Integrar en el CI un paso que genere el `openapi.json` a partir del código FastAPI.
  - **7.2. Implementar Pruebas de Contrato**: El pipeline de CI del frontend debe fallar si se detecta un cambio en el schema de la API que rompa el contrato.

---
## 8. Estrategia de Pruebas Evolucionada
- **Responsable**: QA Lead + Tech Leads
- **Logros Esperados**: Una pirámide de pruebas equilibrada que brinde confianza para desplegar rápidamente.
- **Tareas**:
  - **8.1. Tests Unitarios de Dominio y Casos de Uso (Base)**: La mayor parte de las pruebas. Deben correr sin dependencias externas (usando repositorios en memoria).
  - **8.2. Tests de Integración para Adaptadores (Medio)**: Probar que los `adapters` (repositorios, clientes de API) interactúan correctamente con la base de datos real y otros servicios en un entorno de pruebas.
  - **8.3. Tests de Contrato para APIs Externas**: Validar que nuestro código es compatible con el contrato de las APIs de terceros (Claude, etc.) usando mocks.
  - **8.4. Tests E2E para Flujos Críticos (Punta)**: Mínimo número de tests que simulen un flujo de usuario completo (ej: subir documento -> recibir análisis).

---
## 9. Observabilidad (Gate 7)
- **Responsable**: Platform Lead
- **Logros Esperados**: Capacidad completa para trazar, depurar y monitorear cualquier petición a través del sistema.
- **Tareas**:
  - **9.1. Asegurar `trace_id` End-to-End**: Desde el ingreso a la API hasta la última llamada de base de datos.
  - **9.2. Logging Estructurado**: Implementar logging en formato JSON para todas las entradas de log.
  - **9.3. Visualización de Grafos de IA**: Integrar con una herramienta (como LangSmith o similar) para visualizar la ejecución de cada `AnalysisState` a través de los nodos de LangGraph.

---
## 10. Documentación Viva
- **Responsable**: Arquitecto Principal + Tech Leads
- **Logros Esperados**: Documentación que reduce la carga cognitiva y acelera la toma de decisiones.
- **Tareas**:
  - **10.1. Mantener ADRs (Architectural Decision Records)** para todas las decisiones significativas (Monolito Modular, elección de LangGraph, etc.).
  - **10.2. Generar Diagramas C4**: Crear y mantener actualizados los diagramas de Contexto, Contenedores y Componentes (por módulo) para visualizar la arquitectura.

---
## 11. Roadmap de Despliegue y Riesgos
- **Responsable**: Arquitecto Principal + Product
- **Logros Esperados**: Una evolución controlada y sin "big bangs" que pongan en riesgo la operación.
- **Tareas**:
  - **11.1. Mapear Fases a Hitos de Negocio**: Vincular la finalización de cada fase del plan a la capacidad de entregar ciertos tipos de funcionalidades de negocio.
  - **11.2. Identificar Riesgos por Fase**: Mantener una lista viva de los principales riesgos técnicos y de producto en cada fase y sus planes de mitigación.