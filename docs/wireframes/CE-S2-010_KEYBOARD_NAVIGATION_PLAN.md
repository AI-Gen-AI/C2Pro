# CE-S2-010: Keyboard Navigation (← →) - Implementation Plan
**Navegación con Teclado entre Highlights**

**Fecha:** 2026-01-17
**Prioridad:** MEDIA
**Estimación:** 3 horas
**Estado:** 📋 PLANNING

---

## 🎯 Objetivo

Implementar navegación con flechas del teclado (← →) para navegar entre **todos los highlights** del documento actual en el Evidence Viewer, permitiendo a los usuarios moverse rápidamente entre entidades extraídas sin necesidad de hacer click o usar búsqueda.

---

## 📋 Requerimientos

### Funcionales

| # | Requerimiento | Descripción |
|---|---------------|-------------|
| 1 | Navegación con → | Presionar flecha derecha avanza al siguiente highlight |
| 2 | Navegación con ← | Presionar flecha izquierda retrocede al highlight anterior |
| 3 | Orden de navegación | Los highlights se navegan en orden de página ascendente |
| 4 | Navegación circular | Al llegar al último, → vuelve al primero (y viceversa) |
| 5 | Auto-scroll PDF | Al navegar, el PDF debe moverse a la página correcta |
| 6 | Auto-scroll Entity Card | El panel derecho debe scrollear a la entidad correspondiente |
| 7 | Indicador de posición | Mostrar "Highlight X/Y" para orientar al usuario |
| 8 | Estado activo visual | El highlight actual debe tener animación/border especial |
| 9 | Independiente de búsqueda | Funciona incluso cuando la búsqueda NO está activa |
| 10 | Compatible con búsqueda | Si la búsqueda está activa, las flechas navegan solo matches |

### No Funcionales

| # | Requerimiento | Target | Descripción |
|---|---------------|--------|-------------|
| 1 | Performance | < 100ms | Tiempo de respuesta al presionar flecha |
| 2 | Accessibility | WCAG AA | ARIA announcements para screen readers |
| 3 | Browser support | Modern browsers | Chrome, Firefox, Safari, Edge (últimas 2 versiones) |
| 4 | Code maintainability | Baja complejidad | Cyclomatic complexity < 10 |
| 5 | No regressions | 100% backward compatible | No debe romper funcionalidad existente |

---

## 🏗️ Arquitectura

### Estado Actual (Simplified)

```
EvidenceViewer.tsx
├─ useState: currentDocumentId
├─ useState: activeHighlightId
├─ useState: isSearchVisible
├─ useHighlightSearch: {
│    searchQuery,
│    matches,           ← Solo highlights que matchean búsqueda
│    currentIndex,
│    currentMatch,
│    goToNext,          ← Navega solo entre matches
│    goToPrevious
│  }
├─ useEffect: keyboard shortcuts (Ctrl+F, Enter, Esc)
└─ highlights (array de todos los highlights del documento)
```

### Estado Propuesto (Con Arrow Navigation)

```
EvidenceViewer.tsx
├─ useState: currentDocumentId
├─ useState: activeHighlightId
├─ useState: isSearchVisible
├─ useState: currentHighlightIndex   ← NUEVO: índice del highlight actual
├─ useHighlightSearch: { ... }
├─ useEffect: keyboard shortcuts (Ctrl+F, Enter, Esc) ← MODIFICAR
│    └─ Agregar handlers para ArrowLeft, ArrowRight
└─ useEffect: auto-navigate to current highlight ← NUEVO
     └─ Similar al efecto de currentMatch, pero para currentHighlightIndex
```

**Diferencia clave:**
- `currentMatch` (de useHighlightSearch): Highlight activo cuando **HAY búsqueda**
- `currentHighlightIndex` (nuevo estado): Índice del highlight activo cuando **NO HAY búsqueda**

---

## 📦 Componentes y Archivos

### Archivos a Modificar

| Archivo | Líneas Estimadas | Cambios |
|---------|------------------|---------|
| `vision-matched-repo/src/pages/EvidenceViewer.tsx` | +60 | 1. Agregar estado `currentHighlightIndex`<br>2. Modificar `handleKeyDown` para agregar flechas<br>3. Agregar useEffect para auto-navegación<br>4. Agregar indicador de posición en UI |

**NO se crean archivos nuevos** - Todo se implementa en EvidenceViewer existente.

---

## 🔨 Implementación Detallada

### Fase 1: Agregar Estado para Navegación (15 min)

```typescript
// En EvidenceViewer.tsx, después de activeHighlightId

// State for keyboard navigation (arrow keys)
const [currentHighlightIndex, setCurrentHighlightIndex] = useState<number>(0);

// Compute sorted highlights (by page) for navigation
const sortedHighlights = useMemo(() => {
  return [...highlights].sort((a, b) => a.page - b.page);
}, [highlights]);

// Get current highlight based on index
const currentNavigationHighlight = sortedHighlights[currentHighlightIndex] || null;
```

**Por qué:**
- `currentHighlightIndex`: Índice del highlight actual (0-based)
- `sortedHighlights`: Array ordenado por página para navegación lógica
- `currentNavigationHighlight`: El highlight activo al navegar con flechas

---

### Fase 2: Modificar handleKeyDown (30 min)

```typescript
// En el useEffect de keyboard shortcuts, modificar handleKeyDown

const handleKeyDown = (e: KeyboardEvent) => {
  const isCtrlOrCmd = e.ctrlKey || e.metaKey;

  // Existing shortcuts...
  // Ctrl+F, Esc, Enter (búsqueda)
  // ...

  // NEW: Arrow navigation
  // Solo funciona si:
  // 1. NO hay un input/textarea enfocado
  // 2. NO hay un modal abierto
  const isInputFocused =
    document.activeElement?.tagName === 'INPUT' ||
    document.activeElement?.tagName === 'TEXTAREA';

  if (isInputFocused) return; // No interferir con inputs

  // Arrow Right: Next highlight
  if (e.key === 'ArrowRight') {
    e.preventDefault();

    // Si hay búsqueda activa, usar goToNext (ya existente)
    if (isSearchVisible && totalMatches > 0) {
      goToNext();
    } else {
      // Si NO hay búsqueda, navegar todos los highlights
      if (sortedHighlights.length > 0) {
        setCurrentHighlightIndex((prev) =>
          (prev + 1) % sortedHighlights.length  // Circular
        );
      }
    }
  }

  // Arrow Left: Previous highlight
  if (e.key === 'ArrowLeft') {
    e.preventDefault();

    if (isSearchVisible && totalMatches > 0) {
      goToPrevious();
    } else {
      if (sortedHighlights.length > 0) {
        setCurrentHighlightIndex((prev) =>
          (prev - 1 + sortedHighlights.length) % sortedHighlights.length
        );
      }
    }
  }
};
```

**Lógica de Prioridad:**
1. Si la búsqueda está activa → flechas navegan MATCHES (comportamiento existente)
2. Si NO hay búsqueda → flechas navegan TODOS los highlights

---

### Fase 3: Auto-navegación al Highlight Actual (30 min)

```typescript
// Nuevo useEffect: Navigate when currentNavigationHighlight changes
useEffect(() => {
  // Solo ejecutar si NO hay búsqueda activa
  // (cuando hay búsqueda, el efecto de currentMatch se encarga)
  if (!isSearchVisible && currentNavigationHighlight) {
    const entityId = currentNavigationHighlight.entityId;
    const entity = currentEntities.find((e) => e.id === entityId);

    if (entity) {
      // Navigate to the page
      updateDocumentState({ currentPage: entity.page });

      // Set as active highlight
      setActiveHighlightId(currentNavigationHighlight.id);

      // Scroll to entity card in data panel
      const entityRef = entityRefs.current[entityId];
      if (entityRef) {
        entityRef.scrollIntoView({
          behavior: 'smooth',
          block: 'center'
        });

        // Add pulse animation
        entityRef.classList.add('animate-pulse-once');
        setTimeout(() => {
          entityRef.classList.remove('animate-pulse-once');
        }, 600);
      }
    }
  }
}, [currentNavigationHighlight, isSearchVisible, currentEntities]);
```

**Coordinación con Búsqueda:**
- Si `isSearchVisible = true` → El efecto de `currentMatch` maneja la navegación
- Si `isSearchVisible = false` → Este nuevo efecto maneja la navegación con flechas

---

### Fase 4: Indicador de Posición (UI) (45 min)

```typescript
// En el JSX, agregar un indicador de navegación

// Compute position info
const navigationInfo = useMemo(() => {
  if (isSearchVisible && totalMatches > 0) {
    // Mostrar contador de búsqueda (ya existe en HighlightSearchBar)
    return null; // SearchBar ya muestra "3/12"
  } else if (sortedHighlights.length > 0) {
    // Mostrar contador de navegación general
    return {
      current: currentHighlightIndex + 1,
      total: sortedHighlights.length,
    };
  }
  return null;
}, [isSearchVisible, totalMatches, currentHighlightIndex, sortedHighlights.length]);

// En el render, justo debajo del PDFViewer
{navigationInfo && !isSearchVisible && (
  <div className="absolute bottom-4 right-4 z-10">
    <Badge variant="secondary" className="shadow-lg">
      Highlight {navigationInfo.current}/{navigationInfo.total}
      <span className="ml-2 text-xs text-muted-foreground">
        Use ← → to navigate
      </span>
    </Badge>
  </div>
)}
```

**Ubicación:** Esquina inferior derecha del panel del PDF (overlay)

**Visibilidad:**
- ✅ Se muestra cuando NO hay búsqueda activa
- ❌ Se oculta cuando HighlightSearchBar está visible (para no duplicar info)

---

### Fase 5: Reset al Cambiar Documento (10 min)

```typescript
// Modificar handleDocumentChange para resetear índice

const handleDocumentChange = (newDocumentId: string) => {
  setActiveHighlightId(null);
  setCurrentHighlightIndex(0);  // ← AGREGAR: Reset a primer highlight
  setCurrentDocumentId(newDocumentId);
};
```

**Por qué:** Al cambiar de documento, resetear al primer highlight.

---

### Fase 6: Accessibility (30 min)

```typescript
// Agregar screen reader announcements

// En el useEffect de currentNavigationHighlight, agregar:

// Announce to screen readers
const announceText = `Navigated to highlight ${currentHighlightIndex + 1} of ${sortedHighlights.length}. ${entity.type}: ${entity.text.substring(0, 100)}`;
const announcement = document.createElement('div');
announcement.setAttribute('role', 'status');
announcement.setAttribute('aria-live', 'polite');
announcement.setAttribute('aria-atomic', 'true');
announcement.className = 'sr-only';
announcement.textContent = announceText;
document.body.appendChild(announcement);
setTimeout(() => document.body.removeChild(announcement), 1000);
```

**ARIA Attributes:**
- `role="status"`: Indica que es un mensaje de estado
- `aria-live="polite"`: Anuncia cuando el usuario está idle
- `aria-atomic="true"`: Lee el mensaje completo

---

## 🧪 Testing

### Test Cases

#### TC-001: Navegación Básica con Flechas ⭐ CRITICAL
**Prioridad:** HIGH
**Pasos:**
1. Abrir Evidence Viewer con un documento que tenga 5+ highlights
2. Presionar flecha derecha (→) varias veces
3. **Verificar:**
   - PDF navega a la página correcta
   - Entity Card hace scroll al highlight correspondiente
   - Indicador muestra "Highlight 1/5", "Highlight 2/5", etc.
   - Highlight activo tiene animación pulse
4. Presionar flecha izquierda (←)
5. **Verificar:** Navega al highlight anterior

**Resultado esperado:** ✅ Navegación fluida en ambas direcciones

---

#### TC-002: Navegación Circular
**Prioridad:** HIGH
**Pasos:**
1. Abrir documento con 5 highlights
2. Presionar → hasta llegar al último (5/5)
3. Presionar → una vez más
4. **Verificar:** Vuelve al primero (1/5)
5. Presionar ← desde el primero
6. **Verificar:** Va al último (5/5)

**Resultado esperado:** ✅ Loop circular funciona correctamente

---

#### TC-003: Compatibilidad con Búsqueda
**Prioridad:** CRITICAL
**Pasos:**
1. Abrir documento con 10 highlights
2. Activar búsqueda (Ctrl+F) y buscar algo que genere 3 matches
3. **Verificar:** SearchBar muestra "1/3"
4. Presionar → (flecha derecha)
5. **Verificar:** Navega solo entre los 3 matches (NO todos los highlights)
6. **Verificar:** SearchBar actualiza a "2/3"
7. Cerrar búsqueda (Esc)
8. Presionar →
9. **Verificar:** Ahora navega todos los highlights, indicador muestra "Highlight X/10"

**Resultado esperado:** ✅ Las flechas respetan el contexto (búsqueda vs navegación general)

---

#### TC-004: No Interferir con Inputs
**Prioridad:** MEDIUM
**Pasos:**
1. Abrir Evidence Viewer
2. Hacer click en el campo de búsqueda (Input)
3. Presionar → y ←
4. **Verificar:** El cursor se mueve dentro del input, NO se navegan highlights

**Resultado esperado:** ✅ Las flechas solo navegan cuando NO hay input enfocado

---

#### TC-005: Cambio de Documento
**Prioridad:** MEDIUM
**Pasos:**
1. Navegar al highlight 3/5 con flechas
2. Cambiar a otro documento usando el dropdown
3. **Verificar:** El indicador se resetea a "Highlight 1/X" (primer highlight del nuevo doc)

**Resultado esperado:** ✅ Reset correcto al cambiar documento

---

#### TC-006: Accessibility (Screen Reader)
**Prioridad:** MEDIUM
**Pasos:**
1. Activar screen reader (NVDA/JAWS/VoiceOver)
2. Presionar → para navegar
3. **Verificar:** Screen reader anuncia "Navigated to highlight 2 of 5. Payment Terms: Payment shall be made..."

**Resultado esperado:** ✅ Anuncios claros para usuarios con screen readers

---

#### TC-007: Sin Highlights
**Prioridad:** LOW
**Pasos:**
1. Abrir un documento sin entidades extraídas (sin highlights)
2. Presionar → y ←
3. **Verificar:** No pasa nada, no hay errores en consola
4. **Verificar:** No se muestra indicador "Highlight 0/0"

**Resultado esperado:** ✅ Manejo graceful de caso sin highlights

---

## 📊 Métricas de Éxito

| Métrica | Target | Cómo Medir |
|---------|--------|------------|
| TypeScript errors | 0 | `npm run build` |
| Build time | < 45s | `npm run build` |
| Bundle size increase | < 5KB | Comparar dist/assets/*.js |
| Performance (keypress → navigation) | < 100ms | Chrome DevTools Performance tab |
| Accessibility score | WCAG AA | axe DevTools |
| User testing satisfaction | > 80% | Manual testing checklist |

---

## 🚀 Timeline

### Estimación por Fase

| Fase | Descripción | Tiempo Estimado |
|------|-------------|-----------------|
| 1 | Agregar estado (currentHighlightIndex, sortedHighlights) | 15 min |
| 2 | Modificar handleKeyDown (ArrowLeft, ArrowRight) | 30 min |
| 3 | Agregar useEffect para auto-navegación | 30 min |
| 4 | Agregar indicador de posición (UI Badge) | 45 min |
| 5 | Reset al cambiar documento | 10 min |
| 6 | Accessibility (ARIA announcements) | 30 min |
| 7 | Testing manual (ejecutar 7 test cases) | 30 min |
| 8 | Documentación y PR | 20 min |
| **TOTAL** | | **~3 horas** |

---

## 🎨 Diseño Visual

### Indicador de Navegación

```
┌─────────────────────────────────────┐
│ PDF Viewer (Panel Izquierdo)       │
│                                     │
│                                     │
│                                     │
│                                     │
│                     ┌───────────────┐
│                     │ Highlight 3/12│ ← Badge en esquina inf. derecha
│                     │ Use ← → to nav│
│                     └───────────────┘
└─────────────────────────────────────┘
```

**Estilos:**
```tsx
<Badge
  variant="secondary"
  className="shadow-lg backdrop-blur-sm bg-background/90"
>
  Highlight {current}/{total}
  <span className="ml-2 text-xs text-muted-foreground">
    Use ← → to navigate
  </span>
</Badge>
```

**Posición:**
- `absolute bottom-4 right-4 z-10`
- Sobre el PDF (overlay)
- Solo visible cuando NO hay búsqueda activa

---

## ⚠️ Consideraciones Técnicas

### 1. Conflictos de Keyboard Shortcuts

**Problema:** Las flechas pueden interferir con:
- Navegación en inputs (solución: check `isInputFocused`)
- Scroll de la página (solución: `e.preventDefault()`)
- Modals abiertos (solución: check si hay modal visible)

**Solución:**
```typescript
const isInputFocused =
  document.activeElement?.tagName === 'INPUT' ||
  document.activeElement?.tagName === 'TEXTAREA';

if (isInputFocused) return; // No manejar flechas
```

---

### 2. Coordinación con Búsqueda

**Desafío:** Decidir cuándo las flechas navegan matches vs todos los highlights.

**Decisión de Diseño:**
- `isSearchVisible = true` → Navegar solo matches (usar `goToNext/goToPrevious`)
- `isSearchVisible = false` → Navegar todos los highlights (usar `currentHighlightIndex`)

**Ventaja:** No hay conflicto, cada contexto tiene su lógica clara.

---

### 3. Performance con Muchos Highlights

**Escenario:** Documento con 100+ highlights.

**Optimización:**
```typescript
// Ya usamos useMemo para sortedHighlights
const sortedHighlights = useMemo(() => {
  return [...highlights].sort((a, b) => a.page - b.page);
}, [highlights]); // Solo re-calcula si highlights cambian
```

**Complejidad:** O(n log n) para sort, pero se ejecuta solo cuando cambian highlights.

---

### 4. Sincronización de Estado

**Problema:** Si se hace click en un highlight manualmente, ¿se actualiza `currentHighlightIndex`?

**Solución:** Modificar `handleHighlightClick`:
```typescript
const handleHighlightClick = (highlightId: string, entityId: string) => {
  setActiveHighlightId(highlightId);

  // Actualizar índice para sincronizar con navegación por flechas
  const index = sortedHighlights.findIndex(h => h.id === highlightId);
  if (index !== -1) {
    setCurrentHighlightIndex(index);
  }

  // Resto del código...
};
```

**Ventaja:** Las flechas continúan desde el highlight clickeado.

---

## 📝 Documentación

### README / User Guide

Agregar sección al `CE-S2-010_TESTING_CHECKLIST.md`:

```markdown
## Keyboard Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| Ctrl+F / Cmd+F | Open highlight search | Global |
| Enter | Next search result | When search is active |
| Shift+Enter | Previous search result | When search is active |
| → | Next highlight | Global (all highlights) |
| ← | Previous highlight | Global (all highlights) |
| Esc | Close search | When search is active |

**Note:** When search is active, arrow keys (← →) navigate only the search results. When search is closed, arrow keys navigate all highlights in the document.
```

---

## 🔄 Rollback Plan

Si algo falla:

1. **Deshacer commit:**
   ```bash
   git revert <commit-hash>
   ```

2. **Feature flag** (si se quiere release gradual):
   ```typescript
   const ENABLE_ARROW_NAVIGATION = process.env.REACT_APP_ARROW_NAV === 'true';

   if (ENABLE_ARROW_NAVIGATION && e.key === 'ArrowRight') {
     // ...
   }
   ```

3. **Remover solo el indicador visual** (si solo la UI tiene issues):
   - Comentar el Badge en JSX
   - Mantener la lógica de navegación

---

## ✅ Checklist de Implementación

**Antes de empezar:**
- [ ] Revisar este plan con el usuario
- [ ] Confirmar prioridad (Media está OK)
- [ ] Decidir: ¿Implementar ahora o después del testing manual de Highlight Search?

**Durante implementación:**
- [ ] Crear branch `feature/keyboard-navigation`
- [ ] Implementar Fase 1: Estado (15 min)
- [ ] Implementar Fase 2: handleKeyDown (30 min)
- [ ] Implementar Fase 3: useEffect auto-navegación (30 min)
- [ ] Implementar Fase 4: Indicador UI (45 min)
- [ ] Implementar Fase 5: Reset documento (10 min)
- [ ] Implementar Fase 6: Accessibility (30 min)
- [ ] Testing local: Ejecutar 7 test cases (30 min)
- [ ] Build verification: `npm run build` (0 errors)

**Después de implementación:**
- [ ] Commit con mensaje descriptivo
- [ ] Push a remote
- [ ] Crear Pull Request
- [ ] Solicitar code review
- [ ] Merge después de aprobación

---

## 🎓 Lecciones de Implementaciones Previas

### De Highlight Search (CE-S2-010)

**Éxitos:**
- ✅ Planificación detallada aceleró desarrollo
- ✅ useMemo/useCallback para performance
- ✅ Documentación exhaustiva facilitó revisión

**Aplicar aquí:**
- Usar misma estructura de plan
- Optimizar con useMemo para sortedHighlights
- Documentar keyboard shortcuts claramente

---

## 📞 Preguntas para el Usuario

Antes de proceder, confirmar:

1. **Prioridad:** ¿Implementar ahora o primero hacer testing manual de Highlight Search?
2. **Scope:** ¿Solo highlights, o también agregar navegación de páginas con flechas arriba/abajo?
3. **UI del indicador:** ¿El badge en esquina inferior derecha está OK, o preferís otra ubicación?
4. **Conflicto con búsqueda:** ¿Te parece bien que las flechas naveguen matches cuando hay búsqueda activa?

---

**Plan preparado por:** Claude Code
**Fecha:** 2026-01-17
**Versión:** 1.0
**Estado:** ✅ READY FOR REVIEW


---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
