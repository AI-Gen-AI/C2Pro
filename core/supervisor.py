"""C2Pro Multi-Agent Orchestration Supervisor

Coordinates 9 specialized agent roles through a unified blackboard pattern:
  • planner   - Strategic planning and task decomposition
  • backend   - API and server-side implementation
  • frontend  - UI/UX component development
  • ai        - AI/ML model development and deployment
  • infra     - Infrastructure provisioning and configuration
  • qa        - Quality assurance and testing
  • reviewer  - Code review and quality feedback
  • security  - Security audits and vulnerability analysis
  • devops    - CI/CD pipeline and deployment automation

All tasks enforce mandatory backlog_id linking (pattern: TASK-XXX-YYY) to ensure
complete traceability between ephemeral session state (blackboard.json) and
permanent task register (C2PRO_MASTER_BACKLOG.md).

Defense-in-Depth Validation (4 Layers):
  1. Schema Validation    - JSON Schema Draft-07 validation (schemas/{role}_output.json)
  2. Runtime Validation   - backlog_id pattern enforcement (^TASK-[A-Z0-9-]+$)
  3. Pre-Exec Validation  - Verify backlog_id exists in files before execution
  4. Post-Exec Validation - Verify backlog updated after task completion

Configuration:
  • Role assignments: core/session_config.json
  • Model assignments: core/models.yaml
  • Session state:     blackboard.json (ephemeral)
  • Permanent backlog: C2PRO_MASTER_BACKLOG.md + backlogs/*.md

Documentation:
  • Complete Guide: docs/workflows/AGENT_ORCHESTRATION_GUIDE.md
  • Architecture:   AGENT_STRUCTURE_UNIFICATION_ANALYSIS.md

Usage Examples:
    # Execute task with automatic agent orchestration
    python core/supervisor.py "Add user authentication to API"

    # Interactive mode (shows commands without executing)
    python core/supervisor.py "Deploy to staging" --modo interactivo

    # Show current blackboard state
    python core/supervisor.py --estado

    # Show session configuration
    python core/supervisor.py --init
"""
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML requerido. pip install pyyaml")
    sys.exit(1)

# Import schema validator for UNIFY-012
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from schemas.validator import VALID_ROLES, validate_role_output
except ImportError as e:
    print(f"WARNING: Schema validator not available: {e}")
    print("Schema validation will be skipped. Install jsonschema: pip install jsonschema")
    validate_role_output = None
    VALID_ROLES = []

BASE_DIR = Path(__file__).resolve().parent.parent
BLACKBOARD_PATH = BASE_DIR / "blackboard.json"
BLACKBOARD_SCHEMA_PATH = BASE_DIR / "schemas" / "blackboard_schema.json"
MODELS_PATH = BASE_DIR / "core" / "models.yaml"
SESSION_CONFIG_PATH = BASE_DIR / "core" / "session_config.json"
ROLES_DIR = BASE_DIR / "roles"
LOGS_PATH = BASE_DIR / "logs" / "execution_traces.log"
METRICS_PATH = BASE_DIR / "logs" / "metrics.json"

# Regex pattern for valid backlog_id (must match schemas/blackboard_schema.json)
BACKLOG_ID_PATTERN = re.compile(r"^TASK-[A-Z0-9-]+$")

# Backlog file paths
MASTER_BACKLOG_PATH = BASE_DIR / "C2PRO_MASTER_BACKLOG.md"
CATEGORY_BACKLOGS_DIR = BASE_DIR / "backlogs"


def cargar_legacy_compatibility() -> dict:
    compat_path = BASE_DIR / ".c2pro" / "control" / "legacy-compatibility.yaml"
    if compat_path.exists():
        try:
            with open(compat_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


def es_nuevo_control_work_id(backlog_id: str) -> bool:
    """Verifica si un ID es un ID de trabajo del nuevo plano de control."""
    if not backlog_id:
        return False
    # Patron estandar: C2PRO-DEV-xx o similar
    if re.match(r"^C2PRO-[A-Z0-9-]+$", backlog_id):
        return True
    
    # También verificar si está listado en work-queue.yaml
    wq_path = BASE_DIR / ".c2pro" / "control" / "work-queue.yaml"
    if wq_path.exists():
        try:
            with open(wq_path, encoding="utf-8") as f:
                wq = yaml.safe_load(f) or {}
                for item in wq.get("items", []):
                    if item.get("work_id") == backlog_id:
                        return True
        except Exception:
            pass
    return False


def cargar_json(ruta: Path) -> dict:
    if not ruta.exists():
        return {}
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar_json(ruta: Path, data: dict) -> None:
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def cargar_yaml(ruta: Path) -> dict:
    if not ruta.exists():
        return {}
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def cargar_blackboard() -> dict:
    default = {
        "session_id": None,
        "objetivo_global": None,
        "estado_actual": "idle",
        "created_at": None,
        "updated_at": None,
        "role_assignment": {
            "planner": None,
            "builder": None,
            "qa": None,
            "reviewer": None,
            "security": None,
            "devops": None,
        },
        "tareas": [],
        "contexto_paso_anterior": "",
        "trazas_de_error": [],
        "reintentos": 0,
        "max_reintentos": 3,
        "backlog_sync": {
            "last_sync": None,
            "backlog_file": "C2PRO_MASTER_BACKLOG.md",
            "task_ids_en_sesion": [],
        },
    }
    if not BLACKBOARD_PATH.exists():
        return default
    data = cargar_json(BLACKBOARD_PATH)
    for key, val in default.items():
        if key not in data:
            data[key] = val
    if "role_assignment" not in data:
        data["role_assignment"] = default["role_assignment"]
    if "backlog_sync" not in data:
        data["backlog_sync"] = default["backlog_sync"]
    return data


def validar_backlog_ids(tareas: list[dict]) -> list[str]:
    """Valida que todas las tareas tengan backlog_id valido.

    Retorna lista de errores. Si vacia, todas las tareas son validas.

    Validaciones:
      - Cada tarea debe tener campo 'backlog_id'
      - backlog_id debe coincidir con el patron: ^TASK-[A-Z0-9-]+$
      - Ejemplos validos: TASK-1490, TASK-UNIFY-005, TASK-BCK-1155
    """
    errores = []

    for idx, tarea in enumerate(tareas):
        tarea_id = tarea.get("tarea_id", f"tarea_{idx}")

        # Validacion 1: Campo backlog_id obligatorio
        if "backlog_id" not in tarea:
            errores.append(
                f"Tarea {tarea_id}: Campo 'backlog_id' es OBLIGATORIO. "
                f"Toda tarea en blackboard.json debe vincularse a C2PRO_MASTER_BACKLOG.md"
            )
            continue

        backlog_id = tarea["backlog_id"]

        # Validacion 2: backlog_id no puede estar vacio
        if not backlog_id or not isinstance(backlog_id, str):
            errores.append(
                f"Tarea {tarea_id}: 'backlog_id' no puede estar vacio. "
                f"Debe ser string con formato TASK-[A-Z0-9-]+"
            )
            continue

        # Validacion 3: Patron obligatorio
        compat = cargar_legacy_compatibility()
        transition_mode = compat.get("transition_mode")
        if transition_mode == "dual_read_single_write_new_control" and es_nuevo_control_work_id(backlog_id):
            # En modo nuevo control, los IDs de trabajo nuevos son validos
            continue

        if not BACKLOG_ID_PATTERN.match(backlog_id):
            errores.append(
                f"Tarea {tarea_id}: 'backlog_id' invalido: '{backlog_id}'. "
                f"Patron requerido: ^TASK-[A-Z0-9-]+$ "
                f"(Ejemplos: TASK-1490, TASK-UNIFY-005, TASK-BCK-1155)"
            )

    return errores


def validar_task_schemas(tareas: list[dict]) -> list[str]:
    """Valida que todas las tareas cumplan con sus esquemas de rol (UNIFY-012).

    Esta funcion valida la estructura de salida de cada tarea contra el esquema
    JSON correspondiente a su rol. Complementa la validacion de backlog_id con
    validacion estructural profunda de todos los campos obligatorios y opcionales.

    Layer 1 of defense-in-depth: Schema validation at save time.

    Args:
        tareas: Lista de tareas del blackboard.json

    Returns:
        Lista de errores de validacion (vacia si todas las tareas son validas)

    Validaciones:
        - Cada tarea debe tener campo 'asignado_a' (rol)
        - El rol debe ser valido (uno de los 9 roles definidos)
        - La estructura de la tarea debe cumplir con el schema del rol
        - Campos obligatorios: tarea_id, backlog_id, tipo, descripcion, asignado_a, estado, resultado
        - Campos opcionales validados segun el schema del rol
    """
    errores = []

    # Skip validation if validator not available
    if validate_role_output is None:
        return errores

    for idx, tarea in enumerate(tareas):
        tarea_id = tarea.get("tarea_id", f"tarea_{idx}")

        # Validacion 1: Rol asignado obligatorio
        if "asignado_a" not in tarea:
            errores.append(
                f"Tarea {tarea_id}: Campo 'asignado_a' (rol) es OBLIGATORIO para validacion de schema"
            )
            continue

        rol = tarea["asignado_a"]

        # Validacion 2: Rol debe ser valido
        if rol not in VALID_ROLES:
            errores.append(
                f"Tarea {tarea_id}: Rol '{rol}' invalido. "
                f"Debe ser uno de: {', '.join(VALID_ROLES)}"
            )
            continue

        # Validacion 3: Estructura de tarea debe cumplir schema del rol
        try:
            is_valid, validation_errors = validate_role_output(rol, tarea, strict=True)

            if not is_valid:
                # Format validation errors for display
                error_msg = f"Tarea {tarea_id} (rol: {rol}): Schema validation FAILED:\n"
                for err in validation_errors:
                    error_msg += f"    - {err}\n"
                errores.append(error_msg.rstrip())

        except Exception as e:
            # Catch unexpected validation errors
            errores.append(
                f"Tarea {tarea_id} (rol: {rol}): Schema validation ERROR: {e!s}"
            )

    return errores


def validar_backlog_id_existe(backlog_id: str) -> tuple[bool, str]:
    """Verifica que un backlog_id existe en los archivos de backlog.

    Args:
        backlog_id: ID a verificar (e.g., "TASK-1490", "TASK-BCK-018")

    Returns:
        Tupla (existe: bool, archivo: str)
        - existe: True si el ID fue encontrado en algun backlog
        - archivo: Path del archivo donde se encontro, o mensaje de error
    """
    # Buscar en master backlog
    if MASTER_BACKLOG_PATH.exists():
        content = MASTER_BACKLOG_PATH.read_text(encoding="utf-8")
        # Pattern: | [x] | o | [ ] | seguido del task ID en backticks
        pattern = rf'\|\s*\[[x\s]\]\s*\|[^|]*\|\s*`{re.escape(backlog_id)}`\s*\|'
        if re.search(pattern, content, re.IGNORECASE):
            return True, str(MASTER_BACKLOG_PATH)

    # Buscar en category backlogs
    if CATEGORY_BACKLOGS_DIR.exists():
        for backlog_file in CATEGORY_BACKLOGS_DIR.glob("*.md"):
            content = backlog_file.read_text(encoding="utf-8")
            pattern = rf'\|\s*\[[x\s]\]\s*\|[^|]*\|\s*`{re.escape(backlog_id)}`\s*\|'
            if re.search(pattern, content, re.IGNORECASE):
                return True, str(backlog_file)

    return False, f"Backlog ID '{backlog_id}' no encontrado en ningun archivo de backlog"


def verificar_backlog_actualizado(backlog_id: str) -> tuple[bool, str]:
    """Verifica que un backlog_id esta marcado como completo [x] en los archivos.

    Args:
        backlog_id: ID a verificar (e.g., "TASK-1490", "TASK-BCK-018")

    Returns:
        Tupla (actualizado: bool, archivo_o_mensaje: str)
        - actualizado: True si el ID esta marcado [x] en algun backlog
        - archivo_o_mensaje: Path del archivo donde se encontro, o mensaje de error
    """
    # Buscar en master backlog
    if MASTER_BACKLOG_PATH.exists():
        content = MASTER_BACKLOG_PATH.read_text(encoding="utf-8")
        # Pattern: | [x] | seguido del task ID en backticks (completado)
        pattern = rf'\|\s*\[x\]\s*\|[^|]*\|\s*`{re.escape(backlog_id)}`\s*\|'
        if re.search(pattern, content, re.IGNORECASE):
            return True, str(MASTER_BACKLOG_PATH)

    # Buscar en category backlogs
    if CATEGORY_BACKLOGS_DIR.exists():
        for backlog_file in CATEGORY_BACKLOGS_DIR.glob("*.md"):
            content = backlog_file.read_text(encoding="utf-8")
            pattern = rf'\|\s*\[x\]\s*\|[^|]*\|\s*`{re.escape(backlog_id)}`\s*\|'
            if re.search(pattern, content, re.IGNORECASE):
                return True, str(backlog_file)

    return False, f"Backlog ID '{backlog_id}' no esta marcado como completo [x] en ningun archivo"


def validar_tarea_post_ejecucion(tarea: dict) -> tuple[bool, str]:
    """Hook de validacion POST-EJECUCION (UNIFY-010).

    Valida que una tarea completada tenga su backlog_id marcado como completo [x]
    en los archivos de backlog. Esto verifica que los agentes realmente actualizaron
    el backlog permanente despues de completar el trabajo.

    Args:
        tarea: Diccionario de tarea de blackboard.json

    Returns:
        Tupla (valido: bool, mensaje: str)
        - valido: True si el backlog fue actualizado correctamente
        - mensaje: Mensaje de exito o error detallado

    Validaciones:
        1. Tarea debe estar en estado 'completado'
        2. Tarea debe tener backlog_id valido
        3. En modo de compatibilidad de nuevo control, se valida contra el estado canonical .c2pro.
           Para tareas legadas, se valida que el backlog_id este marcado [x] en archivos de backlog.
        4. (Opcional) Verificar que tiene nota de implementacion
    """
    tarea_id = tarea.get("tarea_id", "UNKNOWN")
    estado = tarea.get("estado", "")
    backlog_id = tarea.get("backlog_id", "")

    # Validacion 1: Tarea debe estar completada
    if estado != "completado":
        return True, (
            f"[POST-EXEC VALIDATION SKIPPED] Tarea {tarea_id}: "
            f"Estado '{estado}' - validacion solo para tareas completadas"
        )

    # Validacion 2: Debe tener backlog_id
    if not backlog_id:
        return False, (
            f"[POST-EXEC VALIDATION FAILED] Tarea {tarea_id}: "
            f"Tarea completada pero sin backlog_id. "
            f"Esto no deberia ocurrir (pre-exec validation debio bloquearlo)."
        )

    # Validar si es nuevo control
    compat = cargar_legacy_compatibility()
    transition_mode = compat.get("transition_mode")
    es_nuevo = es_nuevo_control_work_id(backlog_id)

    if transition_mode == "dual_read_single_write_new_control" and es_nuevo:
        # En modo nuevo control, no requerimos escrituras en el Markdown heredado.
        # En su lugar, validamos contra el estado canonical de .c2pro
        wq_path = BASE_DIR / ".c2pro" / "control" / "work-queue.yaml"
        if not wq_path.exists():
            return False, f"[POST-EXEC VALIDATION FAILED] Tarea {tarea_id}: No existe .c2pro/control/work-queue.yaml"
            
        try:
            with open(wq_path, encoding="utf-8") as f:
                wq = yaml.safe_load(f) or {}
        except Exception as e:
            return False, f"[POST-EXEC VALIDATION FAILED] Tarea {tarea_id}: Error al cargar work-queue.yaml: {e}"
            
        items = wq.get("items", [])
        work_item = next((item for item in items if item.get("work_id") == backlog_id), None)
        if not work_item:
            return False, f"[POST-EXEC VALIDATION FAILED] Tarea {tarea_id}: El work_id '{backlog_id}' no existe en .c2pro/control/work-queue.yaml"
            
        # Validación exitosa contra el plano de control canonical
        return True, (
            f"[POST-EXEC VALIDATION OK] Tarea {tarea_id}: "
            f"work_id '{backlog_id}' validado exitosamente contra el plano de control canonical .c2pro"
        )

    # Validacion 3: backlog_id debe estar marcado [x] en archivos para tareas legadas
    actualizado, archivo_o_error = verificar_backlog_actualizado(backlog_id)
    if not actualizado:
        return False, (
            f"[POST-EXEC VALIDATION FAILED] Tarea {tarea_id}: "
            f"backlog_id '{backlog_id}' NO esta marcado como completo [x] en los archivos. "
            f"El agente completo la tarea en blackboard.json pero NO actualizo el backlog permanente. "
            f"ACCION REQUERIDA: Marca manualmente '{backlog_id}' como [x] en "
            f"C2PRO_MASTER_BACKLOG.md o el backlog de categoria correspondiente."
        )

    # Validacion exitosa para tareas legadas
    return True, (
        f"[POST-EXEC VALIDATION OK] Tarea {tarea_id}: "
        f"backlog_id '{backlog_id}' marcado [x] en {Path(archivo_o_error).name}"
    )


def validar_tarea_antes_ejecucion(tarea: dict) -> tuple[bool, str]:
    """Hook de validacion PRE-EJECUCION (UNIFY-009).

    Valida que una tarea tenga backlog_id valido y existente ANTES de ejecutarla.
    Esto previene que agentes trabajen en tareas sin trazabilidad al backlog permanente.

    Args:
        tarea: Diccionario de tarea de blackboard.json

    Returns:
        Tupla (valido: bool, mensaje: str)
        - valido: True si la tarea puede ejecutarse
        - mensaje: Mensaje de exito o error detallado

    Validaciones:
        1. Tarea debe tener campo 'backlog_id'
        2. backlog_id debe coincidir con patron ^TASK-[A-Z0-9-]+$ o ser ID de nuevo control
        3. backlog_id debe existir en C2PRO_MASTER_BACKLOG.md, backlogs/*.md o ser valido en .c2pro/control/work-queue.yaml
    """
    tarea_id = tarea.get("tarea_id", "UNKNOWN")

    # Validacion 1: Campo backlog_id obligatorio
    if "backlog_id" not in tarea:
        return False, (
            f"[PRE-EXEC VALIDATION FAILED] Tarea {tarea_id}: "
            f"Campo 'backlog_id' es OBLIGATORIO. "
            f"Toda tarea debe vincularse a C2PRO_MASTER_BACKLOG.md antes de ejecutarse."
        )

    backlog_id = tarea["backlog_id"]

    # Validacion 2: backlog_id no puede estar vacio
    if not backlog_id or not isinstance(backlog_id, str):
        return False, (
            f"[PRE-EXEC VALIDATION FAILED] Tarea {tarea_id}: "
            f"'backlog_id' no puede estar vacio. "
            f"Debe ser string con formato TASK-[A-Z0-9-]+"
        )

    # Validar si es nuevo control
    compat = cargar_legacy_compatibility()
    transition_mode = compat.get("transition_mode")
    es_nuevo = es_nuevo_control_work_id(backlog_id)

    if transition_mode == "dual_read_single_write_new_control" and es_nuevo:
        # Validar contra el estado canonical de .c2pro
        wq_path = BASE_DIR / ".c2pro" / "control" / "work-queue.yaml"
        if not wq_path.exists():
            return False, f"[PRE-EXEC VALIDATION FAILED] Tarea {tarea_id}: Modo '{transition_mode}' activo pero no existe .c2pro/control/work-queue.yaml"
            
        try:
            with open(wq_path, encoding="utf-8") as f:
                wq = yaml.safe_load(f) or {}
        except Exception as e:
            return False, f"[PRE-EXEC VALIDATION FAILED] Tarea {tarea_id}: Error al cargar work-queue.yaml: {e}"
            
        items = wq.get("items", [])
        work_item = next((item for item in items if item.get("work_id") == backlog_id), None)
        if not work_item:
            return False, f"[PRE-EXEC VALIDATION FAILED] Tarea {tarea_id}: El work_id '{backlog_id}' no existe en .c2pro/control/work-queue.yaml"
            
        # Verificar archivo de envelope de trabajo
        work_ref = work_item.get("work_ref")
        if work_ref:
            envelope_path = BASE_DIR / work_ref
        else:
            envelope_path = BASE_DIR / ".c2pro" / "work" / f"{backlog_id}.yaml"
            
        if not envelope_path.exists():
            return False, f"[PRE-EXEC VALIDATION FAILED] Tarea {tarea_id}: No existe el archivo de envelope de trabajo en '{envelope_path}'"
            
        try:
            with open(envelope_path, encoding="utf-8") as f:
                envelope = yaml.safe_load(f) or {}
        except Exception as e:
            return False, f"[PRE-EXEC VALIDATION FAILED] Tarea {tarea_id}: Error al cargar el envelope de trabajo '{envelope_path}': {e}"
            
        # Todo correcto para pre-ejecución en nuevo plano de control
        return True, (
            f"[PRE-EXEC VALIDATION OK] Tarea {tarea_id}: "
            f"work_id '{backlog_id}' verificado en .c2pro/control/work-queue.yaml and {envelope_path.name}"
        )

    # Validacion 3: Patron obligatorio para tareas legadas
    if not BACKLOG_ID_PATTERN.match(backlog_id):
        return False, (
            f"[PRE-EXEC VALIDATION FAILED] Tarea {tarea_id}: "
            f"'backlog_id' invalido: '{backlog_id}'. "
            f"Patron requerido: ^TASK-[A-Z0-9-]+$ "
            f"(Ejemplos: TASK-1490, TASK-UNIFY-009, TASK-BCK-018)"
        )

    # Validacion 4: backlog_id debe existir en archivos de backlog
    existe, archivo_o_error = validar_backlog_id_existe(backlog_id)
    if not existe:
        return False, (
            f"[PRE-EXEC VALIDATION FAILED] Tarea {tarea_id}: "
            f"backlog_id '{backlog_id}' no encontrado en ningun backlog. "
            f"Debes agregar esta tarea a C2PRO_MASTER_BACKLOG.md o un backlog de categoria "
            f"ANTES de ejecutarla. Esto asegura trazabilidad completa."
        )

    # Validacion exitosa para tareas legadas
    return True, (
        f"[PRE-EXEC VALIDATION OK] Tarea {tarea_id}: "
        f"backlog_id '{backlog_id}' verificado en {Path(archivo_o_error).name}"
    )


def guardar_blackboard(data: dict) -> None:
    """Guarda blackboard.json con validacion completa (UNIFY-012).

    Implementa defense-in-depth con 2 capas de validacion:
      1. Schema validation: Valida estructura de tareas contra schemas/{role}_output.json
      2. Backlog ID validation: Valida patron y presencia de backlog_id

    CRITICO: Todas las tareas DEBEN:
      - Cumplir con el schema JSON de su rol (tarea_id, backlog_id, tipo, descripcion, etc.)
      - Tener backlog_id valido que vincule a C2PRO_MASTER_BACKLOG.md

    Esto previene trabajo huerfano y asegura trazabilidad + consistencia completa.

    Raises:
        ValueError: Si alguna tarea tiene errores de schema o backlog_id
    """
    tareas = data.get("tareas", [])
    todos_errores = []

    # UNIFY-012: Layer 1 - Schema validation
    errores_schema = validar_task_schemas(tareas)
    if errores_schema:
        todos_errores.extend(errores_schema)

    # Layer 2 - Backlog ID validation (existing UNIFY-006)
    errores_backlog = validar_backlog_ids(tareas)
    if errores_backlog:
        todos_errores.extend(errores_backlog)

    # Si hay errores, no guardar y mostrar todos
    if todos_errores:
        error_msg = (
            f"\n{'='*70}\n"
            f"ERROR CRITICO: Validacion de Blackboard FALLO\n"
            f"{'='*70}\n"
            f"El blackboard.json NO se guardara hasta corregir estos errores:\n\n"
        )

        # Mostrar errores de schema (Layer 1)
        if errores_schema:
            error_msg += f"LAYER 1 - SCHEMA VALIDATION ({len(errores_schema)} errores):\n"
            for i, err in enumerate(errores_schema, 1):
                error_msg += f"  {i}. {err}\n"
            error_msg += "\n"

        # Mostrar errores de backlog_id (Layer 2)
        if errores_backlog:
            error_msg += f"LAYER 2 - BACKLOG ID VALIDATION ({len(errores_backlog)} errores):\n"
            for i, err in enumerate(errores_backlog, 1):
                error_msg += f"  {i}. {err}\n"
            error_msg += "\n"

        error_msg += (
            f"{'='*70}\n"
            f"RECORDATORIO - Defense-in-Depth (2 capas):\n"
            f"  Layer 1 - Schema Validation:\n"
            f"    - Todas las tareas deben cumplir schemas/{{role}}_output.json\n"
            f"    - Campos obligatorios: tarea_id, backlog_id, tipo, descripcion, etc.\n"
            f"  Layer 2 - Backlog ID Validation:\n"
            f"    - El backlog_id debe existir en C2PRO_MASTER_BACKLOG.md\n"
            f"    - Patron valido: ^TASK-[A-Z0-9-]+$\n"
            f"    - Ejemplos: TASK-1490, TASK-UNIFY-012, TASK-BCK-1155\n"
            f"{'='*70}\n"
        )

        _log_trace(
            "SUPERVISOR",
            f"VALIDACION FALLO: {len(errores_schema)} schema errors, "
            f"{len(errores_backlog)} backlog_id errors"
        )
        raise ValueError(error_msg)

    # Validacion exitosa - guardar
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    guardar_json(BLACKBOARD_PATH, data)

    # Log exitoso con conteo de tareas validadas
    num_tareas = len(tareas)
    _log_trace(
        "SUPERVISOR",
        f"blackboard.json actualizado. Estado: {data['estado_actual']}. "
        f"Tareas validadas: {num_tareas}"
    )


def cargar_modelos() -> dict:
    return cargar_yaml(MODELS_PATH)


def cargar_session_config() -> dict:
    """Carga o crea la configuracion de sesion (mapeo rol -> modelo)."""
    if SESSION_CONFIG_PATH.exists():
        return cargar_json(SESSION_CONFIG_PATH)
    default_config = {
        "roles": {
            "planner": "claude_code",
            "builder": "codex_cli",
            "qa": "gemini_cli",
            "reviewer": "claude_code",
            "security": "claude_code",
            "devops": "codex_cli",
        },
        "modo": "interactivo",
        "auto_aprobar_comandos": False,
    }
    guardar_json(SESSION_CONFIG_PATH, default_config)
    return default_config


def obtener_modelo_para_rol(rol: str) -> dict | None:
    """Devuelve la configuracion del modelo asignado a un rol."""
    session_config = cargar_session_config()
    modelos = cargar_modelos()
    rol_asignado = session_config.get("roles", {}).get(rol)
    if not rol_asignado:
        return None
    return modelos.get("models", {}).get(rol_asignado)


def construir_comando(modelo_config: dict, profile_path: Path, prompt: str) -> list[str]:
    """Construye el comando real para invocar el CLI."""
    cli_cmd = modelo_config.get("cli_command", "")
    if not cli_cmd:
        raise ValueError("Modelo sin cli_command configurado")

    formato = modelo_config.get("formato_invocacion", "")
    if formato:
        cmd_str = formato.format(
            cli=cli_cmd,
            profile=str(profile_path),
            prompt=prompt,
        )
        return cmd_str

    flags = modelo_config.get("flags_sistema", [])
    soporta_system_prompt = modelo_config.get("soporta_system_prompt", False)
    soporta_prompt_file = modelo_config.get("soporta_prompt_file", False)

    if soporta_system_prompt:
        cmd = [cli_cmd]
        cmd.extend(flags)
        cmd.extend(["--system-prompt", str(profile_path)])
        cmd.extend(["--prompt", prompt])
        return cmd

    cmd = [cli_cmd]
    cmd.extend(flags)
    cmd.extend(["--prompt", prompt])
    return cmd


def invocar_rol(rol: str, prompt: str, auto: bool = False) -> dict:
    """Invoca un rol mediante su modelo asignado.

    Si auto=True, ejecuta el comando via subprocess.
    Si auto=False, muestra el comando para que el usuario lo ejecute manualmente.
    """
    modelo_config = obtener_modelo_para_rol(rol)
    if not modelo_config:
        session_config = cargar_session_config()
        modelo_id = session_config.get("roles", {}).get(rol, "no configurado")
        return {
            "success": False,
            "error": f"No hay modelo configurado para rol '{rol}' (actual: {modelo_id})",
            "comando": None,
        }

    profile_path = ROLES_DIR / f"role_{rol}.md"
    if not profile_path.exists():
        return {
            "success": False,
            "error": f"Perfil de rol no encontrado: {profile_path}",
            "comando": None,
        }

    cli_cmd = modelo_config["cli_command"]
    _log_trace("SUPERVISOR", f"Invocando rol '{rol}' via {cli_cmd} ({modelo_config.get('vendor', 'unknown')})")

    if auto:
        cmd = construir_comando(modelo_config, profile_path, prompt)
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)

        _log_trace("SUPERVISOR", f"Ejecutando: {' '.join(cmd[:5])}...")
        print(f"\n[SUPERVISOR] Ejecutando: {cli_cmd} para rol '{rol}'")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=modelo_config.get("timeout_seg", 300),
                cwd=str(BASE_DIR),
            )
            output = result.stdout
            if result.returncode != 0:
                output += f"\nSTDERR: {result.stderr}"

            _log_trace("SUPERVISOR", f"Rol '{rol}' completado. Exit code: {result.returncode}")
            return {
                "success": result.returncode == 0,
                "output": output,
                "comando": " ".join(cmd) if isinstance(cmd, list) else cmd,
            }
        except subprocess.TimeoutExpired:
            _log_trace("SUPERVISOR", f"Rol '{rol}' TIMEOUT despues de {modelo_config.get('timeout_seg', 300)}s")
            return {
                "success": False,
                "error": f"Timeout despues de {modelo_config.get('timeout_seg', 300)}s",
                "comando": " ".join(cmd) if isinstance(cmd, list) else cmd,
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"CLI '{cli_cmd}' no encontrado en PATH. Instalalo primero.",
                "comando": " ".join(cmd) if isinstance(cmd, list) else cmd,
            }
    else:
        modo_interactivo = f"""
{'='*70}
[SUPERVISOR] MODO INTERACTIVO — Ejecuta manualmente en una terminal:
{'='*70}

  1. Abre una terminal con: {cli_cmd}
  2. Carga el perfil: roles/role_{rol}.md
  3. Ejecuta el prompt:
     "{prompt}"
  4. Cuando termine, presiona Enter aqui para continuar.

{'='*70}
"""
        print(modo_interactivo)
        return {
            "success": True,
            "output": "Esperando confirmacion del usuario...",
            "comando": f"{cli_cmd} --system-prompt roles/role_{rol}.md --prompt \"{prompt[:80]}...\"",
        }


def iniciar_sesion(objetivo: str) -> dict:
    """Crea una nueva sesion de trabajo."""
    bb = cargar_blackboard()
    bb["session_id"] = f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    bb["objetivo_global"] = objetivo
    bb["estado_actual"] = "planificacion"
    bb["created_at"] = datetime.now(timezone.utc).isoformat()
    bb["tareas"] = []
    bb["contexto_paso_anterior"] = ""
    bb["trazas_de_error"] = []
    bb["reintentos"] = 0
    guardar_blackboard(bb)
    _log_trace("SUPERVISOR", f"Sesion iniciada: {bb['session_id']} - Objetivo: {objetivo}")
    return bb


def siguiente_tarea(bb: dict, rol: str) -> dict | None:
    """Busca la siguiente tarea pendiente para un rol especifico."""
    for tarea in bb.get("tareas", []):
        if tarea.get("asignado_a") == rol and tarea.get("estado") == "pendiente":
            return tarea
    return None


def tareas_pendientes_por_rol(bb: dict, rol: str) -> list[dict]:
    """Devuelve todas las tareas pendientes de un rol."""
    return [t for t in bb.get("tareas", []) if t.get("asignado_a") == rol and t.get("estado") == "pendiente"]


def ejecutar_ciclo(objetivo: str, modo: str = "interactivo") -> None:
    """Ejecuta el ciclo completo: Planificar -> Implementar -> Revisar.

    modos:
      - interactivo: muestra comandos, usuario ejecuta manualmente (default)
      - auto: ejecuta subprocess directamente (requiere CLIs instalados)
    """
    auto = modo == "auto"
    bb = iniciar_sesion(objetivo)
    session_config = cargar_session_config()

    print(f"\n{'='*60}")
    print(f"[SUPERVISOR] Ciclo iniciado: {objetivo}")
    print(f"[SUPERVISOR] Modo: {modo}")
    print(f"[SUPERVISOR] Session: {bb['session_id']}")
    print("[SUPERVISOR] Roles configurados:")
    for rol, modelo_id in session_config.get("roles", {}).items():
        print(f"  {rol}: {modelo_id}")
    print(f"{'='*60}")

    # Paso 1: Planificacion
    print(f"\n{'='*60}")
    print("PASO 1: PLANIFICACION")
    print(f"{'='*60}")
    resultado = invocar_rol(
        "planner",
        f"Objetivo: {objetivo}. Lee C2PRO_MASTER_BACKLOG.md y blackboard.json. Crea el plan de tareas en blackboard.json.",
        auto=auto,
    )
    if not resultado["success"]:
        error_msg = resultado.get('error', 'Desconocido')
        output_msg = resultado.get('output', '')
        cmd_used = resultado.get('comando', '')
        print(f"ERROR: {error_msg}")
        if output_msg:
            print(f"OUTPUT: {output_msg[:500]}")
        if cmd_used:
            print(f"COMANDO: {cmd_used}")
        return
    if not auto:
        input("\n[SUPERVISOR] Presiona Enter cuando el Planner haya terminado...")

    bb = cargar_blackboard()
    if not bb.get("tareas"):
        print("\n[SUPERVISOR] El Planner no creo tareas. Verifica su output.")
        return

    print(f"\n[SUPERVISOR] Plan creado con {len(bb['tareas'])} tareas:")
    for t in bb["tareas"]:
        print(f"  [{t['tarea_id']}] ({t['asignado_a']}) {t['descripcion'][:60]}...")

    # Paso 2+: Ejecucion secuencial por rol
    _ejecutar_secuencial(bb, auto=auto)


def _ejecutar_secuencial(bb: dict, auto: bool = False) -> None:
    """Ejecuta tareas secuencialmente por rol: builder -> qa -> reviewer -> loop."""
    max_reintentos = bb.get("max_reintentos", 3)
    orden_roles = ["backend", "frontend", "ai", "infra", "qa", "reviewer"]

    while True:
        alguna_ejecutada = False

        for rol in orden_roles:
            tareas = tareas_pendientes_por_rol(bb, rol)
            if not tareas:
                continue

            for tarea in tareas:
                print(f"\n{'='*60}")
                print(f"EJECUTANDO: [{tarea['tarea_id']}] Rol: {rol}")
                print(f"Descripcion: {tarea['descripcion']}")
                print(f"{'='*60}")

                # UNIFY-009: Pre-execution validation hook
                valido, mensaje_validacion = validar_tarea_antes_ejecucion(tarea)
                _log_trace("SUPERVISOR", mensaje_validacion)

                if not valido:
                    print(f"\n[ERROR] {mensaje_validacion}")
                    print(f"\n[SUPERVISOR] Tarea {tarea['tarea_id']} BLOQUEADA por validacion.")
                    print(f"[SUPERVISOR] Agrega '{tarea.get('backlog_id', 'MISSING')}' a un backlog antes de continuar.")
                    tarea["estado"] = "fallido"
                    bb["trazas_de_error"].append({
                        "tarea_id": tarea["tarea_id"],
                        "tipo": "validacion_pre_ejecucion",
                        "severidad": "critica",
                        "mensaje": mensaje_validacion,
                    })
                    guardar_blackboard(bb)
                    continue

                print(f"[OK] {mensaje_validacion}")

                contexto = bb.get("contexto_paso_anterior", "")
                errores = bb.get("trazas_de_error", [])
                error_contexto = ""
                if errores:
                    errores_tarea = [e for e in errores if e.get("tarea_id") == tarea["tarea_id"]]
                    if errores_tarea:
                        error_contexto = "\nErrores previos a corregir:\n"
                        for err in errores_tarea:
                            error_contexto += f"  - {err.get('mensaje', '')}\n"

                prompt = (
                    f"Lee blackboard.json. Ejecuta la tarea {tarea['tarea_id']}: "
                    f"{tarea['descripcion']}. "
                    f"Criterio de exito: {tarea.get('criterio_done', 'N/A')}. "
                    f"Actualiza blackboard.json al terminar.{error_contexto}"
                )

                resultado = invocar_rol(rol, prompt, auto=auto)
                if not resultado["success"]:
                    print(f"ERROR: {resultado.get('error', 'Desconocido')}")
                    tarea["estado"] = "fallido"
                    bb["trazas_de_error"].append({
                        "tarea_id": tarea["tarea_id"],
                        "tipo": "ejecucion",
                        "severidad": "alta",
                        "mensaje": resultado.get("error", "Error desconocido"),
                    })
                    guardar_blackboard(bb)
                    continue

                if not auto:
                    input(f"\n[SUPERVISOR] Presiona Enter cuando {rol} haya terminado la tarea {tarea['tarea_id']}...")

                # Reload blackboard to get updated state
                bb = cargar_blackboard()
                alguna_ejecutada = True

                # UNIFY-010: Post-execution validation hook
                # Find the task in the reloaded blackboard to check its updated state
                tarea_actualizada = next(
                    (t for t in bb.get("tareas", []) if t.get("tarea_id") == tarea["tarea_id"]),
                    None
                )

                if tarea_actualizada:
                    valido, mensaje_validacion = validar_tarea_post_ejecucion(tarea_actualizada)
                    _log_trace("SUPERVISOR", mensaje_validacion)

                    if not valido:
                        print(f"\n[WARNING] {mensaje_validacion}")
                        print(f"[SUPERVISOR] Tarea {tarea['tarea_id']} completo en blackboard pero backlog NO actualizado.")

                        # Add warning trace (not critical - task completed successfully)
                        bb["trazas_de_error"].append({
                            "tarea_id": tarea["tarea_id"],
                            "tipo": "validacion_post_ejecucion",
                            "severidad": "media",
                            "mensaje": mensaje_validacion,
                        })
                        guardar_blackboard(bb)
                    else:
                        print(f"[OK] {mensaje_validacion}")

        # Verificar reintentos
        tareas_fallidas = [t for t in bb.get("tareas", []) if t.get("estado") == "fallido"]
        if tareas_fallidas and bb.get("reintentos", 0) < max_reintentos:
            bb["reintentos"] = bb.get("reintentos", 0) + 1
            for t in tareas_fallidas:
                t["estado"] = "pendiente"
            guardar_blackboard(bb)
            print(f"\n[SUPERVISOR] Reintento {bb['reintentos']}/{max_reintentos}. Reenviando tareas fallidas.")
            continue
        elif tareas_fallidas:
            print(f"\n[SUPERVISOR] MAX REINTENTOS ALCANZADO ({max_reintentos}). Escalando a humano.")
            bb["estado_actual"] = "fallido"
            guardar_blackboard(bb)
            return

        # Verificar completado
        tareas_pendientes = [t for t in bb.get("tareas", []) if t.get("estado") in ("pendiente", "en_progreso")]
        if not tareas_pendientes:
            bb["estado_actual"] = "completado"
            guardar_blackboard(bb)
            print(f"\n{'='*60}")
            print("[SUPERVISOR] TODAS LAS TAREAS COMPLETADAS")
            print(f"[SUPERVISOR] Session finalizada: {bb['session_id']}")
            print(f"{'='*60}")
            return

        if not alguna_ejecutada:
            print("\n[SUPERVISOR] No se ejecuto ninguna tarea. Verifica asignaciones.")
            return

        bb = cargar_blackboard()


def mostrar_estado() -> None:
    """Muestra el estado actual del blackboard."""
    bb = cargar_blackboard()
    if not bb.get("session_id"):
        print("No hay sesion activa.")
        return

    print(f"\n{'='*60}")
    print(f"SESION: {bb['session_id']}")
    print(f"OBJETIVO: {bb['objetivo_global']}")
    print(f"ESTADO: {bb['estado_actual']}")
    print(f"REINTENTOS: {bb.get('reintentos', 0)}/{bb.get('max_reintentos', 3)}")
    print(f"{'='*60}")

    if bb.get("tareas"):
        print(f"\nTAREAS ({len(bb['tareas'])}):")
        for t in bb["tareas"]:
            icono = {"pendiente": "○", "en_progreso": "◐", "completado": "●", "fallido": "✗"}.get(t.get("estado", "?"), "?")
            print(f"  {icono} [{t['tarea_id']}] ({t.get('asignado_a', '?')}) {t['descripcion'][:70]}")
    print()


def _log_trace(agente: str, mensaje: str) -> None:
    """Registra una traza de ejecucion en el log."""
    LOGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    linea = f"[{timestamp}] [{agente}] {mensaje}\n"
    with open(LOGS_PATH, "a", encoding="utf-8") as f:
        f.write(linea)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="C2Pro Multi-Agent Orchestration Supervisor",
        epilog="""
Examples:
  %(prog)s "Add user authentication to API"
      Execute task with automatic agent orchestration

  %(prog)s "Deploy to staging" --modo interactivo
      Show commands without executing (interactive mode)

  %(prog)s --estado
      Display current blackboard.json state

  %(prog)s --init
      Show session configuration (core/session_config.json)

Documentation:
  Complete Guide:   docs/workflows/AGENT_ORCHESTRATION_GUIDE.md
  Architecture:     AGENT_STRUCTURE_UNIFICATION_ANALYSIS.md

Requirements:
  All tasks MUST have valid backlog_id (pattern: TASK-XXX-YYY)
  linking to C2PRO_MASTER_BACKLOG.md or backlogs/*.md

Validation (4 Layers):
  1. Schema:   JSON Schema Draft-07 (schemas/{role}_output.json)
  2. Runtime:  backlog_id pattern (^TASK-[A-Z0-9-]+$)
  3. Pre-Exec: backlog_id exists in files
  4. Post-Exec: backlog updated after completion
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "objetivo",
        nargs="?",
        help="Task objective or user request (e.g., 'Add login endpoint')"
    )
    parser.add_argument(
        "--modo",
        choices=["interactivo", "auto"],
        default="interactivo",
        help="Execution mode: 'interactivo' shows commands without executing, 'auto' executes subprocesses"
    )
    parser.add_argument(
        "--estado",
        action="store_true",
        help="Display current blackboard.json state and active tasks"
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Show session configuration from core/session_config.json"
    )

    args = parser.parse_args()

    if args.init:
        config = cargar_session_config()
        print("Configuracion de sesion actual:")
        print(json.dumps(config, indent=2, ensure_ascii=False))
        print("\nPara cambiar asignaciones, edita: core/session_config.json")
        sys.exit(0)

    if args.estado:
        mostrar_estado()
        sys.exit(0)

    if not args.objetivo:
        print("C2Pro Multi-Agent Orchestration Supervisor")
        print("=" * 60)
        print("\nUsage:")
        print("  python core/supervisor.py <objetivo> [--modo interactivo|auto]")
        print("  python core/supervisor.py --estado")
        print("  python core/supervisor.py --init")
        print("  python core/supervisor.py --help")
        print("\nExamples:")
        print("  python core/supervisor.py 'Add user authentication to API'")
        print("  python core/supervisor.py 'Deploy to staging' --modo auto")
        print("\nDocumentation:")
        print("  Complete Guide: docs/workflows/AGENT_ORCHESTRATION_GUIDE.md")
        print("  Architecture:   AGENT_STRUCTURE_UNIFICATION_ANALYSIS.md")
        print("\nRoles Available (9):")
        print("  planner, backend, frontend, ai, infra, qa, reviewer, security, devops")
        print("\nRequirements:")
        print("  • All tasks MUST have valid backlog_id (pattern: TASK-XXX-YYY)")
        print("  • Backlog_id must exist in C2PRO_MASTER_BACKLOG.md or backlogs/*.md")
        print("  • 4-layer validation enforced (Schema, Runtime, Pre-Exec, Post-Exec)")
        print("\nFor detailed help, run: python core/supervisor.py --help")
        print("=" * 60)
        sys.exit(1)

    ejecutar_ciclo(args.objetivo, modo=args.modo)
