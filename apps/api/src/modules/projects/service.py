"""
C2Pro - Projects Service

Lógica de negocio para gestión de proyectos.
"""

import math
from datetime import datetime
from typing import Any  # Added to fix F821 Undefined name Any
from uuid import UUID

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ConflictError, NotFoundError
from src.modules.projects.models import Project, ProjectStatus
from src.modules.projects.schemas import (
    ProjectCreateRequest,
    ProjectFilters,
    ProjectListItemResponse,
    ProjectListResponse,
    ProjectStatsResponse,
    ProjectUpdateRequest,
)

logger = structlog.get_logger()


# ===========================================
# HELPER FUNCTIONS
# ===========================================


async def get_project_by_id(db: AsyncSession, project_id: UUID, tenant_id: UUID) -> Project | None:
    """
    Obtiene proyecto por ID verificando tenant.

    Args:
        db: Sesión de base de datos
        project_id: ID del proyecto
        tenant_id: ID del tenant (para verificar permisos)

    Returns:
        Proyecto si existe y pertenece al tenant, None si no
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id).where(Project.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def get_project_by_code(db: AsyncSession, code: str, tenant_id: UUID) -> Project | None:
    """
    Obtiene proyecto por código dentro del tenant.

    Args:
        db: Sesión de base de datos
        code: Código del proyecto
        tenant_id: ID del tenant

    Returns:
        Proyecto si existe, None si no
    """
    result = await db.execute(
        select(Project).where(Project.code == code).where(Project.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


# ===========================================
# PROJECT SERVICE
# ===========================================


class ProjectService:
    """Servicio de gestión de proyectos."""

    @staticmethod
    async def create_project(
        db: AsyncSession, tenant_id: UUID, user_id: UUID, request: ProjectCreateRequest
    ) -> Project:
        """
        Crea nuevo proyecto.

        Args:
            db: Sesión de base de datos
            tenant_id: ID del tenant
            user_id: ID del usuario que crea el proyecto
            request: Datos del proyecto

        Returns:
            Proyecto creado

        Raises:
            ConflictError: Si ya existe un proyecto con el mismo código
        """
        # Verificar que el código sea único (si se proporciona)
        if request.code:
            existing = await get_project_by_code(db, request.code, tenant_id)
            if existing:
                raise ConflictError(f"Project with code '{request.code}' already exists")

        # Crear proyecto
        project = Project(
            tenant_id=tenant_id,
            name=request.name,
            description=request.description,
            code=request.code,
            project_type=request.project_type,
            status=ProjectStatus.DRAFT,  # Siempre empieza como draft
            estimated_budget=request.estimated_budget,
            currency=request.currency,
            start_date=request.start_date,
            end_date=request.end_date,
            project_metadata=request.metadata or {},
        )

        db.add(project)
        await db.commit()
        await db.refresh(project)

        logger.info(
            "project_created",
            project_id=str(project.id),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            name=project.name,
        )

        return project

    @staticmethod
    async def get_project(db: AsyncSession, project_id: UUID, tenant_id: UUID) -> Project:
        """
        Obtiene proyecto por ID.

        Args:
            db: Sesión de base de datos
            project_id: ID del proyecto
            tenant_id: ID del tenant

        Returns:
            Proyecto

        Raises:
            NotFoundError: Si el proyecto no existe o no pertenece al tenant
        """
        project = await get_project_by_id(db, project_id, tenant_id)

        if not project:
            raise NotFoundError("Project not found")

        return project

    @staticmethod
    async def list_projects(
        db: AsyncSession,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        filters: ProjectFilters | None = None,
    ) -> ProjectListResponse:
        """
        Lista proyectos con paginación y filtros.

        Args:
            db: Sesión de base de datos
            tenant_id: ID del tenant
            page: Número de página (1-indexed)
            page_size: Tamaño de página
            filters: Filtros opcionales

        Returns:
            Lista paginada de proyectos
        """
        # Validar paginación
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        # Base query
        query = select(Project).where(Project.tenant_id == tenant_id)

        # Aplicar filtros
        if filters:
            # Búsqueda en texto
            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.where(
                    or_(
                        Project.name.ilike(search_term),
                        Project.description.ilike(search_term),
                        Project.code.ilike(search_term),
                    )
                )

            # Filtros exactos
            if filters.status:
                query = query.where(Project.status == filters.status)

            if filters.project_type:
                query = query.where(Project.project_type == filters.project_type)

            # Coherence score range
            if filters.min_coherence_score is not None:
                query = query.where(Project.coherence_score >= filters.min_coherence_score)

            if filters.max_coherence_score is not None:
                query = query.where(Project.coherence_score <= filters.max_coherence_score)

            # Fechas
            if filters.created_after:
                query = query.where(Project.created_at >= filters.created_after)

            if filters.created_before:
                query = query.where(Project.created_at <= filters.created_before)

        # Contar total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Ordenar por fecha de creación (más recientes primero)
        query = query.order_by(Project.created_at.desc())

        # Aplicar paginación
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Ejecutar query
        result = await db.execute(query)
        projects = result.scalars().all()

        # Calcular metadata de paginación
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        has_next = page < total_pages
        has_prev = page > 1

        return ProjectListResponse(
            items=[ProjectListItemResponse.model_validate(p) for p in projects],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
        )

    @staticmethod
    async def update_project(
        db: AsyncSession, project_id: UUID, tenant_id: UUID, request: ProjectUpdateRequest
    ) -> Project:
        """
        Actualiza proyecto.

        Args:
            db: Sesión de base de datos
            project_id: ID del proyecto
            tenant_id: ID del tenant
            request: Datos a actualizar

        Returns:
            Proyecto actualizado

        Raises:
            NotFoundError: Si el proyecto no existe
            ConflictError: Si el nuevo código ya existe
        """
        project = await ProjectService.get_project(db, project_id, tenant_id)

        # Verificar código único (si se está actualizando)
        if request.code and request.code != project.code:
            existing = await get_project_by_code(db, request.code, tenant_id)
            if existing and existing.id != project_id:
                raise ConflictError(f"Project with code '{request.code}' already exists")

        # Actualizar campos
        if request.name is not None:
            project.name = request.name

        if request.description is not None:
            project.description = request.description

        if request.code is not None:
            project.code = request.code

        if request.project_type is not None:
            project.project_type = request.project_type

        if request.status is not None:
            project.status = request.status

        if request.estimated_budget is not None:
            project.estimated_budget = request.estimated_budget

        if request.currency is not None:
            project.currency = request.currency

        if request.start_date is not None:
            project.start_date = request.start_date

        if request.end_date is not None:
            project.end_date = request.end_date

        if request.metadata is not None:
            project.project_metadata = request.metadata

        project.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(project)

        logger.info("project_updated", project_id=str(project_id), tenant_id=str(tenant_id))

        return project

    @staticmethod
    async def delete_project(db: AsyncSession, project_id: UUID, tenant_id: UUID) -> None:
        """
        Elimina proyecto.

        Args:
            db: Sesión de base de datos
            project_id: ID del proyecto
            tenant_id: ID del tenant

        Raises:
            NotFoundError: Si el proyecto no existe
        """
        project = await ProjectService.get_project(db, project_id, tenant_id)

        await db.delete(project)
        await db.commit()

        logger.info("project_deleted", project_id=str(project_id), tenant_id=str(tenant_id))

        @staticmethod
        async def get_project_stats(db: AsyncSession, tenant_id: UUID) -> ProjectStatsResponse:
            """
            Obtiene estadísticas de proyectos del tenant.

                    Args:

                        db: Sesión de base de datos

                        tenant_id: ID del tenant



                    Returns:

                        Estadísticas de proyectos

            """
            # Contar proyectos por estado
            base_query = select(Project).where(Project.tenant_id == tenant_id)

            # Total
            total_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
            total = total_result.scalar_one()

            # Por estado
            active_result = await db.execute(
                select(func.count()).select_from(
                    base_query.where(Project.status == ProjectStatus.ACTIVE).subquery()
                )
            )
            active = active_result.scalar_one()

            draft_result = await db.execute(
                select(func.count()).select_from(
                    base_query.where(Project.status == ProjectStatus.DRAFT).subquery()
                )
            )
            draft = draft_result.scalar_one()

            completed_result = await db.execute(
                select(func.count()).select_from(
                    base_query.where(Project.status == ProjectStatus.COMPLETED).subquery()
                )
            )
            completed = completed_result.scalar_one()

            archived_result = await db.execute(
                select(func.count()).select_from(
                    base_query.where(Project.status == ProjectStatus.ARCHIVED).subquery()
                )
            )
            archived = archived_result.scalar_one()

            # Coherence score promedio
            avg_score_result = await db.execute(
                select(func.avg(Project.coherence_score))
                .where(Project.tenant_id == tenant_id)
                .where(Project.coherence_score.isnot(None))
            )
            avg_score = avg_score_result.scalar_one()

            # TODO: Contar alertas cuando implementemos el módulo de análisis
            total_critical_alerts = 0
            total_high_alerts = 0

            return ProjectStatsResponse(
                total_projects=total,
                active_projects=active,
                draft_projects=draft,
                completed_projects=completed,
                archived_projects=archived,
                avg_coherence_score=float(avg_score) if avg_score else None,
                total_critical_alerts=total_critical_alerts,
                total_high_alerts=total_high_alerts,
            )

        @staticmethod
        async def get_project_coherence_score(
            db: AsyncSession, project_id: UUID, tenant_id: UUID
        ) -> dict[str, Any]:
            """
            Obtiene el score de coherencia y su desglose para un proyecto.

                    Args:
                        db: Sesión de base de datos
                        project_id: ID del proyecto
                        tenant_id: ID del tenant

                    Returns:
                        Diccionario con el score de coherencia y su desglose.                    Raises:

                        NotFoundError: Si el proyecto no existe o no pertenece al tenant.

            """
            project = await ProjectService.get_project(db, project_id, tenant_id)

            # Simulación de cálculo de coherencia y desglose
            # En una implementación real, esto interactuaría con el módulo de análisis
            coherence_score = project.coherence_score if project.coherence_score is not None else 75
            breakdown = {
                "document_consistency": 80,
                "stakeholder_alignment": 70,
                "wbs_bom_coherence": 75,
                "overall_rules_passed": 15,
                "overall_rules_failed": 3,
            }

            logger.info(
                "project_coherence_score_retrieved",
                project_id=str(project_id),
                tenant_id=str(tenant_id),
                coherence_score=coherence_score,
            )
            return {"coherence_score": coherence_score, "breakdown": breakdown}
