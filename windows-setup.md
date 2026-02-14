# Guía de Configuración para Desarrollo en Windows

**Última Actualización:** 2026-02-07

Este documento consolida todos los consejos, configuraciones y soluciones a problemas comunes para desarrolladores que trabajan en un entorno nativo de Windows.

Aunque recomendamos usar **WSL2 (Windows Subsystem for Linux)** para una experiencia más fluida y compatible con el ecosistema de contenedores, es posible desarrollar en Windows nativo siguiendo esta guía.

---

## 1. Prerrequisitos Esenciales

Antes de empezar, asegúrate de tener lo siguiente:

- **Ejecutar como Administrador**: Inicia siempre tu terminal (PowerShell, CMD, Windows Terminal) con "Ejecutar como administrador". Esto previene errores de permisos (`PermissionError: [WinError 5]`).

- **Python 3.11**: Se recomienda **Python 3.11** en lugar de versiones más recientes (como 3.12+). La versión 3.11 tiene un ecosistema de paquetes precompilados (wheels) mucho más maduro para Windows, lo que evita la necesidad de compilar paquetes desde el código fuente.

- **Visual Studio Build Tools**: Si insistes en usar una versión de Python más reciente (3.12+), es **obligatorio** instalar las "Herramientas de compilación de C++ de Visual Studio". Muchos paquetes de Python (como `spacy` o `asyncpg`) las necesitan para compilarse en Windows.
  - Descarga el "Build Tools for Visual Studio" desde la web de Visual Studio.
  - Durante la instalación, selecciona la carga de trabajo "Desarrollo de escritorio con C++".

- **Docker Desktop**: Asegúrate de tener Docker Desktop instalado y funcionando.

---

## 2. Configuración del Entorno

### 2.1. Variables de Entorno en PowerShell

Para evitar problemas de codificación de caracteres en la consola, especialmente al ejecutar scripts de Python, establece la siguiente variable de entorno al inicio de tu sesión:

```powershell
# Resuelve errores de tipo UnicodeEncodeError
$env:PYTHONIOENCODING='utf-8'
```

Para establecer otras variables de entorno necesarias para el proyecto (como `DATABASE_URL`):

```powershell
$env:DATABASE_URL="postgresql://user:pass@host:port/db"
```

### 2.2. Conexión a la Base de Datos (Supabase)

Al configurar tu archivo `.env`, es **altamente recomendable** usar la URL de conexión del **Connection Pooler (pgbouncer)** de Supabase, que utiliza el puerto `6543`.

```dotenv
# .env

# ✅ RECOMENDADO PARA WINDOWS
DATABASE_URL=postgresql://postgres.xxx:[PASSWORD]@aws-region.pooler.supabase.com:6543/postgres

# ❌ NO RECOMENDADO (puede dar problemas de DNS/IPv6 en Windows)
# DATABASE_URL=postgresql://postgres.xxx:[PASSWORD]@aws-region.connect.aws.supabase.com:5432/postgres
```

El Connection Pooler es más compatible con la pila de red de Windows y evita problemas comunes de resolución de DNS.

---

## 3. Solución de Problemas Comunes (Troubleshooting)

### Error: `UnicodeEncodeError: 'charmap' codec can't encode character...`

- **Causa**: La consola de Windows (CMD o PowerShell) no está usando UTF-8 por defecto.
- **Solución**: Ejecuta `$env:PYTHONIOENCODING='utf-8'` en tu sesión de PowerShell antes de correr cualquier script de Python.

### Error: `PermissionError: [WinError 5] Acceso denegado`

- **Causa**: El script necesita privilegios elevados para realizar una operación (ej. acceder a ciertos archivos o puertos).
- **Solución**: Cierra tu terminal y vuelve a abrirla haciendo clic derecho y seleccionando "Ejecutar como administrador".

### Error: `Microsoft Visual C++ 14.0 or greater is required`

- **Causa**: Estás intentando instalar un paquete de Python que necesita ser compilado desde código fuente y no tienes las herramientas de compilación de C++ necesarias.
- **Solución**:
  1. **(Recomendado)** Desinstala tu versión actual de Python e instala **Python 3.11**.
  2. **(Alternativa)** Instala las "Build Tools for Visual Studio" como se indica en la sección de prerrequisitos.

### Error: `ConnectionResetError [WinError 10054]` al conectar con Docker

- **Causa**: Incompatibilidad entre el driver `asyncpg` y el event loop por defecto de Python en Windows al conectar con un contenedor Docker.
- **Solución**:
  1. **(Recomendado)** Usa WSL2 para ejecutar los tests y el backend. El entorno de red de Linux es mucho más compatible.
  2. **(Alternativa)** Instala PostgreSQL de forma nativa en Windows en lugar de usar Docker para la base de datos de prueba.

### Error: Puerto 8000 ya en uso

- **Causa**: Otro proceso está ocupando el puerto 8000.
- **Solución**: Encuentra y detén el proceso.
  ```powershell
  # 1. Encuentra el ID del proceso (PID) que usa el puerto 8000
  netstat -ano | findstr :8000

  # 2. Detén el proceso usando su PID
  taskkill /PID <PID_del_proceso> /F
  ```

---
*Este documento debe ser el primer punto de referencia para cualquier desarrollador que trabaje en Windows.*