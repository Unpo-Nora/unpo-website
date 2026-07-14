"""
Autorización por rol reutilizable.

Reemplaza el patrón repetido `if current_user.role != "admin": raise HTTPException(...)`
que estaba copiado router por router. Se apoya en `get_current_user` (que ya resuelve
la autenticación y devuelve 401 si el token es inválido o falta) y agrega el chequeo de
rol, devolviendo 403 si el rol no está permitido.

Uso:
    from ..dependencies.permissions import require_roles

    @router.get("/algo")
    def algo(current_user = Depends(require_roles("admin"))): ...

    @router.post("/otro")
    def otro(current_user = Depends(require_roles("admin", "vendedor"))): ...

Roles válidos del sistema (Etapa 0A): "admin" y "vendedor".
Los roles fantasma "seller" y "vendor" NO son válidos: si se pasan a require_roles se
lanza un error de configuración en el arranque (falla rápido, no se aceptan en silencio).
El rol "supervisor_comercial" se agregará en una etapa posterior; hoy no está permitido.
"""

from fastapi import Depends, HTTPException, status

from ..models import User
from ..routers.auth import get_current_user

# Única fuente de verdad de los roles válidos actuales.
VALID_ROLES = frozenset({"admin", "vendedor"})


def require_roles(*allowed_roles: str):
    """
    Factory de dependencia FastAPI que exige autenticación y uno de los roles indicados.

    - 401 si no hay credenciales válidas (lo resuelve `get_current_user`).
    - 403 si el usuario autenticado no tiene ninguno de los roles permitidos.
    - Devuelve el `User` autenticado para que el endpoint lo siga usando.
    """
    if not allowed_roles:
        raise ValueError("require_roles requiere al menos un rol")

    invalid = set(allowed_roles) - VALID_ROLES
    if invalid:
        # Falla de configuración en import-time: evita habilitar roles fantasma
        # (p. ej. "seller"/"vendor") por error.
        raise ValueError(
            f"require_roles: rol(es) inválido(s) {sorted(invalid)}. "
            f"Roles válidos: {sorted(VALID_ROLES)}"
        )

    allowed = frozenset(allowed_roles)

    async def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para realizar esta acción",
            )
        return current_user

    return _dependency
