"""
C2Pro - MCP (Model Context Protocol) Integration

Este paquete contiene los servidores MCP para integración segura
con agentes de IA y sistemas externos.

Security First:
- Allowlist estricta de vistas y funciones
- Query limits (timeout, row count, cost)
- Rate limiting por tenant
- Logging completo para auditoría
- NO permite SQL arbitrario
"""

from src.core.mcp.servers.database_server import DatabaseMCPServer

__all__ = [
    "DatabaseMCPServer",
]
