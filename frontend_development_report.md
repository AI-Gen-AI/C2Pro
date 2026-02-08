# Informe de Desarrollo Frontend: C2Pro Web

## 1. Visión General del Proyecto Frontend

El proyecto frontend de C2Pro (`apps/web`) es una aplicación web moderna y robusta, construida principalmente con **Next.js y React**, utilizando **TypeScript** para una mayor seguridad y mantenibilidad del código. Adopta un enfoque de diseño modular y componentes, con un fuerte énfasis en la accesibilidad y la experiencia del usuario. La integración con el backend se realiza a través de una API RESTful, para la cual se genera automáticamente un cliente a partir de una especificación OpenAPI.

## 2. Tecnologías y Frameworks Clave

*   **Framework Principal:**
    *   **Next.js (v15.3.9):** Utilizado como framework de React, aprovechando sus capacidades de renderizado del lado del servidor (SSR) o generación estática (SSG) para optimizar el rendimiento y el SEO.
    *   **React (v19.1.5):** La biblioteca principal para la construcción de interfaces de usuario interactivas.
*   **Lenguaje:**
    *   **TypeScript (v5.3.3):** Garantiza la robustez del código, la detección temprana de errores y una mejor experiencia de desarrollo a través de la tipificación estática.
*   **Gestión de Estado y Datos:**
    *   **`@tanstack/react-query` (v5.87.1):** Para la gestión eficiente de la caché, sincronización y estado del servidor, facilitando la obtención y actualización de datos de la API.
    *   **`axios` (v1.7.7):** Cliente HTTP para realizar peticiones a la API backend.
*   **Generación de Cliente API:**
    *   **`openapi-typescript-codegen` (v0.29.0):** Herramienta esencial para generar automáticamente el cliente de la API (en `lib/api/generated`) a partir de la especificación OpenAPI del backend. Esto asegura la coherencia entre el frontend y el backend y reduce errores manuales.
*   **Estilado y Componentes UI:**
    *   **Tailwind CSS (v3.4.19):** Un framework CSS utility-first que permite construir diseños personalizados rápidamente y de forma eficiente.
    *   **Radix UI:** Una colección de librerías de componentes UI sin estilado, accesibles y de alta calidad, utilizada como base para construir componentes reutilizables (DropdownMenu, Dialog, Select, etc.).
    *   **`class-variance-authority`, `clsx`, `tailwind-merge`:** Utilidades para gestionar y combinar clases de Tailwind de forma condicional y eficiente.
    *   **`next-themes`:** Para la gestión de temas (por ejemplo, modo oscuro/claro).
*   **Iconografía:**
    *   **`lucide-react` (v0.562.0):** Biblioteca de iconos.
*   **Fuentes:**
    *   `@fontsource-variable/inter`, `@fontsource/jetbrains-mono`: Gestión de fuentes para tipografía consistente.
*   **Utilidades Adicionales:**
    *   **`date-fns` (v3.6.0):** Para manipulación de fechas.
    *   **`react-resizable-panels` (v2.1.9):** Para la creación de layouts con paneles redimensionables.
    *   **`recharts` (v2.15.4):** Biblioteca de gráficos para visualización de datos.
    *   **`pdfjs-dist` & `react-pdf` (v5.4.530 / v10.3.0):** Para la visualización y renderizado de documentos PDF.
    *   **`@dnd-kit/core`, `@dnd-kit/utilities` (v6.1.0 / v3.2.2):** Para funcionalidades de drag-and-drop.
    *   **`sonner` (v1.7.4):** Para notificaciones toast.
    *   **`cmdk` (v1.1.1):** Para la implementación de una paleta de comandos.
*   **Observabilidad:**
    *   **`@sentry/react` (v10.38.0):** Integración para monitoreo de errores y rendimiento.

## 3. Arquitectura y Capas

La aplicación sigue una arquitectura modular, típica de proyectos Next.js y React, con una clara separación de preocupaciones:

*   **Capa de Presentación (`app`, `components`):**
    *   **`app/`:** Contiene las rutas y páginas de Next.js, donde se orquestan los componentes y se define la estructura de la aplicación.
    *   **`components/`:** Almacena todos los componentes reutilizables de la UI, desde átomos básicos (botones, inputs) hasta moléculas y organismos complejos.
*   **Capa de Lógica de Aplicación (`hooks`, `contexts`, `lib/api/generated`, `types`):**
    *   **`hooks/`:** Custom hooks de React que encapsulan lógica reutilizable, como manejo de estado local, efectos secundarios o interacciones con la API.
    *   **`contexts/`:** Contextos de React para la gestión del estado global y la inyección de dependencias a lo largo del árbol de componentes.
    *   **`lib/api/generated/`:** El cliente de la API generado automáticamente, que abstrae las llamadas HTTP y proporciona interfaces tipadas para interactuar con el backend.
    *   **`types/`:** Definiciones de tipos de TypeScript para entidades de dominio, DTOs y otras estructuras de datos, manteniendo la coherencia en toda la aplicación.
*   **Capa de Acceso a Datos (implícita en `lib/api/generated` y `@tanstack/react-query`):**
    *   Aunque no hay una carpeta `data-access` explícita, la combinación de `openapi-typescript-codegen` y `@tanstack/react-query` actúa como esta capa, manejando la comunicación con la API, la serialización/deserialización y el caching de datos.

## 4. Estilado y Componentes UI

El estilado se basa en **Tailwind CSS**, lo que permite un desarrollo ágil y consistente. Se utiliza **Radix UI** para proporcionar componentes base accesibles y funcionales, que luego son estilados con Tailwind. Esto permite una gran flexibilidad y customización sin sacrificar la accesibilidad. La configuración de `tailwind.config.ts` y `postcss.config.js` es estándar para un proyecto Next.js + Tailwind.

## 5. Gestión de Estado

La gestión del estado se aborda en varios niveles:

*   **Estado del servidor:** Principalmente gestionado por **`@tanstack/react-query`**, que se encarga de la obtención, caché, invalidación y sincronización de los datos provenientes de la API.
*   **Estado global de la aplicación:** Se utiliza el **Context API de React** (en la carpeta `contexts/`) para compartir estados y funciones entre componentes distantes.
*   **Estado local de componentes:** Gestionado mediante los hooks `useState` y `useReducer` de React, o encapsulado en custom hooks (`hooks/`).

## 6. Estrategia de Testing

El proyecto tiene una sólida estrategia de testing, evidenciada por el uso de:

*   **Vitest (v3.2.4):** Como framework de pruebas principal, configurado para entornos de React.
*   **`@testing-library/react`:** Para pruebas unitarias y de integración de componentes de React, enfocándose en cómo el usuario interactúa con la UI.
*   **`@testing-library/jest-dom`:** Para aserciones de DOM más amigables.
*   **`@vitest/coverage-v8`:** Para generar informes de cobertura de código.
*   Scripts dedicados (`test`, `test:watch`, `test:coverage`) confirman la importancia del testing en el ciclo de desarrollo.

## 7. Flujo de Trabajo y Herramientas de Desarrollo

*   **Desarrollo Local:** `next dev` para un entorno de desarrollo rápido con hot-reloading.
*   **Build:** `next build` para la generación de la aplicación optimizada para producción.
*   **Linting:** `eslint` para mantener un código limpio y consistente.
*   **Generación de Cliente API:** El script `generate-client` automatiza la creación del cliente de la API, un paso crítico para la integración continua.
*   **Monitoreo:** `Sentry` para el seguimiento de errores y rendimiento en producción.

## 8. Estado Actual de Desarrollo

El frontend está configurado como una aplicación Next.js bien estructurada y tipada con TypeScript. La fuerte dependencia de `openapi-typescript-codegen` indica una integración backend robusta y definida por contratos. La presencia de diversas librerías de UI (Radix UI, Tailwind CSS) y utilidades (dnd-kit, recharts, react-pdf) sugiere que la aplicación ya soporta o está diseñada para soportar una rica interactividad y visualización de datos. La estrategia de testing es madura, lo que contribuye a la estabilidad y calidad del código. El proyecto parece estar en una fase avanzada de desarrollo, con una base técnica sólida para futuras expansiones.

Este informe proporciona una instantánea del estado actual del desarrollo frontend de C2Pro, destacando las herramientas, la arquitectura y las prácticas que sustentan el proyecto.
