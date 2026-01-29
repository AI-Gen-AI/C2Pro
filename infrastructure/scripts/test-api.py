#!/usr/bin/env python3
"""
C2Pro - API Testing Script

Script rápido para probar que la API funciona correctamente.
"""

import requests
import json
import sys
from typing import Optional

API_URL = "http://localhost:8000"


def print_header(message: str):
    """Print formatted header."""
    print("\n" + "="*60)
    print(f"  {message}")
    print("="*60 + "\n")


def print_success(message: str):
    """Print success message."""
    print(f"✅ {message}")


def print_error(message: str):
    """Print error message."""
    print(f"❌ {message}")


def print_info(message: str):
    """Print info message."""
    print(f"ℹ️  {message}")


def test_health() -> bool:
    """Test health endpoint."""
    print_header("Test 1: Health Check")

    try:
        response = requests.get(f"{API_URL}/health", timeout=5)

        if response.status_code == 200:
            data = response.json()
            print_success(f"API está corriendo")
            print_info(f"Versión: {data.get('version')}")
            print_info(f"Environment: {data.get('environment')}")
            return True
        else:
            print_error(f"Status code inesperado: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print_error("No se pudo conectar a la API")
        print_info("Asegúrate de que el servidor esté corriendo en http://localhost:8000")
        return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False


def test_register() -> Optional[dict]:
    """Test user registration."""
    print_header("Test 2: Registro de Usuario")

    user_data = {
        "company_name": "Empresa de Prueba",
        "email": f"test_{id(object())}@ejemplo.com",  # Email único
        "password": "TestPassword123!",
        "password_confirm": "TestPassword123!",
        "first_name": "Usuario",
        "last_name": "Prueba",
        "accept_terms": True
    }

    try:
        response = requests.post(
            f"{API_URL}/api/v1/auth/register",
            json=user_data,
            timeout=10
        )

        if response.status_code == 201:
            data = response.json()
            print_success("Usuario registrado correctamente")
            print_info(f"Email: {data['user']['email']}")
            print_info(f"Empresa: {data['tenant']['name']}")
            print_info(f"Token obtenido: {data['tokens']['access_token'][:20]}...")
            return data
        elif response.status_code == 409:
            print_error("Email ya existe (esto es normal si ya corriste el test)")
            return None
        else:
            print_error(f"Error al registrar: {response.status_code}")
            print_info(f"Respuesta: {response.text}")
            return None

    except Exception as e:
        print_error(f"Error: {e}")
        return None


def test_login(email: str, password: str) -> Optional[str]:
    """Test user login."""
    print_header("Test 3: Login")

    login_data = {
        "email": email,
        "password": password
    }

    try:
        response = requests.post(
            f"{API_URL}/api/v1/auth/login",
            json=login_data,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            access_token = data['tokens']['access_token']
            print_success("Login exitoso")
            print_info(f"Token: {access_token[:20]}...")
            return access_token
        else:
            print_error(f"Error al hacer login: {response.status_code}")
            return None

    except Exception as e:
        print_error(f"Error: {e}")
        return None


def test_me(token: str) -> bool:
    """Test /me endpoint."""
    print_header("Test 4: Obtener Usuario Actual")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{API_URL}/api/v1/auth/me",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print_success("Usuario obtenido correctamente")
            print_info(f"Email: {data['user']['email']}")
            print_info(f"Nombre: {data['user']['full_name']}")
            print_info(f"Rol: {data['user']['role']}")
            return True
        else:
            print_error(f"Error: {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Error: {e}")
        return False


def test_create_project(token: str) -> Optional[str]:
    """Test project creation."""
    print_header("Test 5: Crear Proyecto")

    headers = {"Authorization": f"Bearer {token}"}
    project_data = {
        "name": "Proyecto de Prueba API",
        "description": "Proyecto creado por el script de testing",
        "code": f"TEST-{id(object())}",
        "project_type": "construction",
        "estimated_budget": 150000.00,
        "currency": "EUR"
    }

    try:
        response = requests.post(
            f"{API_URL}/api/v1/projects",
            json=project_data,
            headers=headers,
            timeout=10
        )

        if response.status_code == 201:
            data = response.json()
            project_id = data['id']
            print_success("Proyecto creado correctamente")
            print_info(f"ID: {project_id}")
            print_info(f"Nombre: {data['name']}")
            print_info(f"Estado: {data['status']}")
            return project_id
        else:
            print_error(f"Error al crear proyecto: {response.status_code}")
            print_info(f"Respuesta: {response.text}")
            return None

    except Exception as e:
        print_error(f"Error: {e}")
        return None


def test_list_projects(token: str) -> bool:
    """Test project listing."""
    print_header("Test 6: Listar Proyectos")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{API_URL}/api/v1/projects",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print_success("Proyectos obtenidos correctamente")
            print_info(f"Total: {data['total']}")
            print_info(f"Página: {data['page']}/{data['total_pages']}")
            print_info(f"Proyectos en esta página: {len(data['items'])}")
            return True
        else:
            print_error(f"Error: {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Error: {e}")
        return False


def test_get_project(token: str, project_id: str) -> bool:
    """Test get project details."""
    print_header("Test 7: Obtener Detalles de Proyecto")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{API_URL}/api/v1/projects/{project_id}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print_success("Proyecto obtenido correctamente")
            print_info(f"Nombre: {data['name']}")
            print_info(f"Tipo: {data['project_type']}")
            print_info(f"Presupuesto: {data['estimated_budget']} {data['currency']}")
            return True
        else:
            print_error(f"Error: {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  C2Pro API - Testing Suite")
    print("="*60)

    results = {
        "passed": 0,
        "failed": 0,
        "total": 7
    }

    # Test 1: Health
    if test_health():
        results["passed"] += 1
    else:
        results["failed"] += 1
        print_error("\nLa API no está disponible. Asegúrate de iniciarla primero.")
        sys.exit(1)

    # Test 2: Register
    register_data = test_register()
    if register_data:
        results["passed"] += 1
        email = register_data['user']['email']
        password = "TestPassword123!"
        token = register_data['tokens']['access_token']
    else:
        results["failed"] += 1
        # Try with a default user for remaining tests
        email = "test@ejemplo.com"
        password = "TestPassword123!"
        token = None

    # Test 3: Login
    if not token:
        token = test_login(email, password)

    if token:
        results["passed"] += 1
    else:
        results["failed"] += 1
        print_error("\nNo se pudo obtener token. Remaining tests se omiten.")
        print_summary(results)
        sys.exit(1)

    # Test 4: Me
    if test_me(token):
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Test 5: Create Project
    project_id = test_create_project(token)
    if project_id:
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Test 6: List Projects
    if test_list_projects(token):
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Test 7: Get Project (if created)
    if project_id:
        if test_get_project(token, project_id):
            results["passed"] += 1
        else:
            results["failed"] += 1
    else:
        print_info("\nTest 7 omitido (no se creó proyecto)")
        results["failed"] += 1

    # Summary
    print_summary(results)

    # Exit code
    sys.exit(0 if results["failed"] == 0 else 1)


def print_summary(results: dict):
    """Print test summary."""
    print_header("Resumen de Tests")

    total = results["total"]
    passed = results["passed"]
    failed = results["failed"]

    print(f"Total:   {total}")
    print(f"Pasados: {passed} ✅")
    print(f"Fallidos: {failed} ❌")
    print()

    percentage = (passed / total) * 100

    if percentage == 100:
        print("🎉 ¡Todos los tests pasaron! La API está funcionando perfectamente.")
    elif percentage >= 70:
        print("⚠️  La mayoría de tests pasaron. Revisa los errores.")
    else:
        print("❌ Varios tests fallaron. Revisa la configuración.")

    print()


if __name__ == "__main__":
    main()
