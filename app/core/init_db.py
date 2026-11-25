from sqlalchemy import inspect, select, text

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_pin
from app.models import Almacen, RolUsuario, Usuario


def _sync_missing_columns() -> None:
    inspector = inspect(engine)
    if "usuarios" in inspector.get_table_names():
        columnas = {col["name"] for col in inspector.get_columns("usuarios")}
        if "telefono" not in columnas:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE usuarios ADD COLUMN telefono VARCHAR(30)"))


def init_db() -> None:
    """Crea las tablas definidas y siembra el almacen y admin inicial si la BD esta vacia."""
    Base.metadata.create_all(bind=engine)
    _sync_missing_columns()

    settings = get_settings()
    with SessionLocal() as db:
        almacen = db.scalar(select(Almacen).limit(1))
        if almacen is None:
            almacen = Almacen(nombre=settings.default_store_name)
            db.add(almacen)
            db.flush()

        admin = db.scalar(
            select(Usuario).where(
                Usuario.almacen_id == almacen.id,
                Usuario.username == settings.default_admin_user,
            )
        )
        if admin is None:
            admin = Usuario(
                almacen_id=almacen.id,
                nombre="Administrador",
                username=settings.default_admin_user,
                pin_hash=hash_pin(settings.default_admin_pin),
                rol=RolUsuario.ADMIN.value,
            )
            db.add(admin)

        db.commit()
