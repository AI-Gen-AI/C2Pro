# C2Pro - Lecciones Aprendidas
**Fecha de creación:** 2026-01-22
**Versión:** 1.0

## Propósito

Este documento registra las lecciones aprendidas durante el desarrollo de C2Pro para evitar repetir errores y mejorar el proceso de desarrollo continuo.

---

## LL-001: No Eliminar Elementos Críticos de UI Durante Refactorización

**Fecha:** 2026-01-22
**Severidad:** Alta
**Contexto:** CE-S2-011 - Frontend Type Safety & API Integration

### Problema

Durante la implementación de mejoras de type safety y sincronización de tipos entre frontend y backend, se eliminó accidentalmente el badge de alertas críticas en el componente `RecentProjectsCard.tsx`.

**Código eliminado:**
```tsx
{/* Alerts */}
{project.critical_alerts > 0 && (
  <Badge variant="destructive" className="animate-pulse-critical">
    {project.critical_alerts} Critical
  </Badge>
)}
```

### Impacto

- Pérdida de visualización crítica: Los usuarios no podían ver las alertas críticas de los proyectos
- Error de build: TypeScript detectó que `critical_alerts` podría ser `undefined`
- Trabajo duplicado: Tiempo invertido en identificar y restaurar el código eliminado

### Causa Raíz

Durante la refactorización para sincronizar tipos entre frontend/backend:
1. Se modificaron múltiples archivos simultáneamente
2. No se validó visualmente la UI antes del commit
3. No se ejecutó el build de TypeScript antes del commit
4. Faltó checklist de elementos UI críticos

### Solución Aplicada

1. Restaurar el badge de alertas críticas
2. Agregar validación de null safety: `project.critical_alerts && project.critical_alerts > 0`
3. Verificar el build de TypeScript: `npm run build`
4. Validar visualmente el dashboard en localhost

### Prevención Futura

**Checklist Pre-Commit para Cambios de UI:**
- [ ] Ejecutar `npm run build` para verificar errores de TypeScript
- [ ] Iniciar dev server y verificar visualmente los componentes modificados
- [ ] Revisar git diff para asegurar que no se eliminaron elementos críticos
- [ ] Documentar elementos UI críticos en comentarios del código
- [ ] Usar búsqueda global antes de eliminar código que parece duplicado

**Elementos UI Críticos Identificados:**
- `RecentProjectsCard.tsx`: Badge de alertas críticas
- `ActivityTimeline.tsx`: Iconos y timeline de actividades
- `StatsCards.tsx`: Métricas principales del dashboard

### Archivos Afectados

- `apps/web/components/dashboard/RecentProjectsCard.tsx`
- `apps/web/types/project.ts`

### Referencias

- Commit que introdujo el bug: (revisar git log)
- Commit con la corrección: (siguiente commit)
- Issue relacionado: CE-S2-011

---

## LL-002: Placeholder para Próximas Lecciones

Las lecciones aprendidas futuras se documentarán aquí siguiendo el mismo formato.

---

## Formato de Lección Aprendida

Cada lección debe incluir:

1. **Fecha:** Cuándo ocurrió
2. **Severidad:** Baja/Media/Alta/Crítica
3. **Contexto:** En qué tarea o sprint ocurrió
4. **Problema:** Descripción del error o problema
5. **Impacto:** Consecuencias del problema
6. **Causa Raíz:** Por qué ocurrió
7. **Solución Aplicada:** Cómo se resolvió
8. **Prevención Futura:** Checklist o procesos para evitarlo
9. **Archivos Afectados:** Código relacionado
10. **Referencias:** Commits, issues, documentos

---

## Estadísticas

- **Total de lecciones:** 1
- **Severidad Alta:** 1
- **Categorías:**
  - UI/Frontend: 1
  - Backend: 0
  - Infraestructura: 0
  - Proceso: 0

**Última actualización:** 2026-01-22
