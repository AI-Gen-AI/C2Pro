"""Schema validation utility for role outputs (UNIFY-011).

This module provides utilities to validate role outputs against their
corresponding JSON schemas. All role schemas extend base_output.json.

Usage:
    from schemas.validator import validate_role_output

    role_output = {
        "tarea_id": "T001",
        "backlog_id": "TASK-1490",
        "tipo": "backend",
        "asignado_a": "backend",
        "estado": "completado",
        ...
    }

    is_valid, errors = validate_role_output("backend", role_output)
    if not is_valid:
        for error in errors:
            print(f"Validation error: {error}")
"""
import json
from pathlib import Path
from typing import Any

# Third-party imports
try:
    from jsonschema import Draft7Validator, RefResolver, ValidationError
except ImportError:
    raise ImportError(
        "jsonschema library is required. Install with: pip install jsonschema"
    )


# Schema directory
SCHEMAS_DIR = Path(__file__).parent


# Valid roles
VALID_ROLES = [
    "planner",
    "backend",
    "frontend",
    "ai",
    "infra",
    "qa",
    "reviewer",
    "security",
    "devops",
]


def load_schema(role: str) -> dict[str, Any]:
    """Load JSON schema for a specific role.

    Args:
        role: Role name (planner, backend, frontend, ai, infra, qa, reviewer, security, devops)

    Returns:
        Parsed JSON schema dictionary

    Raises:
        ValueError: If role is invalid
        FileNotFoundError: If schema file doesn't exist
        json.JSONDecodeError: If schema file is invalid JSON
    """
    if role not in VALID_ROLES:
        raise ValueError(
            f"Invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}"
        )

    schema_path = SCHEMAS_DIR / f"{role}_output.json"

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_base_schema() -> dict[str, Any]:
    """Load the base output schema that all role schemas extend.

    Returns:
        Parsed base_output.json schema

    Raises:
        FileNotFoundError: If base schema doesn't exist
        json.JSONDecodeError: If base schema is invalid JSON
    """
    base_path = SCHEMAS_DIR / "base_output.json"

    if not base_path.exists():
        raise FileNotFoundError(f"Base schema not found: {base_path}")

    with open(base_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_ref_resolver() -> RefResolver:
    """Create a RefResolver for handling $ref in schemas.

    This resolver allows schemas to reference base_output.json using:
        {"$ref": "base_output.json"}

    Returns:
        Configured RefResolver for schemas directory
    """
    # Base URI for schema resolution
    base_uri = SCHEMAS_DIR.as_uri() + "/"

    # Store for pre-loaded schemas (for faster resolution)
    store = {}

    # Pre-load base schema
    try:
        base_schema = load_base_schema()
        store[f"{base_uri}base_output.json"] = base_schema
    except (FileNotFoundError, json.JSONDecodeError):
        # Base schema will be loaded on-demand if not pre-loaded
        pass

    return RefResolver(base_uri, None, store=store)


def validate_role_output(
    role: str, data: dict[str, Any], strict: bool = True
) -> tuple[bool, list[str]]:
    """Validate role output data against its JSON schema.

    Args:
        role: Role name (planner, backend, frontend, ai, infra, qa, reviewer, security, devops)
        data: Role output data to validate
        strict: If True, all validation errors are collected. If False, stops at first error.

    Returns:
        Tuple of (is_valid: bool, errors: list[str])
        - is_valid: True if data passes all validation
        - errors: List of validation error messages (empty if valid)

    Example:
        >>> output = {"tarea_id": "T001", "backlog_id": "TASK-1490", ...}
        >>> is_valid, errors = validate_role_output("backend", output)
        >>> if not is_valid:
        ...     print("Validation failed:")
        ...     for error in errors:
        ...         print(f"  - {error}")
    """
    errors: list[str] = []

    try:
        # Load schema for this role
        schema = load_schema(role)

        # Create resolver for $ref handling
        resolver = create_ref_resolver()

        # Create validator
        validator = Draft7Validator(schema, resolver=resolver)

        # Validate and collect errors
        if strict:
            # Collect ALL validation errors
            validation_errors = list(validator.iter_errors(data))
            for err in validation_errors:
                # Build error path (e.g., "resultado.mensaje")
                path = ".".join(str(p) for p in err.path) if err.path else "root"

                # Format error message
                error_msg = f"[{path}] {err.message}"

                # Add validator type if helpful
                if err.validator != "required" and err.validator != "type":
                    error_msg += f" (validator: {err.validator})"

                errors.append(error_msg)
        else:
            # Stop at first error (faster)
            try:
                validator.validate(data)
            except ValidationError as err:
                path = ".".join(str(p) for p in err.path) if err.path else "root"
                errors.append(f"[{path}] {err.message}")

        return (len(errors) == 0, errors)

    except ValueError as e:
        # Invalid role
        return (False, [f"Invalid role: {e}"])

    except FileNotFoundError as e:
        # Schema file not found
        return (False, [f"Schema not found: {e}"])

    except json.JSONDecodeError as e:
        # Invalid schema JSON
        return (False, [f"Invalid schema JSON: {e}"])

    except Exception as e:
        # Unexpected error
        return (False, [f"Unexpected validation error: {e}"])


def validate_role_output_raises(role: str, data: dict[str, Any]) -> None:
    """Validate role output and raise exception on failure.

    This is a convenience wrapper around validate_role_output() that raises
    an exception instead of returning a tuple.

    Args:
        role: Role name
        data: Role output data to validate

    Raises:
        ValidationError: If validation fails, with all errors in the message

    Example:
        >>> try:
        ...     validate_role_output_raises("backend", invalid_output)
        ... except ValidationError as e:
        ...     print(f"Validation failed: {e}")
    """
    is_valid, errors = validate_role_output(role, data, strict=True)

    if not is_valid:
        error_msg = f"Role output validation failed for '{role}':\n"
        error_msg += "\n".join(f"  - {err}" for err in errors)
        raise ValidationError(error_msg)


def get_role_schema_path(role: str) -> Path:
    """Get the file path for a role's output schema.

    Args:
        role: Role name

    Returns:
        Path to the role's schema file

    Raises:
        ValueError: If role is invalid
    """
    if role not in VALID_ROLES:
        raise ValueError(
            f"Invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}"
        )

    return SCHEMAS_DIR / f"{role}_output.json"


def list_available_schemas() -> list[str]:
    """List all available role schemas.

    Returns:
        List of role names that have schemas defined
    """
    available = []
    for role in VALID_ROLES:
        schema_path = SCHEMAS_DIR / f"{role}_output.json"
        if schema_path.exists():
            available.append(role)
    return available


if __name__ == "__main__":
    # CLI usage for quick testing
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m schemas.validator <role> <json_file>")
        print(f"Available roles: {', '.join(VALID_ROLES)}")
        print(f"Available schemas: {', '.join(list_available_schemas())}")
        sys.exit(1)

    role = sys.argv[1]
    json_file = sys.argv[2]

    # Load data from file
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate
    is_valid, errors = validate_role_output(role, data)

    if is_valid:
        print(f"✅ Validation passed for role '{role}'")
        sys.exit(0)
    else:
        print(f"❌ Validation failed for role '{role}':")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
