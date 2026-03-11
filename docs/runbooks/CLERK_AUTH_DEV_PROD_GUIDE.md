# Clerk Auth en C2Pro: guía práctica (Dev vs Producción)

Esta guía explica por qué llega correo desde `noreply@accounts.dev` y cómo arrancar C2Pro en modo desarrollo y en modo "usuario final" (producción).

---

## 1) Qué significa el correo `noreply@accounts.dev`

Si ves correos como:

- `[Development] New device signed in to your C2Pro account`
- remitente `noreply@accounts.dev`

**es normal en Clerk Development**. No es un error de C2Pro: significa que estás autenticando con una instancia de Clerk en entorno de desarrollo.

Señales claras de entorno Dev:

- El asunto del correo incluye `[Development]`.
- El remitente es `accounts.dev`.
- Estás usando claves de Clerk de tipo `pk_test_...` / `sk_test_...`.

---

## 2) Arranque recomendado para desarrollo local (lo más simple)

1. Copia variables de entorno base:

```bash
cp .env.example .env
```

2. Levanta infraestructura:

```bash
docker compose up -d postgres redis minio minio-setup
```

3. Backend (terminal 1):

```bash
cd apps/api
pip install -r requirements.txt
alembic upgrade head
python dev.py
```

4. Frontend (terminal 2):

```bash
cd apps/web
npm install
npm run dev
```

5. Abre la app en `http://localhost:3000`.

> En este flujo, si tu auth está conectada a Clerk Dev, seguirás viendo correos `accounts.dev` y es esperado.

---

## 3) Diferencia real entre "modo dev" y "modo usuario final"

En este repo hay **dos ejes distintos** que suelen confundirse:

1. **Modo de datos de la app web**
   - `NEXT_PUBLIC_APP_MODE=demo` → frontend con mocks (MSW), sin backend real.
   - Sin `NEXT_PUBLIC_APP_MODE=demo` → frontend contra API real.

2. **Entorno de autenticación (Clerk)**
   - **Development (test keys)** → correos `accounts.dev`, asuntos `[Development]`.
   - **Production (live keys + dominio/email de producción)** → experiencia de usuario final.

⚠️ Importante: quitar `demo` **no** te convierte automáticamente en producción de auth. Si sigues con claves test de Clerk, seguirás en entorno de desarrollo.

---

## 4) Checklist para verlo como usuario final (producción)

Para experiencia "real" de usuario final necesitas **todo** en producción, especialmente auth:

- [ ] Proyecto Clerk en entorno Production.
- [ ] Variables con claves `pk_live_...` y `sk_live_...` (no test).
- [ ] Dominio de producción configurado en Clerk (y URLs permitidas de sign-in/sign-up).
- [ ] Plantillas de correo y remitente de producción verificados en Clerk.
- [ ] Frontend desplegado con variables de producción.
- [ ] Backend desplegado y accesible desde frontend.

Si falta cualquiera de estos puntos, la experiencia seguirá parcial de desarrollo.

---

## 5) Cómo comprobar rápido en qué entorno estás

### Desde el correo

- Si pone `[Development]` y viene de `accounts.dev` → estás en Clerk Dev.

### Desde variables de entorno

- Si ves claves `*_test_*` → entorno de desarrollo.
- Si ves claves `*_live_*` → entorno de producción.

### Desde comportamiento de la app

- Si sale banner/demo data o no requiere backend real → estás en modo demo de frontend.

---

## 6) Problemas típicos y solución

### "Puedo entrar, pero me llegan correos de desarrollo"

No es bug: estás autenticando con Clerk Dev. Migra claves y configuración de Clerk a producción.

### "Creía que ya estaba como usuario final porque no uso demo"

Sin `demo` solo indica que usas API real; **no** implica que auth sea producción.

### "No sé si estoy en dev o prod"

Confirma 3 cosas: correo recibido, tipo de claves (`test` vs `live`) y variables cargadas en el entorno donde ejecutas frontend/backend.

---

## 7) Flujo recomendado para evitar confusión

1. Usa local/dev con claves test para desarrollar.
2. Antes de validar como usuario final, crea un entorno de staging/producción con claves live.
3. Verifica login, registro, recuperación de contraseña y correos en ese entorno live.
4. Solo entonces valida UX final de usuario.

---

## 8) Resumen corto

- El correo `noreply@accounts.dev` con `[Development]` es normal en Clerk Dev.
- "Demo mode" de frontend y "entorno Clerk" son cosas diferentes.
- Para verse como usuario final necesitas Clerk Production + claves live + dominio/email de producción.
