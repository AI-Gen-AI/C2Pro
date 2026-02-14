# CE-S2-010: Highlight Search Implementation Plan
**Búsqueda de Highlights por Texto - Media Prioridad**

**Fecha:** 2026-01-17
**Estado:** 📋 PLAN DETALLADO
**Prioridad:** MEDIA
**Prerequisito:** ✅ Highlight Sync Completado

---

## 📋 Tabla de Contenidos

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Objetivos](#objetivos)
3. [Análisis de Datos Existentes](#análisis-de-datos-existentes)
4. [Arquitectura de Componentes](#arquitectura-de-componentes)
5. [Plan de Implementación Paso a Paso](#plan-de-implementación-paso-a-paso)
6. [Especificación de Componentes](#especificación-de-componentes)
7. [Casos de Uso y Flujos](#casos-de-uso-y-flujos)
8. [Testing Plan](#testing-plan)
9. [Optimizaciones Futuras](#optimizaciones-futuras)

---

## Resumen Ejecutivo

### ¿Qué vamos a construir?

Un sistema de búsqueda de highlights que permita a los usuarios:
- 🔍 Buscar por texto en highlights extraídos
- 🎯 Navegar entre resultados (Next/Previous)
- ⌨️ Usar keyboard shortcuts (Ctrl+F, Enter, Esc)
- 📊 Ver contador de matches (ej: "3/12")
- 🎨 Highlight visual de términos encontrados

### ¿Dónde se integra?

En la vista **Evidence Viewer**, como una barra de búsqueda sticky que aparece:
- En el panel izquierdo (PDF Panel), encima del PDF Viewer
- Se muestra/oculta con Ctrl+F
- Integración con el sistema de highlights existente

---

## Objetivos

### Objetivos Funcionales

| # | Objetivo | Criterio de Aceptación |
|---|----------|------------------------|
| 1 | Búsqueda por texto en highlights | Usuario puede escribir query y ver matches en tiempo real |
| 2 | Navegación entre resultados | Botones Next/Previous funcionan correctamente |
| 3 | Contador de resultados | Muestra "X/Y matches" correctamente |
| 4 | Keyboard shortcuts | Ctrl+F abre, Enter navega, Esc cierra |
| 5 | Auto-scroll y highlight | PDF navega automáticamente al resultado activo |
| 6 | Búsqueda case-insensitive | Encuentra "penalty" y "Penalty" |
| 7 | Búsqueda en múltiples campos | Busca en: type, text, originalText |

### Objetivos No Funcionales

- **Performance:** Búsqueda con debounce de 300ms
- **UX:** Animaciones suaves, feedback visual claro
- **Accesibilidad:** Keyboard navigation completa, ARIA labels
- **Responsividad:** Funciona en desktop y tablet

---

## Análisis de Datos Existentes

### Estructura de Entidades (mockExtractedEntities)

```typescript
interface ExtractedEntity {
  id: string;              // "ENT-001"
  documentId: string;      // "contract"
  type: string;            // "Penalty Clause"
  text: string;            // Texto extraído (resumido)
  originalText: string;    // Texto completo original
  confidence: number;      // 0-100
  validated: boolean;
  page: number;            // Página del PDF
  linkedWbs: string[];
  linkedAlerts: string[];
  highlightRects: Rectangle[];
}
```

### Campos Buscables

| Campo | Peso | Ejemplo | Notas |
|-------|------|---------|-------|
| `type` | Alto | "Penalty Clause" | Tipo de entidad |
| `text` | Alto | "In case of delay..." | Texto resumido |
| `originalText` | Medio | Texto completo | Backup si text es corto |
| `id` | Bajo | "ENT-001" | Para búsquedas técnicas |

### Highlights Generados

```typescript
// En EvidenceViewer.tsx:309-325
const highlights: Highlight[] = useMemo(() => {
  return currentEntities.map((entity) =>
    createHighlight(
      entity.id,
      entity.page,
      entity.highlightRects,
      getHighlightColor(entity.confidence),
      entity.type
    )
  );
}, [currentEntities]);
```

**Relación:**
- 1 Entity → 1 Highlight
- Highlight.entityId === Entity.id
- Highlight.label === Entity.type

---

## Arquitectura de Componentes

### Diagrama de Componentes

```
┌─────────────────────────────────────────────────────┐
│ EvidenceViewer.tsx                                  │
│                                                     │
│  ┌────────────────────────────────────────────┐    │
│  │ PDF Panel (Left 40%)                       │    │
│  │                                             │    │
│  │  ┌───────────────────────────────────────┐ │    │
│  │  │ HighlightSearchBar (NEW)              │ │    │
│  │  │ [🔍 Search highlights...] [3/12] [▲▼] │ │    │
│  │  └───────────────────────────────────────┘ │    │
│  │                                             │    │
│  │  ┌───────────────────────────────────────┐ │    │
│  │  │ PDFViewer                             │ │    │
│  │  │ - highlights (filtered)               │ │    │
│  │  │ - activeHighlightId (current match)   │ │    │
│  │  └───────────────────────────────────────┘ │    │
│  └────────────────────────────────────────────┘    │
│                                                     │
│  useHighlightSearch(highlights, entities) (NEW)    │
│    ├─ searchQuery: string                          │
│    ├─ matches: Highlight[]                         │
│    ├─ currentIndex: number                         │
│    ├─ goToNext(), goToPrevious()                   │
│    └─ clearSearch()                                │
└─────────────────────────────────────────────────────┘
```

### Flujo de Datos

```
User types "penalty" in SearchBar
    ↓
useHighlightSearch hook updates searchQuery
    ↓
useMemo filters highlights based on query
    ↓
matches array updated: [Highlight{id: "highlight-ENT-001"}]
    ↓
currentIndex = 0 (first match)
    ↓
EvidenceViewer updates:
    - setPageNumber(matches[0].page)
    - setActiveHighlightId(matches[0].id)
    ↓
PDFViewer navigates to page and highlights the entity
    ↓
Data Panel scrolls to corresponding entity card
```

---

## Plan de Implementación Paso a Paso

### Fase 1: Crear Hook useHighlightSearch

**Archivo:** `vision-matched-repo/src/hooks/useHighlightSearch.ts`

**Responsabilidades:**
- Gestionar estado de búsqueda (query, matches, currentIndex)
- Filtrar highlights según query
- Navegación entre resultados (next/previous)
- Lógica de búsqueda fuzzy/exact

**Features:**
```typescript
interface UseHighlightSearchReturn {
  // State
  searchQuery: string;
  matches: Highlight[];
  currentIndex: number;
  isSearchActive: boolean;

  // Actions
  setSearchQuery: (query: string) => void;
  goToNext: () => void;
  goToPrevious: () => void;
  goToMatch: (index: number) => void;
  clearSearch: () => void;

  // Computed
  totalMatches: number;
  currentMatch: Highlight | null;
  matchCounter: string; // "3/12"
}
```

**Algoritmo de Búsqueda:**

```typescript
// Búsqueda multi-campo con scoring
function searchHighlights(query: string, entities: ExtractedEntity[]): Highlight[] {
  if (!query.trim()) return [];

  const lowerQuery = query.toLowerCase();

  const matches = entities.filter(entity => {
    // Search in type (high weight)
    if (entity.type.toLowerCase().includes(lowerQuery)) return true;

    // Search in text (high weight)
    if (entity.text.toLowerCase().includes(lowerQuery)) return true;

    // Search in originalText (medium weight)
    if (entity.originalText.toLowerCase().includes(lowerQuery)) return true;

    // Search in ID (low weight)
    if (entity.id.toLowerCase().includes(lowerQuery)) return true;

    return false;
  });

  // Convert to highlights
  return matches.map(entity =>
    createHighlight(entity.id, entity.page, entity.highlightRects,
                    getHighlightColor(entity.confidence), entity.type)
  );
}
```

---

### Fase 2: Crear Componente HighlightSearchBar

**Archivo:** `vision-matched-repo/src/components/pdf/HighlightSearchBar.tsx`

**Props Interface:**
```typescript
interface HighlightSearchBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  currentIndex: number;
  totalMatches: number;
  onNext: () => void;
  onPrevious: () => void;
  onClose: () => void;
  isVisible: boolean;
}
```

**UI Structure:**
```
┌────────────────────────────────────────────────────────┐
│ [🔍] [Search highlights in this document...]  [3/12]   │
│                                        [▲] [▼] [✕]     │
└────────────────────────────────────────────────────────┘
```

**Componentes shadcn/ui:**
- `Input` - Búsqueda con debounce
- `Button` (variant="ghost") - Next/Previous/Close
- `Badge` - Counter "3/12"
- `Card` - Container con shadow sutil

**Estilos:**
```css
/* Sticky positioning */
.highlight-search-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  background: white;
  border-bottom: 1px solid hsl(214.3 31.8% 91.4%);
  padding: 0.75rem 1rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

/* Animación de entrada/salida */
.search-bar-enter {
  animation: slideDown 0.2s ease-out;
}

.search-bar-exit {
  animation: slideUp 0.2s ease-in;
}

@keyframes slideDown {
  from { transform: translateY(-100%); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

@keyframes slideUp {
  from { transform: translateY(0); opacity: 1; }
  to { transform: translateY(-100%); opacity: 0; }
}
```

**Estados del Componente:**

| Estado | Query | Matches | UI Display |
|--------|-------|---------|------------|
| Idle | "" | 0 | Input placeholder, buttons disabled |
| Searching | "pen" | 0 | Input with text, "No matches" badge |
| HasMatches | "penalty" | 3 | "3/12", navigation enabled |
| NoDocument | Any | 0 | "Load a document first" message |

---

### Fase 3: Integrar en EvidenceViewer

**Archivo:** `vision-matched-repo/src/pages/EvidenceViewer.tsx`

**Cambios Necesarios:**

```typescript
// 1. Import nuevo hook y componente
import { useHighlightSearch } from '@/hooks/useHighlightSearch';
import { HighlightSearchBar } from '@/components/pdf/HighlightSearchBar';

// 2. Estado para visibilidad de búsqueda
const [isSearchVisible, setIsSearchVisible] = useState(false);

// 3. Usar el hook
const {
  searchQuery,
  setSearchQuery,
  matches,
  currentIndex,
  totalMatches,
  currentMatch,
  goToNext,
  goToPrevious,
  clearSearch,
  matchCounter,
} = useHighlightSearch(highlights, currentEntities);

// 4. Effect: Navigate when currentMatch changes
useEffect(() => {
  if (currentMatch) {
    // Find the entity for this match
    const entity = currentEntities.find(e =>
      `highlight-${e.id}` === currentMatch.id
    );

    if (entity) {
      // Navigate to page
      setPageNumber(entity.page);
      // Set active highlight
      setActiveHighlightId(currentMatch.id);
      // Scroll to entity card
      handleEntityCardClick(entity);
    }
  }
}, [currentMatch]);

// 5. Keyboard shortcuts
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    // Open search with Ctrl+F
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
      e.preventDefault();
      setIsSearchVisible(true);
    }

    // Close with Esc
    if (e.key === 'Escape' && isSearchVisible) {
      setIsSearchVisible(false);
      clearSearch();
    }

    // Navigate with Enter (next) and Shift+Enter (previous)
    if (e.key === 'Enter' && isSearchVisible && totalMatches > 0) {
      e.preventDefault();
      if (e.shiftKey) {
        goToPrevious();
      } else {
        goToNext();
      }
    }
  };

  window.addEventListener('keydown', handleKeyDown);
  return () => window.removeEventListener('keydown', handleKeyDown);
}, [isSearchVisible, totalMatches]);

// 6. Render SearchBar in PDF Panel
<div className="pdf-panel-container">
  {/* SearchBar - Sticky at top */}
  {isSearchVisible && (
    <HighlightSearchBar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      currentIndex={currentIndex}
      totalMatches={totalMatches}
      onNext={goToNext}
      onPrevious={goToPrevious}
      onClose={() => {
        setIsSearchVisible(false);
        clearSearch();
      }}
      isVisible={isSearchVisible}
    />
  )}

  {/* PDF Viewer */}
  <PDFViewer
    documentUrl={currentDocument.url}
    pageNumber={pageNumber}
    // ...resto de props
  />
</div>
```

---

### Fase 4: Keyboard Shortcuts

**Shortcuts a Implementar:**

| Shortcut | Acción | Contexto |
|----------|--------|----------|
| `Ctrl+F` / `Cmd+F` | Abrir búsqueda | Global en Evidence Viewer |
| `Esc` | Cerrar búsqueda | Cuando search bar está visible |
| `Enter` | Ir a siguiente resultado | Cuando search bar está activa |
| `Shift+Enter` | Ir a resultado anterior | Cuando search bar está activa |
| `Ctrl+G` / `Cmd+G` | Ir a siguiente (alternativo) | Opcional |
| `Ctrl+Shift+G` | Ir a anterior (alternativo) | Opcional |

**Implementación con useEffect:**

```typescript
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    const isCtrlOrCmd = e.ctrlKey || e.metaKey;

    // Prevent default browser search
    if (isCtrlOrCmd && e.key === 'f') {
      e.preventDefault();
      setIsSearchVisible(true);
      // Auto-focus on input
      setTimeout(() => {
        document.getElementById('highlight-search-input')?.focus();
      }, 100);
    }

    // Close search
    if (e.key === 'Escape') {
      if (isSearchVisible) {
        e.preventDefault();
        setIsSearchVisible(false);
        clearSearch();
        setActiveHighlightId(null);
      }
    }

    // Navigate results (only when search is active)
    if (isSearchVisible && totalMatches > 0) {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (e.shiftKey) {
          goToPrevious();
        } else {
          goToNext();
        }
      }

      // Alternative shortcuts (Ctrl+G)
      if (isCtrlOrCmd && e.key === 'g') {
        e.preventDefault();
        if (e.shiftKey) {
          goToPrevious();
        } else {
          goToNext();
        }
      }
    }
  };

  window.addEventListener('keydown', handleKeyDown);
  return () => window.removeEventListener('keydown', handleKeyDown);
}, [isSearchVisible, totalMatches, currentIndex]);
```

**ARIA Announcements para Screen Readers:**

```typescript
// En useHighlightSearch hook
useEffect(() => {
  if (matches.length > 0) {
    // Announce to screen readers
    const announcement = `${matches.length} matches found. Current match ${currentIndex + 1} of ${matches.length}`;
    announceToScreenReader(announcement);
  } else if (searchQuery.length > 0) {
    announceToScreenReader('No matches found');
  }
}, [matches, currentIndex]);

function announceToScreenReader(message: string) {
  const announcer = document.getElementById('sr-announcer');
  if (announcer) {
    announcer.textContent = message;
  }
}

// En EvidenceViewer JSX
<div id="sr-announcer" className="sr-only" role="status" aria-live="polite" aria-atomic="true" />
```

---

## Especificación de Componentes

### 1. useHighlightSearch Hook

**Ubicación:** `vision-matched-repo/src/hooks/useHighlightSearch.ts`

**Código Completo (Pseudocódigo):**

```typescript
import { useState, useMemo, useCallback } from 'react';
import type { Highlight } from '@/types/highlight';

interface ExtractedEntity {
  id: string;
  type: string;
  text: string;
  originalText: string;
  page: number;
  // ... otros campos
}

export function useHighlightSearch(
  highlights: Highlight[],
  entities: ExtractedEntity[]
) {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);

  // Filter matches based on search query
  const matches = useMemo(() => {
    if (!searchQuery.trim()) return [];

    const lowerQuery = searchQuery.toLowerCase();

    const matchedEntities = entities.filter(entity => {
      return (
        entity.type.toLowerCase().includes(lowerQuery) ||
        entity.text.toLowerCase().includes(lowerQuery) ||
        entity.originalText.toLowerCase().includes(lowerQuery) ||
        entity.id.toLowerCase().includes(lowerQuery)
      );
    });

    // Convert entity IDs to highlight IDs
    const matchedIds = new Set(matchedEntities.map(e => `highlight-${e.id}`));

    return highlights.filter(h => matchedIds.has(h.id));
  }, [searchQuery, highlights, entities]);

  // Reset index when matches change
  useEffect(() => {
    if (matches.length > 0 && currentIndex >= matches.length) {
      setCurrentIndex(0);
    }
  }, [matches]);

  // Navigation functions
  const goToNext = useCallback(() => {
    if (matches.length === 0) return;
    setCurrentIndex((prev) => (prev + 1) % matches.length);
  }, [matches.length]);

  const goToPrevious = useCallback(() => {
    if (matches.length === 0) return;
    setCurrentIndex((prev) => (prev - 1 + matches.length) % matches.length);
  }, [matches.length]);

  const goToMatch = useCallback((index: number) => {
    if (index >= 0 && index < matches.length) {
      setCurrentIndex(index);
    }
  }, [matches.length]);

  const clearSearch = useCallback(() => {
    setSearchQuery('');
    setCurrentIndex(0);
  }, []);

  // Computed values
  const totalMatches = matches.length;
  const currentMatch = matches[currentIndex] || null;
  const matchCounter = totalMatches > 0
    ? `${currentIndex + 1}/${totalMatches}`
    : '0/0';
  const isSearchActive = searchQuery.trim().length > 0;

  return {
    searchQuery,
    setSearchQuery,
    matches,
    currentIndex,
    currentMatch,
    totalMatches,
    matchCounter,
    isSearchActive,
    goToNext,
    goToPrevious,
    goToMatch,
    clearSearch,
  };
}
```

---

### 2. HighlightSearchBar Component

**Ubicación:** `vision-matched-repo/src/components/pdf/HighlightSearchBar.tsx`

**Código Completo (Pseudocódigo):**

```typescript
import { useState, useEffect, useRef } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Search, ChevronUp, ChevronDown, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface HighlightSearchBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  currentIndex: number;
  totalMatches: number;
  onNext: () => void;
  onPrevious: () => void;
  onClose: () => void;
  isVisible: boolean;
}

export function HighlightSearchBar({
  searchQuery,
  onSearchChange,
  currentIndex,
  totalMatches,
  onNext,
  onPrevious,
  onClose,
  isVisible,
}: HighlightSearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [localQuery, setLocalQuery] = useState(searchQuery);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      onSearchChange(localQuery);
    }, 300);

    return () => clearTimeout(timer);
  }, [localQuery, onSearchChange]);

  // Auto-focus when visible
  useEffect(() => {
    if (isVisible && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isVisible]);

  // Sync with external query changes
  useEffect(() => {
    setLocalQuery(searchQuery);
  }, [searchQuery]);

  if (!isVisible) return null;

  const hasMatches = totalMatches > 0;
  const hasQuery = localQuery.trim().length > 0;
  const matchCounter = hasMatches
    ? `${currentIndex + 1}/${totalMatches}`
    : hasQuery
      ? 'No matches'
      : '';

  return (
    <Card className={cn(
      "sticky top-0 z-20 border-b shadow-sm",
      "animate-in slide-in-from-top duration-200"
    )}>
      <div className="flex items-center gap-2 p-3">
        {/* Search Icon */}
        <Search className="h-4 w-4 text-muted-foreground" />

        {/* Search Input */}
        <Input
          ref={inputRef}
          id="highlight-search-input"
          type="text"
          placeholder="Search highlights in this document..."
          value={localQuery}
          onChange={(e) => setLocalQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              if (e.shiftKey) {
                onPrevious();
              } else {
                onNext();
              }
            } else if (e.key === 'Escape') {
              onClose();
            }
          }}
          className="flex-1 h-9"
          aria-label="Search highlights"
          aria-describedby="search-results-count"
        />

        {/* Match Counter */}
        <Badge
          variant={hasMatches ? "secondary" : hasQuery ? "outline" : "secondary"}
          className="min-w-[60px] text-center"
          id="search-results-count"
        >
          {matchCounter}
        </Badge>

        {/* Navigation Buttons */}
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={onPrevious}
            disabled={!hasMatches}
            aria-label="Previous match"
            className="h-9 w-9"
          >
            <ChevronUp className="h-4 w-4" />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={onNext}
            disabled={!hasMatches}
            aria-label="Next match"
            className="h-9 w-9"
          >
            <ChevronDown className="h-4 w-4" />
          </Button>
        </div>

        {/* Close Button */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close search"
          className="h-9 w-9"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Keyboard Shortcuts Hint (optional) */}
      {hasMatches && (
        <div className="px-3 pb-2 text-xs text-muted-foreground">
          Press <kbd className="px-1 py-0.5 bg-muted rounded">Enter</kbd> for next,{' '}
          <kbd className="px-1 py-0.5 bg-muted rounded">Shift+Enter</kbd> for previous
        </div>
      )}
    </Card>
  );
}
```

**Estilos CSS Adicionales (si es necesario):**

```css
/* vision-matched-repo/src/components/pdf/highlight-search-bar.css */

.highlight-search-bar kbd {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.75rem;
  font-weight: 600;
}

/* Animation for match counter when it changes */
@keyframes bounce-subtle {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

.match-counter-changed {
  animation: bounce-subtle 0.3s ease-in-out;
}
```

---

## Casos de Uso y Flujos

### Caso de Uso 1: Búsqueda Exitosa

```
User Story:
Como revisor de contratos, quiero buscar todas las menciones de "penalty"
para analizar cláusulas penales.

Flujo:
1. Usuario presiona Ctrl+F
   → SearchBar aparece con animación slide-down
   → Input tiene auto-focus

2. Usuario escribe "penalty"
   → Después de 300ms, búsqueda se ejecuta
   → Hook filtra: 2 matches encontrados
   → Badge muestra "1/2"
   → PDF navega automáticamente a página 12 (primer match)
   → Highlight ENT-001 se activa (pulsa suavemente)
   → Data panel scroll a Entity Card correspondiente

3. Usuario presiona Enter
   → currentIndex incrementa: 0 → 1
   → Badge actualiza: "2/2"
   → PDF navega a página 22 (segundo match)
   → Highlight ENT-004 se activa

4. Usuario presiona Enter nuevamente
   → currentIndex cicla: 1 → 0 (vuelve al primero)
   → Badge: "1/2"
   → PDF navega de vuelta a página 12

5. Usuario presiona Esc
   → SearchBar se oculta con animación
   → Búsqueda se limpia
   → Highlights vuelven a estado normal
```

---

### Caso de Uso 2: Búsqueda Sin Resultados

```
User Story:
Usuario busca un término que no existe en el documento.

Flujo:
1. Usuario abre búsqueda (Ctrl+F)
2. Usuario escribe "xyz123"
   → Después de debounce, búsqueda se ejecuta
   → matches = []
   → Badge muestra "No matches"
   → Input mantiene el texto
   → Botones Next/Previous disabled

3. Usuario borra el texto y escribe "payment"
   → Nueva búsqueda encuentra 1 resultado
   → Badge: "1/1"
   → PDF navega al match
```

---

### Caso de Uso 3: Búsqueda Multi-Documento

```
User Story:
Usuario busca "equipment" en documento de contrato, luego cambia a BOM.

Flujo:
1. Usuario en "Contract_Final.pdf"
2. Busca "equipment" → 0 matches
3. Usuario cambia documento a "BOM_Equipment.pdf"
   → currentDocument cambia
   → highlights se recalculan (solo entities del nuevo doc)
   → Búsqueda se re-ejecuta automáticamente
   → matches = 2 (ENT-007, ENT-008)
   → Badge: "1/2"
   → PDF navega a primer resultado del nuevo documento
```

**Implementación del Auto-Re-search:**

```typescript
// En useHighlightSearch hook
useEffect(() => {
  // When entities change (document switch), re-run search
  if (searchQuery.trim()) {
    // Matches will auto-update via useMemo
    // Reset to first match
    setCurrentIndex(0);
  }
}, [entities]);
```

---

### Caso de Uso 4: Búsqueda por Tipo de Entidad

```
User Story:
Usuario quiere ver todas las "Milestone Date" en el schedule.

Flujo:
1. Usuario en "Project_Schedule_v3.pdf"
2. Busca "milestone"
   → Encuentra ENT-005 (type: "Milestone Date")
   → Badge: "1/1"
   → Navega a la entidad

Note: La búsqueda es en todos los campos, incluyendo `type`,
por lo que "milestone" encuentra "Milestone Date".
```

---

## Testing Plan

### Test Cases - Manual Testing

#### TC-001: Basic Search Flow
```
Precondition: Evidence Viewer abierto con documento cargado
Steps:
1. Press Ctrl+F
2. Type "payment"
3. Verify:
   - SearchBar is visible
   - Input shows "payment"
   - Badge shows correct count
   - PDF navigates to first match
   - Highlight is active
4. Press Enter
5. Verify:
   - Navigates to next match
   - Counter updates
6. Press Esc
7. Verify:
   - SearchBar closes
   - Search is cleared

Expected: All verifications pass
```

#### TC-002: Debounce Functionality
```
Precondition: SearchBar open
Steps:
1. Type "p" quickly
2. Wait 100ms
3. Type "e"
4. Wait 100ms
5. Type "n"
6. Wait 400ms (> debounce time)
7. Verify: Search executes only once with "pen"

Expected: Only 1 search execution, not 3
```

#### TC-003: Navigation Loop
```
Precondition: Search with 3 matches active
Steps:
1. Verify: Counter shows "1/3"
2. Press Enter 2 times
3. Verify: Counter shows "3/3"
4. Press Enter 1 more time
5. Verify: Counter loops back to "1/3"
6. Press Shift+Enter
7. Verify: Counter goes to "3/3"

Expected: Navigation loops correctly
```

#### TC-004: No Matches
```
Steps:
1. Search for "xyzabc123"
2. Verify:
   - Badge shows "No matches"
   - Navigation buttons disabled
   - No PDF navigation
3. Clear and search "payment"
4. Verify:
   - Matches found
   - Navigation re-enabled

Expected: Graceful handling of no results
```

#### TC-005: Document Switch
```
Precondition: Search active with matches
Steps:
1. Search "penalty" in Contract document (2 matches)
2. Change document to Schedule
3. Verify:
   - Search query persists
   - Matches recalculated (0 matches in Schedule)
   - Badge updates to "No matches"
4. Change document back to Contract
5. Verify:
   - Matches found again (2)

Expected: Search adapts to document changes
```

#### TC-006: Case Insensitivity
```
Steps:
1. Search "PENALTY"
2. Verify: Finds "Penalty Clause"
3. Clear and search "penalty"
4. Verify: Same results
5. Clear and search "PeNaLtY"
6. Verify: Same results

Expected: All cases find same matches
```

#### TC-007: Multi-Field Search
```
Precondition: Entity with:
  - type: "Payment Terms"
  - text: "Payment shall be made..."
  - id: "ENT-002"

Steps:
1. Search "payment terms"
2. Verify: Finds entity (matches type)
3. Search "shall be made"
4. Verify: Finds entity (matches text)
5. Search "ENT-002"
6. Verify: Finds entity (matches id)

Expected: All fields are searchable
```

#### TC-008: Keyboard Shortcuts
```
Steps:
1. Verify: Ctrl+F opens search
2. Verify: Cmd+F opens search (Mac)
3. Verify: Esc closes search
4. Verify: Enter navigates next
5. Verify: Shift+Enter navigates previous
6. With search closed, press Enter
7. Verify: No navigation (search not active)

Expected: All shortcuts work correctly
```

#### TC-009: Performance (100+ Entities)
```
Precondition: Mock 150 entities
Steps:
1. Search "the" (common word, 50+ matches)
2. Measure:
   - Time from keypress to results display
   - Memory usage
3. Verify:
   - Results appear within 500ms
   - No UI freeze
   - Navigation is smooth

Expected: Performance acceptable
```

#### TC-010: Accessibility
```
Steps:
1. Open search with keyboard only
2. Navigate using Tab
3. Verify:
   - Input receives focus
   - Buttons are tabbable
   - ARIA labels present
4. Use screen reader
5. Verify:
   - Announces match count
   - Announces navigation

Expected: Fully keyboard accessible
```

---

### Integration Testing

```typescript
// vision-matched-repo/src/__tests__/hooks/useHighlightSearch.test.ts

import { renderHook, act } from '@testing-library/react';
import { useHighlightSearch } from '@/hooks/useHighlightSearch';

describe('useHighlightSearch', () => {
  const mockHighlights = [
    { id: 'highlight-ENT-001', label: 'Penalty Clause', page: 12 },
    { id: 'highlight-ENT-002', label: 'Payment Terms', page: 8 },
  ];

  const mockEntities = [
    { id: 'ENT-001', type: 'Penalty Clause', text: 'In case of delay...', page: 12 },
    { id: 'ENT-002', type: 'Payment Terms', text: 'Payment shall be...', page: 8 },
  ];

  test('filters matches based on query', () => {
    const { result } = renderHook(() =>
      useHighlightSearch(mockHighlights, mockEntities)
    );

    act(() => {
      result.current.setSearchQuery('penalty');
    });

    expect(result.current.totalMatches).toBe(1);
    expect(result.current.matches[0].id).toBe('highlight-ENT-001');
  });

  test('navigates to next match', () => {
    const { result } = renderHook(() =>
      useHighlightSearch(mockHighlights, mockEntities)
    );

    act(() => {
      result.current.setSearchQuery('a'); // Matches both
    });

    expect(result.current.currentIndex).toBe(0);

    act(() => {
      result.current.goToNext();
    });

    expect(result.current.currentIndex).toBe(1);
  });

  test('loops navigation at end', () => {
    const { result } = renderHook(() =>
      useHighlightSearch(mockHighlights, mockEntities)
    );

    act(() => {
      result.current.setSearchQuery('a');
      result.current.goToNext(); // 1
      result.current.goToNext(); // Should loop to 0
    });

    expect(result.current.currentIndex).toBe(0);
  });
});
```

---

## Optimizaciones Futuras

### Fase 2 (Post-MVP)

#### 1. Fuzzy Search
```typescript
// Usar librería como 'fuse.js'
import Fuse from 'fuse.js';

const fuse = new Fuse(entities, {
  keys: ['type', 'text', 'originalText'],
  threshold: 0.3, // 30% similarity
});

const matches = fuse.search(searchQuery);
```

**Beneficio:** Encuentra "penlty" cuando buscan "penalty"

---

#### 2. Highlight del Término en Entity Cards
```typescript
// En EntityCard component
function highlightSearchTerm(text: string, query: string) {
  if (!query) return text;

  const regex = new RegExp(`(${query})`, 'gi');
  return text.replace(regex, '<mark>$1</mark>');
}

<p dangerouslySetInnerHTML={{
  __html: highlightSearchTerm(entity.text, searchQuery)
}} />
```

**Beneficio:** Visual feedback en las cards también

---

#### 3. Search History
```typescript
// Guardar últimas 10 búsquedas en localStorage
const [searchHistory, setSearchHistory] = useLocalStorage('search-history', []);

// Dropdown con sugerencias
<Combobox
  items={searchHistory}
  onSelect={(item) => setSearchQuery(item)}
/>
```

**Beneficio:** Búsquedas repetidas más rápidas

---

#### 4. Search Filters
```typescript
// Opciones de filtro adicionales
interface SearchFilters {
  types: string[];        // Filter by entity type
  confidenceMin: number;  // Only show high-confidence
  validated: boolean | null; // Only validated/unvalidated
}

<Select onValueChange={(type) => setFilterType(type)}>
  <SelectItem value="all">All Types</SelectItem>
  <SelectItem value="Penalty Clause">Penalty Clauses</SelectItem>
  <SelectItem value="Payment Terms">Payment Terms</SelectItem>
</Select>
```

**Beneficio:** Búsquedas más precisas

---

#### 5. Export Search Results
```typescript
function exportMatches(matches: Highlight[]) {
  const csv = matches.map(m => ({
    id: m.entityId,
    type: m.label,
    page: m.page,
  }));

  downloadCSV(csv, 'search-results.csv');
}

<Button onClick={() => exportMatches(matches)}>
  Export Results
</Button>
```

**Beneficio:** Análisis offline de resultados

---

## Métricas de Éxito

| Métrica | Target | Medición |
|---------|--------|----------|
| **Time to First Result** | < 500ms | Desde keypress hasta highlight visible |
| **Search Accuracy** | 100% | Encuentra todos los matches relevantes |
| **Keyboard Navigation** | 100% | Todas las acciones disponibles por teclado |
| **Debounce Performance** | 300ms | No lag durante escritura rápida |
| **User Adoption** | >80% | % de usuarios que usan Ctrl+F vs scroll manual |

---

## Timeline Estimado

| Fase | Tarea | Tiempo | Responsable |
|------|-------|--------|-------------|
| **Fase 1** | Crear hook useHighlightSearch | 2h | Dev |
| **Fase 2** | Crear componente HighlightSearchBar | 2h | Dev |
| **Fase 3** | Integrar en EvidenceViewer | 1.5h | Dev |
| **Fase 4** | Keyboard shortcuts | 1h | Dev |
| **Fase 5** | Testing manual | 1.5h | QA + Dev |
| **Fase 6** | Bug fixes y polish | 1h | Dev |
| | **TOTAL** | **9 horas** | |

---

## Dependencias

### Técnicas
- ✅ Sistema de highlights existente (completado)
- ✅ PDFViewer con navegación por página
- ✅ EntityCards con refs para scroll
- ✅ shadcn/ui components (Input, Button, Badge, Card)

### Humanas
- Frontend Developer (9h)
- QA Tester (1.5h manual testing)
- UX Reviewer (30min para aprobar UI)

---

## Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Performance con 100+ entities | Media | Medio | Debounce + useMemo optimización |
| Conflicts con browser Ctrl+F | Alta | Bajo | preventDefault() + clear messaging |
| Search no encuentra variantes | Media | Medio | Fuzzy search en Fase 2 |
| Keyboard shortcuts no intuitivos | Baja | Bajo | Hints en UI + documentación |

---

## Aprobación y Sign-off

### Checklist de Implementación Completada

- [ ] Hook useHighlightSearch implementado
- [ ] Componente HighlightSearchBar implementado
- [ ] Integración en EvidenceViewer completada
- [ ] Keyboard shortcuts funcionando
- [ ] Todos los test cases pasados
- [ ] Performance verificada (< 500ms)
- [ ] Accessibility review completado
- [ ] Documentación actualizada
- [ ] Demo grabada para stakeholders

### Criterios de Aceptación Final

**Must Have:**
1. ✅ Usuario puede buscar highlights por texto
2. ✅ Navegación Next/Previous funciona
3. ✅ Ctrl+F abre búsqueda
4. ✅ Counter muestra "X/Y"
5. ✅ PDF navega al match activo

**Should Have:**
6. ✅ Búsqueda case-insensitive
7. ✅ Debounce de 300ms
8. ✅ Esc cierra búsqueda
9. ✅ Enter navega resultados

**Could Have:**
10. ⏳ Fuzzy search (Fase 2)
11. ⏳ Search history (Fase 2)
12. ⏳ Export results (Fase 2)

---

## Próximos Pasos

Una vez aprobado este plan:

1. **Crear branch:** `feature/highlight-search`
2. **Implementar Fase 1:** Hook useHighlightSearch
3. **Implementar Fase 2:** HighlightSearchBar component
4. **Implementar Fase 3:** Integración
5. **Implementar Fase 4:** Keyboard shortcuts
6. **Testing:** Ejecutar todos los test cases
7. **Pull Request:** Con screenshots/video demo
8. **Code Review:** Por tech lead
9. **Merge:** A main/development
10. **Deploy:** A staging para UAT

---

**Prepared by:** Claude Code
**Date:** 2026-01-17
**Version:** 1.0
**Status:** ✅ READY FOR APPROVAL


---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
