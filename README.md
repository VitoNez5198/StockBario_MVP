# StockBarrio — Plataforma Web SaaS de Inventario y POS

Plataforma web de gestión comercial, control de inventario y Punto de Venta (POS) diseñada específicamente para almacenes de barrio y minimarkets de proximidad.

**Taller de Proyecto de Especialidad (AIEP — Ingeniería en Informática, Sección 16156)**  
**Equipo:** Víctor Antonio Martínez Santibáñez & Sebastián Andrés Aravena Osorio

---

## Alcance del MVP (alineado con Canvas, Cadena de Valor y Entregable Parte I)

1. **Terminal POS Rápido (`<10s` por venta):** Operación fluida por teclado y lector de código de barras USB 1D/2D, cálculo de vuelto, comprobante interno de 80mm (sin timbraje SII ni Transbank según delimitación) e historial con reimpresión/anulación.
2. **Inventario & Semáforo de Caducidad:** Trazabilidad completa de movimientos (entradas, salidas, mermas) y alertas preventivas de vencimiento (30 / 15 / 7 días + bloqueo preventivo de productos vencidos en POS).
3. **Libreta Digital de Fiados:** Gestión de vecinos con límite de crédito, validación atómica en caja, historial de deuda y registro de abonos.
4. **Lista de Compra Sugerida (WhatsApp):** Cálculo automático de reposición `(stock_mínimo × 2) − stock_actual` agrupado por proveedor con copia directa para WhatsApp.
5. **Caja y Arqueo Z:** Apertura de turno, seguimiento por medio de pago y cierre con cuadratura física.
6. **Reportes Analíticos y Resumen Diario:** Panel inicial de estado del negocio, rotación de productos, márgenes de ganancia e indicadores de impacto (**ERI** y **TMV**).

---

## Stack Tecnológico

- **Backend:** Python 3.12+ / FastAPI / SQLAlchemy 2.0 / Alembic
- **Base de Datos:** PostgreSQL (nube / producción) con fallback a SQLite en desarrollo local
- **Frontend:** Jinja2 + CSS moderno sobrio + JavaScript modular + íconos Lucide
- **Seguridad:** PIN hasheado con `bcrypt`, sesiones firmadas y roles (`ADMIN` / `CAJERO`)
- **Pruebas:** `pytest` + `httpx`
- **Despliegue:** GitHub (`main` / `dev`) → Render / Railway + PostgreSQL gestionado

---

## Puesta en Marcha Local

```bash
# 1. Crear entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
copy .env.example .env

# 4. Levantar servidor de desarrollo
uvicorn app.main:app --reload --port 8000
```

Verificar estado del servidor en: `http://127.0.0.1:8000/api/v1/health`

---

## Flujo de Ramas (Git)

- `main`: Versión estable conectada al despliegue en producción.
- `dev`: Rama de integración del sprint actual.
- `feat/<modulo>` / `fix/<detalle>`: Ramas cortas por tarjeta de Trello.
