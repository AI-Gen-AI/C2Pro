# Problema de Conexión a Base de Datos - IPv6

## Problema Detectado

```
[ERROR] Connection failed: [Errno 11001] getaddrinfo failed
```

### Causa Raíz

Supabase usa **solo IPv6** para las conexiones directas a la base de datos (`db.*.supabase.co`), pero Windows en este sistema no tiene IPv6 habilitado/configurado correctamente.

### Evidencia

1. **nslookup funciona (IPv6):**
   ```
   db.tcxedmnvebazcsaridge.supabase.co
   Address: 2a05:d016:571:a420:d0f3:c32f:4143:8f15
   ```

2. **Python/asyncpg falla:**
   ```
   [ERROR] getaddrinfo failed
   [ERROR] No es posible el acceso a la ubicación de red
   ```

---

## Solución: Usar Supabase Connection Pooler

Supabase ofrece dos tipos de conexión:

| Tipo | Hostname | Protocolo | Compatibilidad |
|------|----------|-----------|----------------|
| **Direct Connection** | `db.*.supabase.co` | IPv6 only | ❌ No funciona en este sistema |
| **Connection Pooler** | `aws-0-us-east-1.pooler.supabase.com` | IPv4/IPv6 | ✅ Funciona en Windows |

### Pasos para Obtener el Connection String Correcto

1. **Ir a Supabase Dashboard:**
   - https://supabase.com/dashboard/project/tcxedmnvebazcsaridge

2. **Navegar a Settings → Database:**
   - Sidebar: Settings
   - Tab: Database

3. **Copiar Connection String del Pooler:**
   - Sección: "Connection pooling"
   - Mode: "Transaction"  (recomendado) o "Session"
   - Copy: "Connection string" (URI)

4. **Actualizar `.env`:**
   ```bash
   # ANTES (Direct - no funciona)
   DATABASE_URL=postgresql://postgres:[password]@db.tcxedmnvebazcsaridge.supabase.co:5432/postgres

   # DESPUÉS (Pooler - funciona)
   DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```

### Diferencias Clave

| Aspecto | Direct Connection | Connection Pooler |
|---------|-------------------|-------------------|
| Hostname | `db.*.supabase.co` | `*.pooler.supabase.com` |
| Puerto | `5432` | `6543` (Transaction) o `5432` (Session) |
| Usuario | `postgres` | `postgres.[project-ref]` |
| IPv6 | Requerido | Opcional |
| Conexiones | Directas | Pooled |
| Latencia | Mínima | +1-2ms |

---

## Configuración Recomendada para C2Pro

### Archivo `.env` (Actualizado)

```bash
# ===========================================
# SUPABASE (Database + Auth)
# ===========================================
SUPABASE_URL=https://tcxedmnvebazcsaridge.supabase.co
SUPABASE_ANON_KEY=eyJhbG...
SUPABASE_SERVICE_ROLE_KEY=eyJhbG...

# Conexión con Connection Pooler (IPv4 compatible)
# Obtener de: Supabase Dashboard → Settings → Database → Connection pooling
DATABASE_URL=postgresql://postgres.tcxedmnvebazcsaridge:[YOUR_PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

**IMPORTANTE:**
- Reemplaza `[YOUR_PASSWORD]` con tu contraseña real
- El usuario ahora es `postgres.[project-ref]` en lugar de solo `postgres`
- El puerto ahora es `6543` en lugar de `5432`
- El hostname ahora es `*.pooler.supabase.com` en lugar de `db.*.supabase.co`

---

## Verificar la Conexión

Una vez actualizado el `.env`, ejecuta:

```bash
cd infrastructure/supabase
python test_connection.py
```

Deberías ver:
```
[OK] Connection successful!
PostgreSQL version: PostgreSQL 15.x...
[OK] Connection closed
```

---

## Ejecutar las Migraciones

Una vez verificada la conexión:

```bash
cd infrastructure/supabase
python run_migrations.py --env local
```

---

## Alternativas (Si el Pooler no Funciona)

### Opción 1: Habilitar IPv6 en Windows

1. Abrir PowerShell como Administrador
2. Ejecutar:
   ```powershell
   netsh interface ipv6 show interface
   netsh interface ipv6 set interface "Ethernet" forwarding=enabled advertise=enabled
   ```
3. Reiniciar adaptador de red

### Opción 2: Usar Supabase CLI con Local Postgres

```bash
# Instalar Supabase CLI
npm install -g supabase

# Iniciar base de datos local
supabase start

# Usar DATABASE_URL local
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
```

### Opción 3: Usar Tunnel SSH

```bash
# Requiere SSH access a un servidor con IPv6
ssh -L 5432:db.tcxedmnvebazcsaridge.supabase.co:5432 user@server-with-ipv6

# Usar localhost
DATABASE_URL=postgresql://postgres:[password]@localhost:5432/postgres
```

---

## Referencias

- [Supabase Database Connection Pooling](https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pooler)
- [asyncpg IPv6 Issues on Windows](https://github.com/MagicStack/asyncpg/issues/123)
- [Windows IPv6 Configuration](https://learn.microsoft.com/en-us/windows-server/networking/technologies/ipv6/ipv6-config)

---

## Estado Actual

- ❌ Direct Connection: **No funciona** (IPv6 no disponible)
- ⏳ Connection Pooler: **Pendiente de configurar**
- ⏳ Migraciones: **Pendientes de ejecutar**
- ⏳ CTO Gates: **Pendientes de validar**

**Próximo paso:** Actualizar `DATABASE_URL` en `.env` con el Connection Pooler string de Supabase.

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
