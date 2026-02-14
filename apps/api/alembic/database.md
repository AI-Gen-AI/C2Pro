# Diagrama de Base de Datos (C2Pro)

**Última Actualización:** 2026-01-13

Este documento contiene el diagrama de Entidad-Relación (ERD) para la base de datos de C2Pro. El diagrama se mantiene utilizando la sintaxis de [Mermaid.js](https://mermaid.js.org/).

## Diagrama ERD

```mermaid
erDiagram
    tenants {
        UUID id PK "Clave primaria del tenant"
        string name "Nombre de la organización"
        datetime created_at "Fecha de creación"
        datetime updated_at "Última actualización"
    }

    projects {
        UUID id PK "Clave primaria del proyecto"
        UUID tenant_id FK "Referencia al tenant propietario"
        string name "Nombre del proyecto"
        string description "Descripción del proyecto"
        datetime created_at "Fecha de creación"
        datetime updated_at "Última actualización"
    }

    documents {
        UUID id PK "Clave primaria del documento"
        UUID project_id FK "Referencia al proyecto al que pertenece"
        UUID tenant_id FK "Referencia al tenant (para RLS y queries)"
        string filename "Nombre original del archivo"
        string storage_path "Ruta en el servicio de almacenamiento (R2/MinIO)"
        int file_size_bytes "Tamaño del archivo en bytes"
        DocumentType document_type "Tipo de documento (CONTRACT, BUDGET, etc.)"
        DocumentStatus status "Estado en el pipeline de procesamiento"
        datetime created_at "Fecha de subida"
        datetime updated_at "Última actualización del estado"
    }

    tenants ||--o{ projects : "tiene"
    tenants ||--o{ documents : "posee"
    projects ||--o{ documents : "contiene"
```

## Relaciones Clave

- **`tenants` a `projects`**: Un tenant puede tener múltiples proyectos. La relación `tenants.id` -> `projects.tenant_id` es fundamental para el aislamiento de datos (Row Level Security).
- **`projects` a `documents`**: Un proyecto puede contener múltiples documentos. La relación `projects.id` -> `documents.project_id` organiza los documentos por proyecto.
- **`tenants` a `documents`**: Se mantiene una referencia directa `documents.tenant_id` para optimizar las políticas de RLS y las consultas, evitando un JOIN adicional a la tabla `projects` en cada acceso a un documento.

---
*Este diagrama se genera y actualiza como parte del flujo de trabajo de documentación automatizada.*