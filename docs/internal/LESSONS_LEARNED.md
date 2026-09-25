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
3. Verificar el build de TypeScript: `pnpm build`
4. Validar visualmente el dashboard en localhost

### Prevención Futura

**Checklist Pre-Commit para Cambios de UI:**
- [ ] Ejecutar `pnpm build` para verificar errores de TypeScript
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

## LL-002: Codex Puede Mostrar Login ChatGPT Correcto y Aun Usar una Credencial Obsoleta en un Workspace

**Fecha:** 2026-09-26
**Severidad:** Alta
**Contexto:** C2Pro agent/toolchain operations — Codex CLI on remote VPS

### Problema

Codex CLI devolvía repetidamente:

```text
401 Unauthorized: Incorrect API key provided: sk-svcac…REDACTED
```

contra:

```text
https://chatgpt.com/backend-api/codex/responses
```

aunque todos los indicadores locales de autenticación eran correctos:

- `codex login status` → `Logged in using ChatGPT`
- `auth_mode = chatgpt`
- `stored API key = false`
- `stored ChatGPT tokens = true`
- no existían `OPENAI_API_KEY`, `CODEX_API_KEY` ni `CODEX_ACCESS_TOKEN` en la shell
- `auth.json` contenía tokens JWT de ChatGPT, no una API key
- la red y el handshake WebSocket pasaban en `codex doctor`

El login por Device Code, incluida la validación con llave de seguridad, finalizaba correctamente pero el runtime seguía intentando usar una credencial `sk-svcac…` antigua.

### Impacto

- Codex no podía ejecutar tareas dentro del workspace C2Pro pese a aparecer autenticado.
- Se consumió tiempo investigando autenticación, YubiKey, OAuth, red y versiones cuando la sesión ChatGPT era válida.
- Existía riesgo de revocar o reemplazar una service-account key legítima usada por otro componente si se hubiera asumido erróneamente que era el origen.
- El agente de dependencias #657 quedó temporalmente bloqueado.

### Evidencia y Diagnóstico por Descarte

1. **Login remoto:** el callback OAuth basado en `localhost:1455` no era apropiado para el VPS. Se cambió a Device Code.
2. **YubiKey / ChatGPT:** el Device Code terminó con `Successfully logged in`; la llave no era la causa.
3. **Shell environment:** todas las variables de autenticación relevantes estaban `NOT SET`.
4. **Auth store:** `~/.codex/auth.json` mostraba `auth_mode=chatgpt`, API key nula y access/id tokens JWT.
5. **Configuración:** no se encontró `sk-svcac` ni definición de variables OPENAI/CODEX en el repositorio ni en la configuración normal de Codex.
6. **Backend auth A/B:** una petición HTTP directa usando el `access_token` de `auth.json` devolvió HTTP 400 por payload sin modelo, no HTTP 401. Esto demostró que el JWT era aceptado por el backend.
7. **Versión:** se actualizó Codex CLI de 0.153.4 a 0.157.0. El 401 persistió, por lo que el upgrade por sí solo no era suficiente.
8. **Workspace isolation:** Codex funcionó en `/tmp` y en un repositorio Git limpio.
9. **Feature isolation en C2Pro:** dentro del workspace C2Pro, Codex funcionó cuando se deshabilitó cualquiera de:
   - `features.shell_snapshot=false`
   - `features.workspace_dependencies=false`

### Causa Raíz

**No completamente demostrada.**

La evidencia descarta autenticación ChatGPT, YubiKey, variables de shell, red y la API key almacenada como causa primaria.

El fallo está asociado al **estado/contexto específico del workspace C2Pro y a features de Codex que reutilizan o enriquecen ese contexto**. La presencia de una credencial `sk-svcac…` en la petición pese a no existir en las fuentes normales sugiere estado/metadata de workspace obsoletos.

No se debe afirmar todavía si el defecto concreto está en `shell_snapshot`, `workspace_dependencies` o en una interacción/estado regenerado por esas features: desactivar cualquiera de ellas hizo desaparecer el 401.

### Solución / Workaround Aplicado

Para continuar trabajo sin tocar credenciales válidas:

```bash
cd /srv/aigen/dev/repos/C2Pro

codex \
  -c 'features.shell_snapshot=false'
```

También funcionó:

```bash
codex exec \
  -c 'features.workspace_dependencies=false' \
  "Reply with only: WORKSPACE_DEPENDENCIES_OFF_OK"
```

Se prefirió desactivar temporalmente `shell_snapshot` para conservar `workspace_dependencies` disponible para tareas de análisis de dependencias.

### Lecciones Operativas

- **`codex login status` no prueba que una petición real vaya a usar la misma identidad.** Siempre hacer una llamada mínima de ejecución.
- **Distinguir autenticación de runtime.** Si el JWT directo es aceptado pero Codex CLI devuelve 401 con otra credencial, el problema está después del login.
- **No revocar credenciales por el texto de un 401 sin localizar su procedencia.**
- **No imprimir `auth.json` completo.** Inspeccionar solo estructura, tipos y metadata.
- **Probar fuera del workspace** para separar auth global de estado específico del repo.
- **Aislar feature flags una por una** antes de modificar configuración permanente.
- **Una actualización de versión no sustituye el diagnóstico A/B.** 0.157.0 seguía fallando con la configuración por defecto.
- **En VPS/headless usar Device Code** en lugar de depender de un callback `localhost`.

### Toolchain / Update Pitfall Detectado

El VPS tenía dos raíces npm distintas:

- Codex ejecutado desde:
  `/srv/c2pro/toolchain/npm/lib/node_modules/@openai/codex`
- `npm -g` apuntaba a:
  `/srv/c2pro/toolchain/node/v22.23.2/lib/node_modules`

Por tanto, un `npm install -g @openai/codex` normal podía actualizar una instalación distinta de la que ejecutaba el symlink.

El update correcto fue dirigido explícitamente al prefix activo:

```bash
npm install -g \
  --prefix /srv/c2pro/toolchain/npm \
  @openai/codex@0.157.0
```

Después se verificó con:

```bash
codex --version
codex doctor --json
```

### Checklist de Diagnóstico Futuro

1. `codex login status`
2. `codex doctor --json`
3. comprobar variables OPENAI/CODEX sin mostrar valores
4. inspeccionar estructura de `auth.json`, nunca su contenido completo
5. llamada mínima `codex exec`
6. si hay 401 contradictorio, probar JWT directo con payload deliberadamente incompleto
7. probar Codex en `/tmp` / repo Git limpio
8. comparar con el workspace afectado
9. desactivar `shell_snapshot` y `workspace_dependencies` por separado
10. revisar npm prefix/running package root antes de actualizar
11. no revocar service-account keys hasta demostrar su origen

### Prevención Futura

- Mantener un único root/prefix de instalación para Codex en el toolchain.
- Incorporar `codex doctor` a verificaciones tras upgrades del toolchain.
- Para sesiones críticas, ejecutar una smoke test:
  `codex exec "Reply with only: CODEX_AUTH_OK"`
- No persistir secretos de service accounts en snapshots/workspace metadata.
- Si reaparece el patrón, usar temporalmente `features.shell_snapshot=false` y abrir investigación separada antes de limpiar estado.
- Documentar cualquier eliminación de snapshots/cachés y hacer backup previo si contienen evidencia diagnóstica.

### Referencias

- Codex CLI: 0.153.4 → 0.157.0 durante el incidente
- Workspace: `/srv/aigen/dev/repos/C2Pro`
- Tracking relacionado: #657
- Runbook detallado: [Codex Authentication and Workspace 401 Runbook](./CODEX_AUTH_WORKSPACE_401_RUNBOOK.md)

---

## LL-003: Un CI Rojo Debe Clasificarse por Causa Antes de Modificar una PR

**Fecha:** 2026-09-26
**Severidad:** Alta
**Contexto:** PRs #650, #653, #656 — SQLAlchemy/greenlet, Dependency Audit, P0b

### Problema

Varias PRs mostraron CI rojo por causas distintas de su diff:

- SQLAlchemy 2.1 / `greenlet` durante bootstrap.
- vulnerabilidades críticas de Next.js 16.2.11 en el baseline.
- P0b que agotó timeout porque el Celery worker murió durante la cadena asíncrona.

Modificar la PR funcional para “poner todo verde” habría mezclado alcances y ocultado la causa real.

### Lección

Antes de cambiar código por un CI rojo, clasificar cada fallo como:

1. **regresión propia de la PR**;
2. **baseline/dependencia preexistente**;
3. **infraestructura/configuración del runner**;
4. **flake/intermitencia que exige reproducción**.

La corrección debe vivir en la lane correspondiente. No contaminar una PR de dominio con upgrades de dependencias o reparaciones de CI no relacionadas.

### Prevención Futura

- Revisar el job/log que falla, no solo el estado global.
- Contrastar con el último `main` verde.
- Descargar artifacts de servicio cuando un E2E/P0b solo muestra un timeout.
- Reejecutar únicamente el job sospechoso cuando el resto de gates ya están verdes.
- Exigir evidencia antes de clasificar un fallo como flake.
- Mantener security/dependency fixes en PRs separadas cuando sea posible.

### Referencias

- #653: pin SQLAlchemy/greenlet.
- #654: Next.js 16.3.6 + root lockfile.
- #655: production-runtime E2E.
- #650: HITL/reconciler.
- #656: CRITICAL severity contract.

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

- **Total de lecciones:** 3
- **Severidad Alta:** 3
- **Categorías:**
  - UI/Frontend: 1
  - Backend: 0
  - Infraestructura / Toolchain: 1
  - Proceso / CI: 1

**Última actualización:** 2026-09-26

---

Last Updated: 2026-02-13

Changelog:
- 2026-09-26: Added LL-002 (Codex auth/workspace 401) and LL-003 (CI root-cause classification).
- 2026-02-13: Added metadata block during repository-wide docs format pass.
