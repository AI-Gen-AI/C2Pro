# ADR-001: Arquitectura de Monolito Modular

**Estado**: Aceptado
**Fecha**: 2026-01-27

## Contexto

El análisis del estado actual de la arquitectura (v1) reveló varios desafíos críticos:
- **Límites de Dominio Difusos**: Lógica de negocio dispersa en múltiples carpetas (`agents/`, `apps/api/src/`, etc.), causando una "esquizofrenia arquitectónica".
- **Acoplamiento a la Infraestructura**: El dominio de negocio está fuertemente acoplado a detalles de implementación como el ORM (SQLAlchemy) y el framework web (FastAPI).
- **Complejidad Accidental**: La falta de una estructura clara aumenta la carga cognitiva para el desarrollo y el onboarding, y crea un riesgo elevado de regresiones.

Se consideraron dos alternativas principales: migrar a microservicios o reestructurar el monolito existente.

## Decisión

Se adopta una arquitectura de **Monolito Modular** para C2Pro.

Esto significa:
1.  **Un Único Desplegable (Monolito)**: La aplicación seguirá siendo una única unidad de despliegue, simplificando la infraestructura y las operaciones.
2.  **Módulos Internos por Dominio (Modular)**: El código se organizará en módulos estrictos, cada uno correspondiendo a un Bounded Context del negocio (ej: `documents`, `analysis`, `stakeholders`).
3.  **Arquitectura Limpia/Hexagonal por Módulo**: Dentro de cada módulo, se aplicarán los principios de Arquitectura Limpia. La lógica de dominio será pura y agnóstica a la infraestructura, con dependencias apuntando siempre hacia adentro (UI -> Application -> Domain).
4.  **Política de Comunicación Explícita**: La comunicación entre módulos se realizará **exclusivamente a través de interfaces públicas (Puertos)** definidas en la capa de aplicación de cada módulo. Está terminantemente prohibido que un módulo acceda directamente a las clases internas (modelos ORM, entidades, etc.) de otro módulo.

## Consecuencias

### Positivas
- **Claridad y Bajo Acoplamiento**: Se establecen límites claros, reduciendo la complejidad y permitiendo que los módulos evolucionen de forma independiente.
- **Simplicidad Operativa**: Se evita la sobrecarga de gestionar un sistema distribuido (service discovery, tracing distribuido, latencia de red, etc.).
- **Consistencia Transaccional**: Las operaciones que abarcan varios módulos pueden gestionarse dentro de una única transacción local, lo cual es mucho más simple que las sagas distribuidas.
- **Camino Evolutivo**: Un módulo bien definido puede ser extraído a un microservicio en el futuro si surge una necesidad de negocio real (ej: escalabilidad independiente), con un impacto mínimo en el resto del sistema.

### Negativas
- **Escalabilidad Unificada**: Todos los módulos escalan juntos. Un módulo con alta carga puede requerir escalar toda la aplicación.
- **Riesgo Compartido**: Un bug crítico o una fuga de memoria en un módulo tiene el potencial de afectar a toda la aplicación.

## Justificación

Esta decisión ataca directamente el problema raíz (falta de límites y alto acoplamiento) sin introducir la complejidad masiva de los microservicios, para la cual el sistema y el equipo no están maduros. Prioriza la creación de una base de código sana y evolucionable sobre la adopción de tendencias. Evita el riesgo de "distribuir el caos".

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
