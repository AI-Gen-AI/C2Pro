"""
Test Data Factories

Provides helper functions to create test data in the database.

Usage:
    tenant = await create_tenant(db, name="Test Tenant")
    user = await create_user(db, tenant_id=tenant.id)
    project = await create_project(db, tenant_id=tenant.id, user_id=user.id)
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.models import Tenant, User
from src.modules.documents.models import Document
from src.modules.projects.models import Project

# ===========================================
# TENANT FACTORIES
# ===========================================


async def create_tenant(
    db: AsyncSession,
    name: str | None = None,
    slug: str | None = None,
    subscription_plan: str = "free",
    subscription_status: str = "active",
) -> Tenant:
    """
    Crea un tenant de test.

    Args:
        db: Sesión de base de datos
        name: Nombre del tenant (auto-generado si no se provee)
        slug: Slug del tenant (auto-generado desde name)
        subscription_plan: Plan de suscripción (free, pro, enterprise)
        subscription_status: Estado de suscripción (active, cancelled, suspended)

    Returns:
        Tenant creado y persistido en BD
    """
    if name is None:
        name = f"Test Tenant {uuid4().hex[:8]}"

    if slug is None:
        slug = name.lower().replace(" ", "-")

    tenant = Tenant(
        id=uuid4(),
        name=name,
        slug=slug,
        subscription_plan=subscription_plan,
        subscription_status=subscription_status,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return tenant


# ===========================================
# USER FACTORIES
# ===========================================


async def create_user(
    db: AsyncSession,
    tenant_id: UUID,
    email: str | None = None,
    role: str = "admin",
    is_active: bool = True,
    hashed_password: str = "hashed_password_mock",
) -> User:
    """
    Crea un usuario de test.

    Args:
        db: Sesión de base de datos
        tenant_id: ID del tenant al que pertenece
        email: Email del usuario (auto-generado si no se provee)
        role: Rol del usuario (admin, member)
        is_active: Si el usuario está activo
        hashed_password: Contraseña hasheada (mock por defecto)

    Returns:
        User creado y persistido en BD
    """
    if email is None:
        email = f"user-{uuid4().hex[:8]}@example.com"

    user = User(
        id=uuid4(),
        tenant_id=tenant_id,
        email=email,
        hashed_password=hashed_password,
        role=role,
        is_active=is_active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def create_user_and_tenant(
    db: AsyncSession,
    tenant_name: str | None = None,
    user_email: str | None = None,
    user_role: str = "admin",
) -> tuple[User, Tenant]:
    """
    Helper para crear un tenant Y un usuario al mismo tiempo.

    Args:
        db: Sesión de base de datos
        tenant_name: Nombre del tenant
        user_email: Email del usuario
        user_role: Rol del usuario

    Returns:
        Tupla (user, tenant)
    """
    tenant = await create_tenant(db, name=tenant_name)
    user = await create_user(
        db,
        tenant_id=tenant.id,
        email=user_email,
        role=user_role,
    )

    return user, tenant


# ===========================================
# PROJECT FACTORIES
# ===========================================


async def create_project(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    name: str | None = None,
    description: str = "Test project description",
    status: str = "active",
) -> Project:
    """
    Crea un proyecto de test.

    Args:
        db: Sesión de base de datos
        tenant_id: ID del tenant propietario
        user_id: ID del usuario creador
        name: Nombre del proyecto (auto-generado si no se provee)
        description: Descripción del proyecto
        status: Estado del proyecto (active, archived, completed)

    Returns:
        Project creado y persistido en BD
    """
    if name is None:
        name = f"Test Project {uuid4().hex[:8]}"

    project = Project(
        id=uuid4(),
        tenant_id=tenant_id,
        created_by=user_id,
        name=name,
        description=description,
        status=status,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    return project


# ===========================================
# DOCUMENT FACTORIES
# ===========================================


async def create_document(
    db: AsyncSession,
    tenant_id: UUID,
    project_id: UUID,
    uploaded_by: UUID,
    filename: str | None = None,
    document_type: str = "contract",
    storage_path: str | None = None,
    size_bytes: int = 1024,
) -> Document:
    """
    Crea un documento de test.

    Args:
        db: Sesión de base de datos
        tenant_id: ID del tenant propietario
        project_id: ID del proyecto al que pertenece
        uploaded_by: ID del usuario que subió el documento
        filename: Nombre del archivo (auto-generado si no se provee)
        document_type: Tipo de documento (contract, invoice, schedule, etc.)
        storage_path: Path de almacenamiento (auto-generado si no se provee)
        size_bytes: Tamaño del archivo en bytes

    Returns:
        Document creado y persistido en BD
    """
    if filename is None:
        filename = f"test-document-{uuid4().hex[:8]}.pdf"

    if storage_path is None:
        storage_path = f"projects/{project_id}/documents/{filename}"

    document = Document(
        id=uuid4(),
        tenant_id=tenant_id,
        project_id=project_id,
        uploaded_by=uploaded_by,
        filename=filename,
        document_type=document_type,
        storage_path=storage_path,
        size_bytes=size_bytes,
        processing_status="completed",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    return document


# ===========================================
# COMPOSITE FACTORIES
# ===========================================


async def create_full_test_scenario(
    db: AsyncSession,
    tenant_name: str | None = None,
) -> dict:
    """
    Crea un escenario completo de test con tenant, user, project y document.

    Útil para tests de integración que necesitan datos completos.

    Args:
        db: Sesión de base de datos
        tenant_name: Nombre del tenant

    Returns:
        Dict con todas las entidades creadas:
        {
            "tenant": Tenant,
            "user": User,
            "project": Project,
            "document": Document,
        }
    """
    # 1. Crear tenant y user
    user, tenant = await create_user_and_tenant(db, tenant_name=tenant_name)

    # 2. Crear project
    project = await create_project(
        db,
        tenant_id=tenant.id,
        user_id=user.id,
    )

    # 3. Crear document
    document = await create_document(
        db,
        tenant_id=tenant.id,
        project_id=project.id,
        uploaded_by=user.id,
    )

    return {
        "tenant": tenant,
        "user": user,
        "project": project,
        "document": document,
    }


async def create_cross_tenant_scenario(
    db: AsyncSession,
) -> dict:
    """
    Crea escenario con 2 tenants para tests de RLS isolation.

    Útil para validar que Tenant A no puede acceder datos de Tenant B.

    Returns:
        Dict con:
        {
            "tenant_a": Tenant,
            "user_a": User,
            "project_a": Project,
            "tenant_b": Tenant,
            "user_b": User,
            "project_b": Project,
        }
    """
    # Tenant A
    user_a, tenant_a = await create_user_and_tenant(
        db,
        tenant_name="Tenant A",
    )
    project_a = await create_project(
        db,
        tenant_id=tenant_a.id,
        user_id=user_a.id,
        name="Project A",
    )

    # Tenant B
    user_b, tenant_b = await create_user_and_tenant(
        db,
        tenant_name="Tenant B",
    )
    project_b = await create_project(
        db,
        tenant_id=tenant_b.id,
        user_id=user_b.id,
        name="Project B",
    )

    return {
        "tenant_a": tenant_a,
        "user_a": user_a,
        "project_a": project_a,
        "tenant_b": tenant_b,
        "user_b": user_b,
        "project_b": project_b,
    }
