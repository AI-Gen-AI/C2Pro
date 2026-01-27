# Módulo 2: Arquitectura de Software

## Introducción al módulo y asignatura: Objetivos

### Introducción a la arquitectura de software

---

## ¿Por qué es clave para cualquier desarrollador?

**Carlos Azaustre**  
- Ingeniero de Software  
- Profesor Asociado, Universidad Europea  
- Google Developer Expert (GDE)  
- Microsoft MVP (Most Valuable Professional)

---

## ¿Qué aprenderás en esta asignatura?

- Qué es la arquitectura de software y su papel real en proyectos  
- Decisiones clave: separación, modularidad, escalabilidad  
- Estilos arquitectónicos: monolitos, microservicios, hexagonal, etc…  
- Cómo usar la IA como herramienta  

---

## Estructura completa del módulo

1. Introducción a la arquitectura de software  
2. Aplicando Clean Architecture con TypeScript  
3. Arquitecturas distribuidas y comunicación entre servicios  

---

## ¿Por qué importa la arquitectura?

### Con Arquitectura:
- Mantenibilidad  
- Escalabilidad  
- Claridad  

### Sin Arquitectura:
- Caos  
- Deuda Técnica  
- Cuellos de Botella  

---

## Preguntas que tendrás que resolver

- ¿Cómo organizo mi código?  
- ¿Cómo escalo mi aplicación?  
- ¿Cómo evito que mi app se vuelva inmanejable?  
- ¿Cómo separo responsabilidades?  
- ¿Qué pasa si quiero migrar a microservicios?  

---

## La IA como herramienta para arquitectos

- Comparar estilos arquitectónicos  
- Proponer decisiones técnicas con contexto  
- Generar esquemas y documentación  
- Automatizar partes del diseño  

---

## ¿Cómo será cada lección?

- Teoría clara y al grano  
- Ejemplos reales con TypeScript / Node.js  
- Uso transversal de IA  
- Reflexiones prácticas  

---

## ¡EMPEZAMOS!

**Diseñar software no es solo escribir código, es construir soluciones que duren**

---

# Módulo 2: Arquitectura de Software

## ¿Qué es la arquitectura de software?

### Introducción
Mucho más que dibujar cajas y flechas.

---

## Definición práctica

> “El conjunto de decisiones estructurales que determinan cómo se organiza y comunica un sistema de software.”

Incluye decisiones sobre:
- Módulos  
- Relaciones  
- Responsabilidades  
- Tecnologías  
- Evolución  

---

## La arquitectura permanece

> “La arquitectura no es solo lo que defines al principio… es lo que aguanta con el paso del tiempo.”

La diferencia entre un sistema bien mantenido y uno degradado se hace evidente con el tiempo.

---

## ¿Arquitectura, Diseño o Programación?

| Nivel         | ¿Qué decide?                                | Ejemplo                       |
|---------------|----------------------------------------------|-------------------------------|
| Programación  | Código específico (funciones, clases, etc.)  | `calcularTotal()`             |
| Diseño        | Estructura interna (patrones, principios)    | Repositorio, principios SOLID |
| Arquitectura  | Organización global y decisiones estructurales | Monolito vs Microservicios    |

---

## Ejemplo: App de e-commerce

1. ¿Monolito o Microservicios?  
2. ¿Dominios separados? ¿Capas?  
3. ¿Qué patrones de diseño aplicar?

---

## ¿Quién toma decisiones arquitectónicas?

> “Cada desarrollador toma decisiones que afectan a la arquitectura.”

📌 No es un rol específico, es una **responsabilidad compartida**.

---

## ¿Qué pasa sin una buena arquitectura?

✅ Proyecto con buena arquitectura:
- Escalable  
- Mantenible  
- Preparado para el cambio  

❌ Proyecto sin arquitectura:
- Crece desordenado  
- Costoso de mantener  
- Bugs frecuentes  

---

## La arquitectura importa más con el tiempo

A medida que el sistema crece, **el impacto de la arquitectura también lo hace**.

*(Gráfico de la página 9 muestra cómo aumenta el “coste del cambio” con el tiempo si la arquitectura no es buena.)*

---

## IA como apoyo en decisiones arquitectónicas

La inteligencia artificial puede ayudarte a:
- Comparar estilos y patrones  
- Evaluar ventajas y riesgos  
- Proponer estructuras y tecnologías  
- Generar documentación y flujos  

---

## Próxima Lección

### Decisiones Arquitectónicas Clave - Parte 1

> “Cada decisión estructural que tomas… es una decisión arquitectónica.”

---

# Módulo 2: Arquitectura de Software

## Decisiones Arquitectónicas Clave - Parte 1

### Principios que toda buena arquitectura debe aplicar

---

## ¿Por qué son clave las decisiones arquitectónicas?

> “Independientemente del estilo, hay principios universales que marcan la diferencia.”

- Afectan al mantenimiento, escalabilidad y claridad  
- Se toman desde el inicio (y se pagan si no lo haces)  
- La IA puede ayudarte a evaluarlas, pero la decisión es tuya  

---

## 1. Separación de responsabilidades

> “Cuando todo es responsabilidad de todos… nadie se hace cargo de nada.”

- Basado en **SRP** (Single Responsibility Principle)  
- No mezclar lógica de dominio con acceso a datos o presentación  
- Favorece el cambio sin romper todo  

---

## 2. Modularidad

✅ **Recomendación**: Modularidad por dominio funcional  

- **Agrupación por capas**: controladores, servicios, repositorios  
- **Agrupación por dominio**: `users`, `checkout`, `orders`, etc.  

---

## 3. Aislar la lógica de negocio

> “Tu dominio no debería saber que existe Express ni MongoDB.”

**Ventajas:**

- El core no depende de la tecnología  
- Test sin mocks complejos  
- Evolución sin dolor  

---

## 4. Escalabilidad Organizacional

🎯 **Meta**: Escalar sin fricciones entre personas y equipos  

**Conceptos Clave:**

- Equipos autónomos  
- Bounded Contexts  
- APIs contractuales  

---

## Resumen de decisiones clave

| Decisión                        | Beneficio Principal                                |
|--------------------------------|-----------------------------------------------------|
| Separación de responsabilidades | Código claro y con foco                            |
| Modularidad funcional           | Componentes fáciles de mantener y probar           |
| Aislamiento del dominio         | Independencia tecnológica                          |
| Escalabilidad organizacional    | Equipos que avanzan sin bloquearse entre sí        |

---

# Módulo 2: Arquitectura de Software

## Decisiones Arquitectónicas Clave - Parte 2

### De la teoría a producción

---

## Recordando la Parte 1

- Separación de responsabilidades  
- Modularidad  
- Aislamiento del dominio  
- Escalabilidad organizacional  

🔜 Ahora: decisiones críticas en **producción**

---

## Rendimiento & Escalabilidad

- Cachés: CDN, Redis, base de datos  
- Servicios stateless + colas  
- Queries optimizadas (índices, paginación)  
- Latencia objetivo: definir metas claras  
  - *Ejemplo*: checkout < 200 ms  

---

## Resiliencia & Tolerancia a fallos

- Timeouts + Retries  
- Circuit breakers  
- Idempotencia en operaciones críticas  
- Sagas / Outbox para consistencia  
  - *Ejemplo*: pago procesado una sola vez  

---

## Seguridad por diseño

- Autenticación & Autorización (OAuth2, OIDC)  
- Principio de **mínimo privilegio**  
- Secretos en vaults  
- Validación de entrada y salida  
- Cifrado + logs de auditoría  
- Rate limiting  

⚠️ *La seguridad no es un parche, es parte del diseño*

---

## Observabilidad

- Logs estructurados  
- Métricas (latencia, errores, uso de memoria)  
- Trazas distribuidas  
- SLIs: indicadores concretos  
- SLOs: objetivos medibles  

📝 *Ejemplo*:  
- SLI: latencia de checkout  
- SLO: 95% de las solicitudes < 200 ms  

---

## Evolución segura (sin miedo)

- Versionado de APIs  
- Feature flags / canary releases  
- Compatibilidad hacia atrás  
- Contratos de servicio (tests de contrato)  

➡️ *Cambia el sistema sin romper el negocio*

---

## Datos & Almacenamiento

- Elección de base de datos por caso de uso  
- Ownership de datos por dominio  
- Lecturas denormalizadas  
- Migraciones versionadas  
- Planes de rollback  

---

## Resumen de decisiones clave – Parte 2

- ✅ Rendimiento & escalabilidad  
- ✅ Resiliencia & tolerancia a fallos  
- ✅ Seguridad desde el diseño  
- ✅ Observabilidad  
- ✅ Evolución segura  
- ✅ Datos & persistencia  

---

## Próxima Lección

### Estilos de arquitectura: Introducción

> “Las decisiones arquitectónicas sientan las bases… los estilos le dan forma.”

---

# Módulo 2: Arquitectura de Software

## Estilos de Arquitectura: Introducción

### Estrategias para organizar sistemas de software

---

## ¿Qué es un estilo de arquitectura?

- Forma de estructurar y desplegar software  
- Optimiza unas cosas, sacrifica otras  
- No existe “la mejor arquitectura”  
- Solo la más adecuada para tu **contexto**  

---

## Estilos principales

- Monolito Modular  
- Microservicios  
- Hexagonal (Ports & Adapters)  
- Clean Architecture  
- Event-Driven Architecture  

📌 *Algunos se enfocan en el despliegue, otros en el diseño interno*

---

## Criterios para elegir un estilo

- Topología de despliegue  
- Acoplamiento y comunicación  
- Datos y límites  
- Equipo y **Conway’s Law**  
- Requisitos no funcionales (NFRs)  

⚠️ *La arquitectura más cara es la que no cumple tus NFRs*

---

## Ejemplo: e-commerce con Node/TypeScript

- **Monolito Modular** → simplicidad y velocidad  
- **Microservicios** → equipos paralelos, servicios aislados  
- **Hexagonal/Clean** → dominio protegido, adaptadores intercambiables  
- **Event-Driven** → analítica y reactividad en tiempo real  

---

## Trade-offs: Qué ganas y qué pagas

- **Monolito Modular**: ✅ sencillez, ❌ riesgo de “bola de barro”  
- **Microservicios**: ✅ autonomía, ❌ complejidad operativa  
- **Hexagonal/Clean**: ✅ testabilidad, ❌ requiere disciplina  
- **Event-Driven**: ✅ desacoplamiento, ❌ debugging complejo  

---

## Errores comunes

- Adoptar microservicios demasiado pronto → “monolito distribuido”  
- Monolito sin modularidad → “big ball of mud”  
- Event-Driven por moda → complejidad innecesaria  
- Hexagonal solo de etiqueta → adaptadores vacíos, acoplamientos ocultos  

---

## Camino práctico recomendado

- Monolito Modular + Hexagonal/Clean  
- Eventos internos (pub/sub)  
- Extraer módulos críticos → microservicios  
- Formalizar bus de eventos y contratos  

✅ *Empieza simple, evoluciona según el contexto*

---

## IA en decisiones arquitectónicas

- Comparar estilos según requisitos  
- Generar ADRs (Architecture Decision Records)  
- Revisar límites y dependencias  
- Proponer contratos de APIs y eventos  

---

## Próxima Lección

### Estilos de arquitectura: Monolito Modular

> “La base más común para empezar proyectos”

---

# Módulo 2: Arquitectura de Software

## Estilos de Arquitectura: Monolito Modular

### Un único despliegue, múltiples módulos

---

## ¿Qué es un monolito modular?

- Un **único artefacto** desplegable  
- Módulos separados por **dominio**  
- No es una “bola de barro”  
- Se combina muy bien con **Hexagonal** o **Clean Architecture**  

---

## Ventajas

✅ Sencillez operativa (un solo despliegue)  
✅ Latencia interna mínima  
✅ Alta productividad  
✅ Refactors más fáciles  

---

## Riesgos

❌ Riesgo de “bola de barro” si no hay modularidad real  
❌ Un único despliegue puede convertirse en **cuello de botella**  
❌ Una caída afecta a todo el sistema  

---

## Anatomía del monolito

- Módulos **alineados al dominio**  
- Capas internas:  
  - `domain`  
  - `application`  
  - `infra`  
- Las dependencias **siempre apuntan hacia el dominio**  

---

## Ejemplo en Node/TypeScript

```ts
// Dominio
class Product {
  changePrice() { … }
}

// Puerto
interface ProductRepo {
  findById(): Product;
  save(product: Product): void;
}

// Caso de uso
updateProductPrice(repo, { id, price })


# Módulo 2: Arquitectura de Software

## Estilos de Arquitectura: Microservicios

### Servicios pequeños, autónomos, desplegables por separado

---

## ¿Qué son los microservicios?

- Servicios **pequeños e independientes**  
- Cada uno con una única **responsabilidad de negocio**  
- Comunicación vía **APIs** o **eventos**  
- Despliegue y escalado independientes  

---

## Beneficios

✅ Escalabilidad técnica (solo el servicio que lo necesita)  
✅ Escalabilidad organizacional (equipos autónomos)  
✅ Despliegues independientes  
✅ Tolerancia a fallos  

---

## Retos y costes

❌ Complejidad operativa (infraestructura, CI/CD)  
❌ Observabilidad distribuida  
❌ Consistencia eventual de datos  
❌ Latencia de red  
❌ Testing más costoso  

---

## Comunicación

- **Síncrona** → HTTP, gRPC  
- **Asíncrona** → Eventos, mensajería  

🔧 *Usar lo adecuado para cada caso*

---

## Datos

- Cada servicio es **dueño de sus datos**  
- No hay `joins` entre servicios  
- Se comparten datos mediante **APIs** o **eventos**  
- Se pueden usar **proyecciones locales** si es necesario  

---

## Evolución desde monolito

1. Se empieza con un **monolito modular**  
2. Se extrae un **módulo caliente** como microservicio  
3. Se le asigna una nueva base de datos + APIs/Eventos  
4. Se escalada y se le asigna equipo propio  

---

## Buenas prácticas

- Contratos claros (APIs, eventos versionados)  
- Automatización: CI/CD, tests, monitoreo  
- Diseñar para fallos: timeouts, retries, circuit breakers  
- Observabilidad obligatoria: logs, métricas, trazas  
- **Tamaño justo**: pequeño, pero no demasiado  

---

## ¿Cuándo convienen?

✅ Varios equipos paralelos  
✅ Diferentes necesidades de escalado  
✅ Necesidad de despliegues independientes rápidos  

---

## ¿Cuándo NO convienen?

❌ Equipo pequeño  
❌ No tienes infraestructura madura  
❌ Estás en etapa de validación inicial del producto  

---

## Conclusión

> “Los microservicios te dan independencia y escalabilidad… pero a cambio de complejidad.”

---

## Próxima lección

### Arquitectura Hexagonal (Ports & Adapters)

---
# Módulo 2: Arquitectura de Software

## Estilos de Arquitectura: Hexagonal (Ports & Adapters)

---

## Idea principal

- Separar **lógica de negocio** de la infraestructura  
- Núcleo estable = **dominio**  
- Bordes flexibles = **adaptadores**  
- Contratos claros = **puertos**

---

## ¿Qué son Puertos y Adaptadores?

- **Puerto** = interfaz / contrato  
- **Adaptador** = implementación concreta del puerto

**Ejemplo:**
- `PaymentPort`  
- `StripeAdapter` / `PayPalAdapter`

---

## Ejemplo en Node/TypeScript

```ts
// Puerto
interface ProductRepo {
  findById();
  save();
}

// Caso de uso
updateProductPrice(repo, { id, price });

// Adaptador
class PgProductRepo implements ProductRepo {
  ...
}
Beneficios
✅ Dominio limpio y estable
✅ Alta testabilidad
✅ Flexibilidad tecnológica
✅ Múltiples interfaces de entrada/salida

Múltiples entradas/salidas posibles
Un mismo caso de uso puede exponerse a través de:

REST API

CLI

Mensajería/Eventos

(Ver diagrama en página 7 que muestra adaptadores rodeando al dominio)

Comparación: Hexagonal vs Clean Architecture
Hexagonal: foco en puertos y adaptadores

Clean: capas concéntricas

Ambos comparten el principio de que el dominio no depende de la tecnología

(El diagrama en la página 8 compara ambas visualmente)

Buenas prácticas
Interfaces claras como puertos

Usar nombres de dominio, no de tecnología

Adaptadores en carpeta infra

Wiring (conexión) en el composition root

Tests de contrato entre puertos y adaptadores

¿Cuándo conviene usar Hexagonal?
✅ Dominios complejos
✅ Integraciones múltiples
✅ Necesidad de alta testabilidad
❌ No es recomendable para apps muy pequeñas o triviales

Cierre
“Hexagonal separa el qué del cómo”

Dominio = qué hace tu sistema

Adaptadores = cómo se conecta al mundo


# Módulo 2: Arquitectura de Software

## Estilos de Arquitectura: Clean Architecture

---

## Separar el QUÉ del CÓMO

![Capas Clean Architecture](https://myaidrive.com/preview/file/000000006920720ab854ba57412b868a?pdfPage=2)

---

## Idea Principal

- Capas concéntricas  
- Dependencias siempre hacia adentro  
- El dominio no conoce frameworks ni tecnología  

![Diagrama de capas](https://myaidrive.com/preview/file/000000006920720ab854ba57412b868a?pdfPage=3)

---

## Capas de Clean Architecture

- **Dominio** (Entities / Value Objects): Reglas de negocio  
- **Aplicación** (Use Cases / Ports): Orquestación  
- **Adaptadores**: Controladores, repositorios concretos  
- **Infraestructura**: DB, HTTP server, frameworks  

---

## Beneficios

✅ Dominio limpio y estable  
✅ Alta testabilidad  
✅ Flexibilidad tecnológica  
✅ Mantenibilidad a largo plazo  

---

## Estructura de Proyecto (Node/TypeScript)

```text
src/
  domain/
  application/
  adapters/
    http/
    persistence/
  infrastructure/
  shared/
Ejemplo en Node/TypeScript
// Use case
class UpdateProductPrice {
  constructor(private repo: ProductRepository) {}

  async execute({ id, price }) {
    ...
  }
}
Testing en Clean Architecture
Unit tests en dominio y casos de uso

Contract tests para puertos/adaptadores

Integration tests para adaptadores reales

Fake repos para tests rápidos


Errores Comunes
❌ Anemia de dominio
❌ Fugas de framework
❌ Overengineering
❌ DTOs acoplados a DB

Buenas Prácticas
Interfaces claras como puertos

Adaptadores separados en infra

DTOs propios por caso de uso

Composition root único

Cross-cutting vía puertos

¿Cuándo conviene?
✅ Dominios complejos
✅ Cambios tecnológicos previstos
✅ Múltiples interfaces (REST, CLI, eventos)
✅ Necesidad de testabilidad
❌ Apps muy pequeñas / triviales

Cierre
“Clean Architecture protege el negocio del cambio tecnológico”

# Módulo 2: Arquitectura de Software

## Estilos de Arquitectura: Event-Driven Architecture

---

## ¿Qué es Event-Driven Architecture (EDA)?

- Sistemas que reaccionan a **eventos**
- Cada evento representa un **hecho pasado** en el dominio
- Ejemplos: `OrderPlaced`, `PaymentCaptured`
- Contiene: `id`, `timestamp`, `correlationId`, `versión`  
🟡 Ejemplo visual (p.3):  
```json
OrderPlaced {
  id: 1,
  orderId: 1001,
  userId: 50,
  total: 150.00
}
¿Qué resuelve EDA?
Desacopla productores y consumidores

Permite extender funcionalidades sin tocar el productor

Escalabilidad de lectores/escritores

Facilita auditoría y reprocesamiento

Topología típica
Broker: Kafka, RabbitMQ, NATS

Uso de tópicos o colas

Particiones para orden por clave

Grupos de consumo para balanceo
🔵 Diagrama en página 5 muestra cómo un OrderPlaced es consumido por múltiples servicios (Shipping, Customer, Analytics)

Semántica de entrega
At-most-once: posible pérdida de eventos

At-least-once: posible duplicación → requiere idempotencia

Exactly-once: costoso y difícil de lograr

Idempotencia
Uso de idempotency keys

Tablas de deduplicación

Registrar event.id procesados para evitar dobles ejecuciones
🟢 Diagrama en página 7 ilustra cómo se guarda en una "Event Table" cada evento procesado para evitar re-ejecución

Outbox & Sagas
Outbox: guardar el evento y el cambio de estado en la misma transacción

Sagas:

Coreografía: cada servicio reacciona a eventos

Orquestación: un servicio central coordina el flujo completo
📘 Diagrama en página 8 muestra una saga con servicios de órdenes, inventario y pagos

Publicar y Consumir
Publisher: emite el evento al broker

Consumer: procesa el evento

Uso de ack/nack y colas de errores (DLQ – Dead Letter Queue)

Evolución de eventos
Agregar campos opcionales = compatible

Cambios incompatibles → versionado (e.g., OrderPlaced.v2)

Uso de Schema Registry recomendado para validar compatibilidad

Observabilidad
Agregar CorrelationId a todos los eventos

Métricas clave: lag, errores, reintentos, profundidad DLQ

Trazas distribuidas

Reprocesamiento debe ser seguro (idempotente)
📊 Diagrama en página 11 ilustra un dashboard con métricas y logs correlacionados

¿Cuándo usar EDA?
✅ Cuando necesitas:

Desacoplar módulos

Reacciones múltiples al mismo evento

Escalabilidad y replay de eventos

❌ Evitar si:

Necesitas consistencia inmediata

Tienes equipo pequeño o sin experiencia en mensajería

No hay un caso claro, genera complejidad innecesaria

Cierre
“EDA no reemplaza a Clean… lo complementa.
En Clean, el EventBus es un puerto; productores y consumidores son adaptadores.”
📍 (p.13)

# Módulo 2: Arquitectura de Software

## Usar la IA para comparar estilos

---

## De la teoría a la práctica

- Utilizar IA para análisis arquitectónico  
- Comparar estilos (Monolito, Microservicios, EDA)  
- Formular decisiones técnicas con contexto  

---

## Caso Práctico: E-commerce

- Módulos: catálogo, usuarios, carrito, pedidos, pagos  
- Situación actual: 5 devs  
- Escalado previsto: 12 devs en 1 año  
- Requisito: lanzar rápido, escalar después:contentReference[oaicite:0]{index=0}

---

## Primer paso: análisis general

- Comparar Monolito Modular, Microservicios y Event-Driven  
- Contexto: e-commerce, crecimiento de 5 a 20 devs  
- Incluir: pros, contras, riesgos para cada estilo:contentReference[oaicite:1]{index=1}

---

## Refinar con NFRs (Requisitos No Funcionales)

- Latencia checkout < 200ms (P95)  
- Disponibilidad mínima: 99.9%  
- Bajo presupuesto inicial  
- Alta mantenibilidad en 3 años  
- 📌 Pregunta a la IA: ¿qué estilo se ajusta mejor?:contentReference[oaicite:2]{index=2}

---

## Escenarios Evolutivos

- Si el sistema llega a 100k usuarios concurrentes y 20 devs  
- IA puede predecir problemas del Monolito Modular:  
  - Cuellos de botella  
  - Riesgos de despliegue  
- IA puede recomendar ventajas de Microservicios:  
  - Escalabilidad granular  
  - Autonomía por equipos:contentReference[oaicite:3]{index=3}

---

## Hexagonal vs Clean Architecture

- Comparación práctica en contexto de Monolito Modular con Node.js + TypeScript  
- IA puede explicar:  
  - Diferencia en capas y responsabilidades  
  - Impacto en testabilidad, adaptadores, puertos:contentReference[oaicite:4]{index=4}

---

## Crear un ADR con IA

**Architecture Decision Record (ADR):**  
- Decisión: Empezar con Monolito Modular + Clean Architecture  
- Contexto: simplicidad operativa, equipo pequeño  
- Consecuencias:  
  - Buen punto de partida  
  - Escalable hacia Microservicios en el futuro:contentReference[oaicite:5]{index=5}

---

## Riesgos y mitigaciones con Event-Driven

- Riesgos si el equipo no domina mensajería:  
  - Complejidad técnica  
  - Problemas de consistencia  
  - Dificultad de debugging  
- Mitigaciones sugeridas por IA:  
  - Empezar con eventos internos  
  - Uso de plantillas para consumidores/productores  
  - Observabilidad y trazabilidad desde el inicio:contentReference[oaicite:6]{index=6}

---

## Buen uso de la IA

✅ Acelerador de discusión  
✅ Identificador de riesgos  
✅ Generador de borradores (ADRs, comparativas)  
❌ No reemplaza al juicio humano  
❌ No decide por el equipo:contentReference[oaicite:7]{index=7}

---

## Cierre

> “La IA nos ayuda a analizar, comparar y documentar.  
> La decisión final siempre es del equipo.”  

➡️ Próxima lección: **Práctica – Proponer una arquitectura**

---

# Módulo 2: Arquitectura de Software

## Usar la IA para comparar estilos

---

## De la teoría a la práctica

- Utilizar IA para análisis arquitectónico  
- Comparar estilos (Monolito, Microservicios, EDA)  
- Formular decisiones técnicas con contexto  

---

## Caso Práctico: E-commerce

- Módulos: catálogo, usuarios, carrito, pedidos, pagos  
- Situación actual: 5 devs  
- Escalado previsto: 12 devs en 1 año  
- Requisito: lanzar rápido, escalar después:contentReference[oaicite:0]{index=0}

---

## Primer paso: análisis general

- Comparar Monolito Modular, Microservicios y Event-Driven  
- Contexto: e-commerce, crecimiento de 5 a 20 devs  
- Incluir: pros, contras, riesgos para cada estilo:contentReference[oaicite:1]{index=1}

---

## Refinar con NFRs (Requisitos No Funcionales)

- Latencia checkout < 200ms (P95)  
- Disponibilidad mínima: 99.9%  
- Bajo presupuesto inicial  
- Alta mantenibilidad en 3 años  
- 📌 Pregunta a la IA: ¿qué estilo se ajusta mejor?:contentReference[oaicite:2]{index=2}

---

## Escenarios Evolutivos

- Si el sistema llega a 100k usuarios concurrentes y 20 devs  
- IA puede predecir problemas del Monolito Modular:  
  - Cuellos de botella  
  - Riesgos de despliegue  
- IA puede recomendar ventajas de Microservicios:  
  - Escalabilidad granular  
  - Autonomía por equipos:contentReference[oaicite:3]{index=3}

---

## Hexagonal vs Clean Architecture

- Comparación práctica en contexto de Monolito Modular con Node.js + TypeScript  
- IA puede explicar:  
  - Diferencia en capas y responsabilidades  
  - Impacto en testabilidad, adaptadores, puertos:contentReference[oaicite:4]{index=4}

---

## Crear un ADR con IA

**Architecture Decision Record (ADR):**  
- Decisión: Empezar con Monolito Modular + Clean Architecture  
- Contexto: simplicidad operativa, equipo pequeño  
- Consecuencias:  
  - Buen punto de partida  
  - Escalable hacia Microservicios en el futuro:contentReference[oaicite:5]{index=5}

---

## Riesgos y mitigaciones con Event-Driven

- Riesgos si el equipo no domina mensajería:  
  - Complejidad técnica  
  - Problemas de consistencia  
  - Dificultad de debugging  
- Mitigaciones sugeridas por IA:  
  - Empezar con eventos internos  
  - Uso de plantillas para consumidores/productores  
  - Observabilidad y trazabilidad desde el inicio:contentReference[oaicite:6]{index=6}

---

## Buen uso de la IA

✅ Acelerador de discusión  
✅ Identificador de riesgos  
✅ Generador de borradores (ADRs, comparativas)  
❌ No reemplaza al juicio humano  
❌ No decide por el equipo:contentReference[oaicite:7]{index=7}

---

## Cierre

> “La IA nos ayuda a analizar, comparar y documentar.  
> La decisión final siempre es del equipo.”  

➡️ Próxima lección: **Práctica – Proponer una arquitectura**

---
# Módulo 2: Arquitectura de Software

## PRÁCTICA: PROPONER UNA ARQUITECTURA A UN PROYECTO

### Introducción a la arquitectura de software

---

## Caso real de un e-commerce

🛒 Proyecto de comercio electrónico con módulos como:  
- Catálogo  
- Carrito  
- Pedidos  
- Pagos  
- Usuarios  
- Notificaciones:contentReference[oaicite:0]{index=0}

---

## Brief del Proyecto

**Proyecto:** E-commerce completo  
**Equipo:** 5 desarrolladores → se espera escalar a 12 en 1 año  

### Requisitos No Funcionales (NFRs):

- P95 checkout menor a 200 ms  
- Disponibilidad: 99.9%  
- Presupuesto ajustado  
- Requiere **auditoría de pagos**:contentReference[oaicite:1]{index=1}

---

## Propuesta arquitectónica

📄 La propuesta final debe incluir:

- Un **ADR** documentado con la decisión arquitectónica  
- Estructura del proyecto basada en **Clean Architecture**  
- **Contratos de APIs** y **eventos** bien definidos  
- Un **plan de evolución** progresivo hacia microservicios conforme el equipo crece y las necesidades se expanden:contentReference[oaicite:2]{index=2}

---
## Prompts 

# Clarificación y checklist
Actúa como arquitecto. Reescribe este brief detectando ambigüedades y lista las 10 preguntas clave que debo resolver antes de decidir la arquitectura.
Incluye NFRs propuestos con SLIs/SLOs iniciales.

# Eleccion inicial de estilo
“Decisión inicial típica: Monolito Modular + Clean Architecture, con eventos in-process. Plan de evolución hacia microservicios/EDA si aparecen cuellos.”

# Comparación rápida
Compara Monolito Modular vs Microservicios vs EDA para el brief anterior.
Usa NFRs dados y equipo actual. Dame pros/contras/risks y recomendación.

# Generar ADR
Genera un ADR: “Iniciar con Monolito Modular + Clean Architecture”.
Contexto, Decisión, Consecuencias (positivas/negativas) y Criterios de revisión.

# Módulo 2: Arquitectura de Software

## Conclusiones

### Introducción a la Arquitectura de Software

---

## Lo que aprendimos

- Qué es realmente la arquitectura  
- Decisiones arquitectónicas clave  
- Estilos principales:  
  - Monolito  
  - Microservicios  
  - Hexagonal  
  - Clean Architecture  
  - Event-Driven Architecture (EDA)  
- Uso de la IA como copiloto en arquitectura  
- Práctica: diseñar un e-commerce desde cero:contentReference[oaicite:0]{index=0}

---

## Ideas clave

- **Arquitectura = decisiones duraderas**  
- No hay un estilo único correcto → **depende del contexto**  
- **La IA es un acelerador, no un sustituto** del juicio técnico:contentReference[oaicite:1]{index=1}

---
# Módulo 2: Arquitectura de Software

## Principios Clave  
**Aplicando Clean Architecture con TypeScript**

---

## Arranque del QUÉ al CÓMO

![Capas de Clean Architecture](https://myaidrive.com/preview/file/00000000764871f4949eddaf897b4949?pdfPage=2)

---

## Principio 1 – Regla de Dependencias

✔ El **dominio** importa solo tipos propios  
✔ La **aplicación** importa **puertos** (interfaces), no adaptadores  
✔ La **infraestructura** implementa puertos y conoce frameworks

📍 [Ver imagen, página 3](https://myaidrive.com/preview/file/00000000764871f4949eddaf897b4949?pdfPage=3)

---

## Principio 2 – Modelo de Dominio Explícito

✔ El modelo del dominio debe ser claro y autónomo.  
✔ No acoplado a transporte ni a frameworks externos

📍 [Ver imagen, página 4](https://myaidrive.com/preview/file/00000000764871f4949eddaf897b4949?pdfPage=4)

---

## Principio 3 – Casos de Uso

⚠️ **Los casos de uso orquestan, NO calculan.**  
Toda la lógica de negocio va en el dominio, no en los use cases

📍 [Ver imagen, página 5](https://myaidrive.com/preview/file/00000000764871f4949eddaf897b4949?pdfPage=5)

---

## Principio 4 – Puertos y Adaptadores

- Los **puertos** (interfaces) viven en la capa de aplicación  
- Los **adaptadores** (implementaciones) viven en infraestructura  

📍 [Ver imagen, página 6](https://myaidrive.com/preview/file/00000000764871f4949eddaf897b4949?pdfPage=6)

---

## Principio 5 – Gestión de errores y efectos

- DTOs entran/salen del sistema  
- **Entidades/VOs no deben cruzar la frontera de la aplicación** hacia afuera  
- Los efectos secundarios deben manejarse fuera del dominio

---

## Principio 6 – Testing

Los tests **refuerzan la arquitectura** y protegen límites:

- ✅ Dominio: puro → tests rápidos  
- ✅ Casos de uso: con dobles de puertos (fakes/in-memory)  
- ✅ Adaptadores: tests de contrato contra interfaces

---

## Principio 7 – Inversión de Dependencias

- La **composición (composition-root)** ocurre en el borde de la infraestructura  
- Es el único punto que conoce todas las capas

📍 [Ver imagen, página 9](https://myaidrive.com/preview/file/00000000764871f4949eddaf897b4949?pdfPage=9)

---

## Antipatrones Frecuentes

🚫 Importar `express` o `prisma` en dominio/aplicación  
🚫 DTOs de HTTP/DB filtrándose al dominio  
🚫 Casos de uso con lógica compleja (debe ir al dominio)  
🚫 Singletons globales  
🚫 Leer `process.env` en dominio/aplicación

📍 [Ver imagen de advertencia, página 10](https://myaidrive.com/preview/file/00000000764871f4949eddaf897b4949?pdfPage=10)

---

## IA como Copiloto (Tips)

- 🧠 **Extraer límites y puertos**  
  “Dado este caso de uso {texto}, propone puertos necesarios con nombres de dominio.”
  
- 🔍 **Revisar dependencias**  
  “Revisa este árbol e indica violaciones a la Regla de Dependencias.”

- 🔄 **Diseñar DTOs**  
  “Para el caso de uso {X}, genera DTOs planos y tests de aceptación sin IO.”

- 🧪 **Generar dobles de test**  
  “Crea un repositorio en memoria que implemente esta interfaz y ejemplos de uso en Vitest.”

📍 [Ver página 11](https://myaidrive.com/preview/file/00000000764871f4949eddaf897b4949?pdfPage=11)

---
# Módulo 2: Arquitectura de Software

## Estructura de carpetas en un proyecto Clean  
**Aplicando Clean Architecture con TypeScript**

---

## Estructura opinionada de carpetas

- Tres capas principales:  
  - **Domain**  
  - **Application**  
  - **Infrastructure**  

📍 Diagrama visual en [página 2](https://myaidrive.com/preview/file/0000000014c071f4842f97ee9530e708?pdfPage=2)

---

## Dos sabores: mínima y escalable

- **Mínima**: para equipos pequeños o prototipos  
- **Escalable**: pensada para crecer con múltiples adaptadores y módulos:contentReference[oaicite:0]{index=0}

---

## Estructura escalable

```bash
/src
  /domain
    /entities          # Domain services puros (si los necesitas)
    /value-objects     # Objetos de valor
    /services          # Eventos de dominio (puros)
    /events
    /errors            # Errores del dominio (p. ej. DomainError)
  /application
    /use-cases         # Orquestación por caso de uso
    /ports             # Interfaces de repos, buses, clocks, mailers...
    /dto               # Tipos de entrada/salida (planos)
    /errors            # Errores de aplicación (p. ej. ValidationError)
  /infrastructure
    /persistence
      /in-memory       # Dobles (fakes) para tests/arranque
      /postgres        # Adaptadores reales
      /mappers         # Mapeo entidad <-> modelos de persistencia
    /http
      /controllers     # Adaptadores de entrada (HTTP)
      /routes          # Declaración de rutas
      /server.ts       # Bootstrap HTTP (Fastify/Express)
    /messaging         # Kafka/Rabbit/etc (cuando toque)
    /observability     # Logger, metrics, tracing
    /config            # Configuración (dotenv, etc.)
  /composition
    container.ts       # Composición raíz e inversión de dependencias
  /shared
    result.ts          # Result/Either
  utils.ts
main.ts


# Módulo 2: Arquitectura de Software

## Dominio: Entidades y Value Objects  
**Aplicando Clean Architecture con TypeScript**

---

## ¿Dónde está el dominio?

En el centro de la arquitectura:  
**Domain → Application → Infrastructure**  
📍 Diagrama visual en [página 2](https://myaidrive.com/preview/file/00000000650071f4aeaf9afce8848474?pdfPage=2)

---

## Value Objects (VOs)

- Inmutabilidad  
- Método `create()` para validación  
- Método `equals()` para comparación  
- Invariantes claras:contentReference[oaicite:0]{index=0}

---

## Ejemplo: Value Object `Price`

```ts
// src/domain/value-objects/Currency.ts
export type Currency = "EUR" | "USD"

// src/domain/value-objects/Price.ts
import { Currency } from "./Currency"

export class Price {
  private constructor(
    readonly amount: number,
    readonly currency: Currency
  ) {}

  static create(amount: number, currency: Currency) {
    if (!Number.isFinite(amount) || amount < 0)
      throw new InvalidPrice("Invalid amount")
    const rounded = Math.round(amount * 100) / 100
    return new Price(rounded, currency)
  }

  add(other: Price) {
    if (this.currency !== other.currency)
      throw new CurrencyMismatch()
    return Price.create(this.amount + other.amount, this.currency)
  }

  multiply(qty: number) {
    if (!Number.isInteger(qty) || qty <= 0)
      throw new InvalidQuantity()
    return Price.create(this.amount * qty, this.currency)
  }

  equals(other: Price) {
    return this.amount === other.amount && this.currency === other.currency
  }
}
📍 Ver código en página 4

Entidades y Aggregates
Tienen identidad

Contienen reglas de negocio internas

Garantizan consistencia de estado

Testing del Dominio
✅ Rápido

✅ Puro

✅ Significativo
📍 Ejemplos de test en páginas 7 y 8

// tests/domain/price.spec.ts
import { describe, it, expect } from "vitest"
import { Price } from "../../src/domain/value-objects/Price"

describe("Price", () => {
  it("no permite negativos y redondea a 2 decimales", () => {
    expect(() => Price.create(-1, "EUR")).toThrow()
    const p = Price.create(12.345, "EUR")
    expect(p.amount).toBe(12.35)
  })
})
Más tests con entidades
// tests/domain/order.spec.ts
const o = Order.create(OrderId("o-1"), CustomerId("c-1"))
o.addItem(SKU.create("abc-1"), Price.create(10, "EUR"), Quantity.create(2))
o.addItem(SKU.create("abc-2"), Price.create(5, "EUR"), Quantity.create(1))

expect(o.total().amount).toBe(25)
const ev = o.pullDomainEvents()
expect(ev.some(e => e.type === "order.created")).toBe(true)
expect(ev.some(e => e.type === "order.item_added")).toBe(true)
📍 Ver test en página 8

Antipatrones del dominio
🚫 Primitive obsession: usar string/number en lugar de VOs
🚫 Setters mutables → exponen estados inválidos
🚫 Lógica de negocio en controllers o repositorios
🚫 Uso excesivo de enums “Dios” y condicionales en cascada
🚫 Igualdad de entidad por valor en lugar de por ID
📍 Ver advertencias en página 9

IA como Copiloto
Descubrir invariantes
“Actúa como domain modeler. Dado este contexto {texto}, enumera invariantes candidatas y casos límite para VOs.”

Refactor de primitive obsession a VOs
“Propón Value Objects inmutables con create() y equals().”

Proponer eventos de dominio
“Para el agregado Order, sugiere eventos sin detalles de infraestructura.”

Revisión de errores
“¿Dónde usar excepciones y dónde Result? Propón una tabla de decisiones.”

📍 Prompts en página 10


# Módulo 2: Arquitectura de Software

## Casos de Uso: Lógica de la Aplicación  
**Aplicando Clean Architecture con TypeScript**

---

## Rol del Caso de Uso

- Orquestación, **no cálculo fino**  
- Lógica coordinadora entre capa de dominio y adaptadores externos  
- Usa DTOs de entrada y salida  
- Invoca puertos definidos en `application/ports`

📍 Diagrama de capas: Domain → Application → Infrastructure ([página 2](https://myaidrive.com/preview/file/00000000702471f482404abfb2991ee2?pdfPage=2)) :contentReference[oaicite:0]{index=0}

---

## Patrón `Result` para control de errores

```ts
// src/shared/result.ts
export type Ok<T> = { ok: true; value: T }
export type Fail<E> = { ok: false; error: E }
export type Result<T, E> = Ok<T> | Fail<E>

export const ok = <T>(value: T): Ok<T> => ({ ok: true, value })
export const fail = <E>(error: E): Fail<E> => ({ ok: false, error })

// src/application/errors.ts
export type ValidationError = { type: "validation"; message: string; details?: Record<string, string> }
export type NotFoundError = { type: "not_found"; resource: string; id: string }
export type ConflictError = { type: "conflict"; message: string }
export type InfraError = { type: "infrastructure"; message: string }
export type AppError = ValidationError | NotFoundError | ConflictError | InfraError


Ejemplo de flujo: AddItemToOrder

Validar entrada

Cargar pedido

Pedir precio actual

Invocar reglas del agregado order.addItem(...)

Publicar eventos

Persistir

Devolver DTO

📍 Ver secuencia en página 5

Uso de CQRS

Queries → lectura de datos

Commands → modifican estado

📍 Esquema simplificado en página 6

Antipatrones frecuentes

🚫 Devolver entidades desde el caso de uso
🚫 Acoplar a frameworks (Request, Response, Prisma, etc.)
🚫 Casos de uso como “mini-controller”
🚫 Capturar excepciones genéricas y tragarlas
🚫 No modelar errores como tipos, usar solo throw new Error(...)

📍 Ver advertencia visual en página 7

IA como Copiloto
Diseñar un caso de uso desde una historia

“Dada esta historia {texto}, propón DTOs in/out, puertos necesarios, tipos de error y flujo paso a paso. No uses tipos/frameworks.”

Generar fakes para tests

“Crea dobles en memoria que implementen estas interfaces: OrderRepository, PricingService, EventBus, con ejemplos en Vitest.”

Revisión de errores

“Analiza este caso de uso y clasifica cada throw/fail como:
validation, not_found, conflict, infrastructure. Sugiere estructura uniforme.”

Mapeo Entidad → DTO

“Dada la entidad Order y un DTO de salida, genera una función pura toOrderSummaryDTO(order) que no filtre detalles internos.”


# Módulo 2: Arquitectura de Software

## Puertos y Adaptadores  
**Interfaces + Implementación**  
Aplicando Clean Architecture con TypeScript

---

## ¿Qué son?

- Los **puertos** expresan *necesidades del caso de uso*  
- Los **adaptadores** expresan *tecnología específica*  

📍 Diagrama visual en [página 2](https://myaidrive.com/preview/file/00000000b61871f4bfeb39966901cc97?pdfPage=2)

---

## Antipatrones comunes

🚫 Adaptadores que devuelven entidades (fuera de application)  
🚫 Puertos que filtran detalles técnicos (SQL/HTTP)  
🚫 Controladores que contienen lógica de negocio  
🚫 Repositorios que mutan DTOs o manejan estados ocultos  
🚫 No tener tests de contrato: cada refactor rompe algo diferente

📍 Imagen de advertencia en [página 3](https://myaidrive.com/preview/file/00000000b61871f4bfeb39966901cc97?pdfPage=3) :contentReference[oaicite:0]{index=0}

---

## IA como Copiloto (Prompts útiles)

### ✅ Generar tests de contrato

> “Dado este puerto `{OrderRepository}`, genera una suite de tests de contrato en **Vitest** que valide:  
> - guardar/leer  
> - idempotencia de `save()`  
> - atomicidad”

⚙️ Output esperable: suite parametrizable por fábrica

---

### ✅ Diseñar mapeadores puros

> “A partir del snapshot del agregado `Order`, escribe funciones puras:  
> - `toRows(snapshot)`  
> - `fromRows(rows)`  
> con validación y casos de borde. Sin librerías externas.”

---

### ✅ Revisar acoplamientos

> “Revisa estos adaptadores y detecta acoplamientos accidentales con dominio o aplicación.  
> Sugiere límites y nombres coherentes.”

---

### ✅ Outbox + Dispatcher

> “Genera SQL para una tabla `outbox`  
> y un job en **Node.js** que:  
> - lea eventos  
> - publique (simulado)  
> - marque `published_at`  
> - con reintentos exponenciales”

---

### ✅ Controlador HTTP

> “Dado el caso de uso `{AddItemToOrder}`, crea un **controlador Fastify** que:  
> - valide input con **zod**  
> - mapee errores tipados a HTTP `400 / 404 / 409 / 503`”

📍 Prompts extra en [página 4](https://myaidrive.com/preview/file/00000000b61871f4bfeb39966901cc97?pdfPage=4)

---
# Módulo 2: Arquitectura de Software

## Composición e Inversión de Dependencias  
**Aplicando Clean Architecture con TypeScript**

---

## Diagrama de responsabilidades

- **`/composition`** crea adaptadores  
- Los inyecta en **`/application/use-cases`**  
- Se exponen a través de **`/infra/http`**  

📍 Ver flujo visual en [página 2](https://myaidrive.com/preview/file/00000000af9871f4b2891adb6380f42e?pdfPage=2) :contentReference[oaicite:0]{index=0}

---

## Principios de Dependency Injection (DI)

- **Inversión de Dependencias**  
- **Composition Root** central  
- **Lifetimes** controlados (singleton, scoped, transient)  
- Sin "magia" ni autowiring oculto:contentReference[oaicite:1]{index=1}

---

## Enrutado por entorno (dev / test / prod)

| Entorno | Configuración destacada |
|--------|--------------------------|
| **DEV** | `USE_INMEMORY=true`, logs detallados, sin outbox |
| **TEST** | `USE_INMEMORY=true` o DB efímera, limpieza entre tests |
| **PROD** | DB real, outbox + dispatcher, timeouts estrictos |

📍 Tabla y ejemplo en [página 4](https://myaidrive.com/preview/file/00000000af9871f4b2891adb6380f42e?pdfPage=4) :contentReference[oaicite:2]{index=2}

---

## Checklist de calidad de la composición

✅ Composición root único y visible  
✅ Ningún import de `infra` dentro de `application/domain`  
✅ Configuración **tipada** (fail-fast)  
✅ Lifetimes bien definidos (y justificados)  
✅ Tests de contrato + smoke tests en CI:contentReference[oaicite:3]{index=3}

📍 Ver checklist completo en [página 5](https://myaidrive.com/preview/file/00000000af9871f4b2891adb6380f42e?pdfPage=5)

---

## IA como Copiloto (prompts útiles)

### ✅ Auditar el wiring

> “Revisa este `container.ts` y señala dependencias cíclicas o singletons innecesarios.  
> Propón lifetimes adecuados (singleton/scoped/transient).”

### ✅ Composición por entorno

> “Dado este Config y estos adaptadores, genera una función `buildAdapters(config)`  
> que elija implementaciones por entorno y devuelva tipos concretos.”

### ✅ Scope por petición

> “Crea un helper `makeRequestScope(container)` que inyecte `requestId`,  
> logger con contexto enlazado y ejemplos de uso en un controlador Fastify.”

### ✅ Comprobación de límites

> “Analiza estos imports y marca violaciones de la regla de dependencias entre domain,  
> application, infrastructure, composition. Sugiere cambios y reglas ESLint.”

📍 Ver prompts en [página 6](https://myaidrive.com/preview/file/00000000af9871f4b2891adb6380f42e?pdfPage=6) :contentReference[oaicite:4]{index=4}

---
# Módulo 2: Arquitectura de Software

## Testing en Clean Architecture  
**Aplicando Clean Architecture con TypeScript**

---

## Pirámide de Tests

- **Dominio**: 50-60%  
- **Casos de Uso**: 25-30%  
- **Contratos Adaptadores**: 10-15%  
- **E2E / Smoke**: mínimo viable

📍 Ver pirámide en [página 2](https://myaidrive.com/preview/file/00000000845871f49dba807944ca7baf?pdfPage=2) :contentReference[oaicite:0]{index=0}

---

## Organización de carpetas de tests

```bash
/tests
  /domain         # unit tests puros
  /application    # acceptance (use cases con dobles)
  /contracts      # suites compartidas (repos, event bus...)
  /e2e            # smoke/e2e con servidor real
  doubles.ts      # fakes/stubs/spies reutilizables
📍 Estructura en página 3

Nivel 1: Dominio
✅ Evita mocks
✅ Testea errores específicos (CurrencyMismatch)
✅ Usa Builders para reducir ruido

// tests/domain/price.property.spec.ts
it("sumar es conmutativo", () => {
  const a = Price.create(12.34, "EUR")
  const b = Price.create(5.66, "EUR")
  expect(a.add(b).amount).toBeCloseTo(b.add(a).amount, 2)
})
📍 Código en página 4

Builders para tests
// tests/builders.ts
export const anyEUR = (n = 10) => Price.create(n, "EUR")
export const qty = (n = 1) => Quantity.create(n)
export const sku = (v = "ABC-1") => SKU.create(v)
📍 Fragmento completo en página 5

Nivel 2: Casos de Uso (Aceptación)
Entrada/Salida como DTOs planos

Errores tipados: validation, not_found, conflict

No importar librerías como express, pg, etc.

it("publica eventos tras guardar", async () => {
  const repo = new InMemoryOrderRepository()
  const pricing = new StaticPricingService({ ... })
  const uc = new AddItemToOrder(repo, pricing, new CapturingEventBus())
  const res = await uc.execute({ ... })
  expect(events.published.length).toBeGreaterThan(0)
})
📍 Código en página 7

Nivel 3: Contratos de Adaptadores
Estrategia por tipo:

Repositorio: guardar/leer, idempotencia

EventBus/Outbox: eventos sin published_at

HTTP Client: timeouts, VO mapping

Consejos:

Limpiar estado (TRUNCATE)

API uniforme para test suite

📍 Indicaciones en página 8

Nivel 4: E2E / Smoke
describe("E2E Smoke", async () => {
  const app = await buildServer(buildContainer())
  const r1 = await app.inject({ method: "POST", url: "/orders", ... })
  expect(r1.statusCode).toBe(200)
})
📍 Código en página 9

CI con GitHub Actions
services:
  postgres:
    image: postgres:16
    ports: ['5432:5432']
    env:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: orders
steps:
  - uses: actions/setup-node@v4
    with: { node-version: "20.x" }
  - run: npm ci
  - run: npm run db:migrate
  - run: npm test -- --run
📍 Ejemplo de pipeline en página 10

IA como Copiloto (Prompts útiles)
✅ Diseño de suites por nivel
“Lista los casos de prueba esenciales por nivel para minimizar duplicidad.”

✅ Dobles reutilizables
“Crea fakes/stubs/spies para {OrderRepository, PricingService, EventBus, Clock}.”

✅ Contratos robustos
“Extiende OrderRepository para update + concurrencia + limpieza entre pruebas.”

✅ Test E2E
“Crea test E2E con Fastify inject y validaciones 400/404/409.”

✅ Cobertura
“Analiza cobertura y sugiere pruebas en dominio y aplicación para ramas críticas.”

# Módulo 2: Arquitectura de Software

## Conclusiones  
**Aplicando Clean Architecture con TypeScript**

---

## 10 Principios “no negociables”

1. **Regla de dependencias**: flechas hacia el dominio, que está en el centro.  
2. **Dominio puro**: Value Objects y Entidades con invariantes, sin IO ni frameworks.  
3. **Casos de uso orquestan**: DTOs de entrada/salida, errores tipados, publican eventos.  
4. **Puertos** expresan necesidades; **adaptadores** expresan tecnología.  
5. **Composición explícita** al borde; sin “magia” ni service locator.  
6. **DTOs fuera**; Entidades y VOs dentro.  
7. **Errores como tipos** en application; excepciones solo para invariantes en dominio.  
8. **Tests por niveles**: dominio → aceptación → contratos → E2E/smoke.  
9. **Observabilidad como puerto**: logger y eventos fiables (outbox).  
10. **IA como copiloto**, no como piloto: validación final con criterio arquitectónico.  
📍 [Página 2](https://myaidrive.com/preview/file/00000000bb34720a97e1850f7be9e87e?pdfPage=2) :contentReference[oaicite:0]{index=0}

---

## Llevar a producción

- ✅ Configuración tipada con **Zod**  
- ✅ `.env` por entorno  
- ✅ Migraciones ensayadas + backup/restore  
- ✅ Observabilidad: logs estructurados + métricas (latencia, errores)  
- ✅ Seguridad: input validation, CORS, secrets fuera del repo, rate limiting  
- ✅ Robustez IO: timeouts, reintentos con jitter, circuit breakers  
- ✅ CI: migraciones + tests  
- ✅ CD: blue/green o canary + rollback scripts  
📍 [Página 3](https://myaidrive.com/preview/file/00000000bb34720a97e1850f7be9e87e?pdfPage=3) :contentReference[oaicite:1]{index=1}

---

## Monolito vs Microservicios

- Comienza con un **Monolito Modular**  
- Evalúa cuándo “duele” la modularidad  
- Microservicios deben surgir por necesidad, no por moda  
📍 [Página 4](https://myaidrive.com/preview/file/00000000bb34720a97e1850f7be9e87e?pdfPage=4)

---

## IA como Copiloto – 5 Reglas de Oro

1. Pide artefactos pequeños (VOs, puertos, tests), **no todo el repo**  
2. Siempre añade **contexto de dominio** antes de pedir código  
3. Usa IA para **revisar límites y dependencias**  
4. Genera tests y refactors guiados  
5. **Nunca aceptes imports cruzando capas** sin justificación → haz que la IA explique  
📍 [Página 5](https://myaidrive.com/preview/file/00000000bb34720a97e1850f7be9e87e?pdfPage=5)

---

## Errores Típicos

🚫 Imports de `infra` en `application/domain`  
🚫 Casos de uso que devuelven entidades  
🚫 Adaptadores que mutan DTOs o tienen lógica de negocio  
🚫 Usar solo E2E en lugar de testear dominio y contratos  
🚫 Acoplar logs al dominio  
📍 [Página 6](https://myaidrive.com/preview/file/00000000bb34720a97e1850f7be9e87e?pdfPage=6)

---
# Módulo 2: Arquitectura de Software

## Introducción a la Asignatura: Objetivos  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## Objetivos del módulo

- Comprender qué es una arquitectura distribuida  
- Conocer diferentes formas de comunicación entre servicios  
- Diseñar e implementar Event-Driven Architectures  
- Evolucionar de monolito modular a sistema distribuido  
- Utilizar IA para modelar arquitecturas complejas  
📍 [Página 2](https://myaidrive.com/preview/file/0000000066c471f4824213cd75fbf181?pdfPage=2) :contentReference[oaicite:0]{index=0}

---
# Módulo 2: Arquitectura de Software

## Mitos y Verdades sobre los Microservicios  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## Mitos comunes sobre microservicios

- “Escalabilidad automática”  
- “Más fácil de mantener”  
- “Cada uno con su propia base de datos sí o sí”  
- “Es la única forma moderna de escalar”

---

## Verdades sobre los microservicios

- ✅ Autonomía de equipos  
- ✅ Despliegue independiente  
- ✅ Resiliencia  
- ✅ Reflejan bien el dominio del negocio

📍 [Página 2](https://myaidrive.com/preview/file/0000000034b471f49f64e93ed0c97284?pdfPage=2) :contentReference[oaicite:0]{index=0}

---
# Módulo 2: Arquitectura de Software

## Monolitos Modulares  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## ¿Qué es un Monolito Modular?

Una arquitectura en la que todos los módulos conviven en el mismo proceso,  
pero con una **organización clara por dominios**, separación de responsabilidades y dependencias bien gestionadas:contentReference[oaicite:0]{index=0}.

---

## Ventajas

- 🚀 Desarrollo rápido  
- ✅ Testing simple  
- 🧩 Un solo despliegue  
- 🛠️ Fácil de depurar  
- 🔁 Evolución natural hacia microservicios:contentReference[oaicite:1]{index=1}

---

## Buenas prácticas

- 🔹 Separación por dominio  
- 🔹 Interfaces bien definidas  
- 🔹 Inversión de dependencias  
- 🔹 Mínimas dependencias cruzadas:contentReference[oaicite:2]{index=2}

---

## Qué evitar

🚫 Código “Spaghetti”  
🚫 Acoplamientos innecesarios  
🚫 Microservicios dentro del mismo proceso (anti-patrón):contentReference[oaicite:3]{index=3}

---
# Módulo 2: Arquitectura de Software

## Monolitos Modulares  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## ¿Qué es un Monolito Modular?

Una arquitectura en la que todos los módulos conviven en el mismo proceso,  
pero con una **organización clara por dominios**, separación de responsabilidades y dependencias bien gestionadas:contentReference[oaicite:0]{index=0}.

---

## Ventajas

- 🚀 Desarrollo rápido  
- ✅ Testing simple  
- 🧩 Un solo despliegue  
- 🛠️ Fácil de depurar  
- 🔁 Evolución natural hacia microservicios:contentReference[oaicite:1]{index=1}

---

## Buenas prácticas

- 🔹 Separación por dominio  
- 🔹 Interfaces bien definidas  
- 🔹 Inversión de dependencias  
- 🔹 Mínimas dependencias cruzadas:contentReference[oaicite:2]{index=2}

---

## Qué evitar

🚫 Código “Spaghetti”  
🚫 Acoplamientos innecesarios  
🚫 Microservicios dentro del mismo proceso (anti-patrón):contentReference[oaicite:3]{index=3}

---
# Módulo 2: Arquitectura de Software

## Comunicación Asíncrona y Basada en Eventos  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## Características

| Elemento   | Descripción                                      |
|------------|--------------------------------------------------|
| **Emisor** | Publica un evento sin esperar respuesta          |
| **Receptor** | Se suscribe al evento y reacciona              |
| **Ventajas** | Bajo acoplamiento, resiliencia, escalabilidad  |
| **Desventajas** | Complejidad, observabilidad, consistencia eventual |
| **Tecnologías comunes** | RabbitMQ, Kafka, NATS, Redis Streams |

📍 [Página 2](https://myaidrive.com/preview/file/00000000af3471f486cfd8e3128e05f8?pdfPage=2) :contentReference[oaicite:0]{index=0}

---
# Módulo 2: Arquitectura de Software

## Introducción a Event-Driven Architecture  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## ¿Qué es Event-Driven Architecture?

- 🔹 Los servicios **publican y consumen eventos**  
- 🔹 Comunicación **indirecta** (no hay llamadas directas entre servicios)  
- 🔹 Arquitectura **escalable, resiliente y extensible**  
- 🔹 Ideal para **sistemas distribuidos modernos**  
- 🔹 Requiere **contratos claros** y buen **monitoreo**

🧭 El *diagrama en la página 2* muestra cómo un evento como `order.created` es emitido por el servicio `Order` y consumido por otros como `Payment` e `Inventory`. También ilustra cómo `Payment` puede emitir un `payment.failed`, que otros servicios pueden manejar:contentReference[oaicite:0]{index=0}

---
# Módulo 2: Arquitectura de Software

## Diseño de Flujos de Eventos  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## Pasos clave para diseñar flujos de eventos

🎯 **Identifica eventos del negocio**  
Ej: `order.created`, `payment.failed`

🧱 **Lista servicios productores y consumidores**  
- Productor: `OrderService`  
- Consumidores: `InventoryService`, `NotificationService`  

🔁 **Define el flujo reactivo**  
Cada servicio reacciona a eventos según su rol

📄 **Especifica el contrato de cada evento**  
- Estructura del payload  
- Semántica clara  
- Compatibilidad futura  

🤖 **Usa IA para ayudarte a modelar**  
Pide a la IA:  
> “Genera eventos relevantes para este dominio y modela el flujo entre servicios usando un bus de eventos. Sugiere errores y reintentos.”  

📊 *El diagrama en la página 2* muestra el flujo entre `OrderService`, `Event Bus`, `InventoryService` y `NotificationService`, destacando eventos como `order.created` y `payment.succeed`:contentReference[oaicite:0]{index=0}

---
# Módulo 2: Arquitectura de Software

## Implementación de Eventos en Node.js con TypeScript  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## Estrategias según el contexto

| Estrategia       | Uso recomendado                     | Tecnología sugerida    |
|------------------|-------------------------------------|------------------------|
| **EventEmitter** | Monolitos modulares                 | `events`               |
| **RabbitMQ**     | Microservicios distribuidos         | `amqplib`              |

---

## Buenas prácticas

- 🧾 **Contratos claros** → usar `interface`  
- ✅ **Validación** → con `Zod` o `Joi`  
- 🔄 **Separar Publisher y Consumer**  
- 🤖 **IA para generar boilerplate** (estructura base)  

📍 [Página 2](https://myaidrive.com/preview/file/00000000d5f871f49843646e1fa1620d?pdfPage=2) :contentReference[oaicite:0]{index=0}

---
# Módulo 2: Arquitectura de Software

## Práctica: De Monolito Modular a Sistema Distribuido  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## Migración práctica a sistema distribuido

### Pasos:

1. **Monolito modular**  
   Organización por dominios dentro de un único proceso.

2. **Eventos locales**  
   Uso de `EventEmitter` para desacoplar módulos internamente.

3. **Patrón Outbox**  
   Persistencia de eventos junto a los datos de negocio y publicación asíncrona.

4. **Separación de módulo en microservicio**  
   Extraer un módulo crítico como `OrderService` o `PaymentService`.

5. **Comunicación por eventos**  
   Usar una cola (como RabbitMQ o Kafka) para intercambiar mensajes.

6. **Validación con logs y trazabilidad**  
   Confirmar flujo correcto de eventos, detección de errores y análisis:contentReference[oaicite:0]{index=0}

---

🧭 *El diagrama en la página 2* muestra cómo el **Monolito Modular** se transforma conectando con microservicios (`OrderService`, `PaymentService`) a través de una **cola de eventos**, ilustrando el flujo distribuido.

---
# Módulo 2: Arquitectura de Software

## Uso de IA para Diseñar Arquitecturas Distribuidas  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## Cómo usar IA en el diseño arquitectónico

🧠 Pasos sugeridos para el uso de IA como copiloto:

1. **Modelar eventos y flujos reactivos**  
   - Solicita a la IA generar una lista de eventos y definir quién los produce y quién los consume.

2. **Diseñar servicios y topologías**  
   - Pide a la IA agrupar responsabilidades por dominio y proponer separaciones técnicas.

3. **Generar contratos y esquemas**  
   - Solicita a la IA interfaces de eventos y ejemplos de payload JSON validados con Zod o similares.

4. **Validar decisiones arquitectónicas**  
   - Usa IA para hacer *code reviews arquitectónicos*, revisar límites de responsabilidad y dependencias.

5. **Documentar visualmente**  
   - Pide que te genere diagramas en **Mermaid** o **PlantUML** a partir del flujo diseñado:contentReference[oaicite:0]{index=0}

---
# Módulo 2: Arquitectura de Software

## Práctica: Modelado de Arquitectura Distribuida  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## Pasos para modelar una arquitectura distribuida

1. **Definir flujo de negocio**  
   - Identificar eventos clave del proceso

2. **Identificar servicios y eventos**  
   - Productores y consumidores

3. **Diseñar topología y contratos**  
   - ¿Qué servicios existen? ¿Qué eventos intercambian?

4. **Dibujar flujo reactivo**  
   - Diagramar eventos y relaciones

5. **Usar IA para validar el diseño**  
   - Pedir revisión de dependencias, responsabilidades y límites:contentReference[oaicite:0]{index=0}

---
# Módulo 2: Arquitectura de Software

## Prompts para IA  
**Modelado de una arquitectura distribuida para sistema de reservas de vuelos**

---

### Prompt 1 — Modelado de dominios  
> Tengo que diseñar una arquitectura distribuida para un sistema de reservas de vuelos. ¿Qué módulos o bounded contexts debería considerar? Quiero que me ayudes a definirlos y priorizarlos.

---

### Prompt 2 — Diseño de eventos  
> Proponme los eventos clave del dominio. Usa formato verbo-pasado como `flight.scheduled` o `booking.confirmed`. Dame también el servicio que los emite y qué otros los consumen.

---

### Prompt 3 — Contratos de eventos  
> Genera la estructura JSON para el evento `booking.confirmed`, incluyendo los campos recomendados y buenas prácticas para trazabilidad.

---

### Prompt 4 — Topología de servicios  
> Basado en los eventos anteriores, propón una topología distribuida de servicios. Quiero saber qué servicios existen, cómo se comunican (sincronía vs eventos) y qué base de datos usa cada uno.

---

### Prompt 5 — Validación de decisiones arquitectónicas  
> ¿Crees que el servicio de pagos debe emitir su propio evento al confirmarse el pago o debe simplemente responder al frontend? Evalúa ventajas y riesgos de ambas opciones.

---

### Prompt para diagrama Mermaid  
> Genera un diagrama en formato Mermaid.js para el siguiente flujo:  
> - OrderService crea una orden y emite `order.created`  
> - PaymentService escucha ese evento y responde con `payment.succeeded`  
> - InventoryService reacciona a `payment.succeeded` y descuenta stock  
>  
> **Resultado esperado:**  
> ```mermaid
> graph TD  
> OrderService -->|order.created| EventBus  
> EventBus --> PaymentService  
> PaymentService -->|payment.succeeded| EventBus  
> EventBus --> InventoryService  
> ```

📍 Fuente: [2.3.12-prompts.md_.pdf](https://myaidrive.com/preview/file/0000000053b471f48180a9b29e40bfe7) :contentReference[oaicite:0]{index=0}

---
# Módulo 2: Arquitectura de Software

## Práctica: Modelado de Arquitectura Distribuida  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## Pasos clave

1. **Definir flujo de negocio**  
   - Identificar el proceso principal y sus pasos

2. **Identificar servicios y eventos**  
   - ¿Qué servicios participan?  
   - ¿Qué eventos publican y consumen?

3. **Diseñar topología y contratos**  
   - Representar la estructura del sistema  
   - Especificar el formato de los eventos y las relaciones entre servicios

4. **Dibujar flujo reactivo**  
   - Visualizar cómo los servicios reaccionan ante los eventos

5. **Usar IA para validar el diseño**  
   - Evaluar límites de servicio, dependencias y redundancias con ayuda de IA:contentReference[oaicite:0]{index=0}

---
# Módulo 2: Arquitectura de Software

## Escenario práctico: Plataforma de Pedidos a Domicilio  
**Arquitecturas distribuidas y comunicación entre servicios**

---

## Paso 1 — Flujo de negocio

🧭 Plataforma tipo Glovo, Uber Eats o Rappi:

1. Usuario realiza un pedido desde la app  
2. El sistema valida datos y disponibilidad  
3. Se procesa el pago  
4. Se asigna un repartidor  
5. El restaurante recibe el pedido  
6. El pedido se entrega:contentReference[oaicite:0]{index=0}

---

## Paso 2 — IA para identificar servicios y eventos

💬 Prompt sugerido:  
> Estoy diseñando una arquitectura distribuida para una plataforma de pedidos de comida. ¿Qué módulos o servicios sugerirías? ¿Qué eventos de dominio deberían emitirse y por quién?

**Respuesta esperada**  
**Servicios:**  
- OrderService  
- PaymentService  
- DeliveryService  
- RestaurantService  
- NotificationService

**Eventos:**  
- order.placed  
- payment.succeeded  
- delivery.assigned  
- restaurant.notified  
- order.delivered:contentReference[oaicite:1]{index=1}

---

## Paso 3 — Definición de eventos clave

```json
// order.placed
{
  "orderId": "abc123",
  "userId": "user42",
  "items": [{ "id": "burger01", "qty": 2 }],
  "total": 18.5,
  "createdAt": "2025-09-10T12:00:00Z"
}

// payment.succeeded
{
  "orderId": "abc123",
  "paymentId": "pmt001",
  "method": "card",
  "paidAt": "2025-09-10T12:01:10Z"
}

// delivery.assigned
{
  "orderId": "abc123",
  "driverId": "drv88",
  "eta": "15 min"
}
Paso 4 — Diagrama del flujo de eventos (Mermaid.js)
graph TD
A[User] --> B[OrderService]
B -->|order.placed| EB(EventBus)
EB --> C[PaymentService]
C -->|payment.succeeded| EB
EB --> D[DeliveryService]
EB --> E[RestaurantService]
D -->|delivery.assigned| EB
EB --> F[NotificationService]
Paso 5 — Contratos y consumidores
Evento	Publica	Consume
order.placed	OrderService	PaymentService, RestaurantService
payment.succeeded	PaymentService	DeliveryService, NotificationService
delivery.assigned	DeliveryService	NotificationService
Paso 6 — IA como copiloto de decisión
💬 Prompt sugerido:

¿Crees que debería usar comunicación síncrona entre OrderService y PaymentService, o emitir un evento 'order.placed'? Evalúa pros y contras.

✅ Esto permite discutir trade-offs arquitectónicos con IA

Ejercicio final (alumno)
Repite este proceso con otro caso:

Plataforma de reservas de hoteles

Sistema de logística y paquetería

Plataforma de educación en línea con inscripciones y pagos

# Módulo 2: Arquitectura de Software

## Conclusiones y Próximos Pasos  
**Arquitecturas distribuidas y comunicación entre servicios**

---

### Puntos clave

- 🧭 Piensa en la **arquitectura como herramienta de impacto**  
- 🛠️ **Aplica lo aprendido** en proyectos reales  
- 🧠 **Refina tu pensamiento arquitectónico** con práctica continua  
- 🤖 Usa la **IA como copiloto**, no como muleta  
- 🎯 Aprende a **decidir cuándo, cómo y por qué distribuir** un sistema:contentReference[oaicite:0]{index=0}

---
