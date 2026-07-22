"""
Comando de mantenimiento de WhatsApp: reprocesamiento y purga (Etapa 1D).

Uso:
    python -m app.jobs.whatsapp_maintenance reprocess --limit 100
    python -m app.jobs.whatsapp_maintenance purge --limit 500

Diseño (arquitectura §9): estos comandos se programan como cron/proceso SEPARADO, no
como tarea de fondo del web. El comando es delgado: valida argumentos, arma la sesión
existente (`app.database.SessionLocal`) y delega en `services.whatsapp.recovery`. No
contiene SQL ni lógica de negocio.

Códigos de salida:
    0  el lote operó correctamente (aunque eventos individuales hayan fallado);
    1  fallo OPERACIONAL del lote o de la base;
    2  error de uso (argumentos/rango inválidos).

Salida: únicamente el bloque de resultado sanitizado (sin payloads, teléfonos, nombres,
wa_id/wamid, texto ni SQL).
"""

import argparse
import hashlib
import sys
from typing import List, Optional

from ..database import SessionLocal
from ..services.whatsapp import config, recovery

EXIT_OK = 0
EXIT_OPERATIONAL_ERROR = 1
EXIT_USAGE = 2


def _session_factory():
    return SessionLocal()


def _positive_int(value: str, *, minimum: int, maximum: int, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"{label} debe ser un entero")
    if parsed < minimum or parsed > maximum:
        raise argparse.ArgumentTypeError(f"{label} debe estar entre {minimum} y {maximum}")
    return parsed


def _limit_type(value: str) -> int:
    return _positive_int(value, minimum=config.MIN_BATCH_SIZE, maximum=config.MAX_BATCH_SIZE,
                         label="--limit")


def _lease_type(value: str) -> int:
    return _positive_int(value, minimum=config.MIN_LEASE_SECONDS, maximum=config.MAX_LEASE_SECONDS,
                         label="--lease-seconds")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whatsapp_maintenance",
        description="Reprocesamiento y purga de eventos de webhook de WhatsApp (1D).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    rep = sub.add_parser("reprocess", help="Reclamar y reprocesar eventos elegibles.")
    rep.add_argument("--limit", type=_limit_type, default=None,
                     help=f"Tamaño del lote (default {config.DEFAULT_BATCH_SIZE}).")
    rep.add_argument("--lease-seconds", type=_lease_type, default=None,
                     help=f"Lease/gracia en segundos (default {config.DEFAULT_LEASE_SECONDS}).")
    rep.add_argument("--worker-id", type=str, default=None,
                     help="Identificador del worker (default: aleatorio corto, sin datos sensibles).")

    pur = sub.add_parser("purge", help="Anular raw_payload de eventos vencidos.")
    pur.add_argument("--limit", type=_limit_type, default=None,
                     help=f"Tamaño del lote (default {config.DEFAULT_BATCH_SIZE}).")

    return parser


def _sanitize_worker_id(raw: Optional[str]) -> str:
    """
    Convierte un `--worker-id` provisto en una HUELLA irreversible `wrk-<hash>`.

    Limpiar caracteres no alcanza: `usuario@empresa.com` -> `usuarioempresacom` seguiría
    revelando usuario y dominio. Se hashea (sha256, prefijo) y NUNCA se conserva ni se
    imprime el valor original, así que un email, hostname, usuario del sistema, dominio o
    IP que el operador pase por error jamás llega a la base, a los logs ni a la salida.
    Sin `--worker-id`, se genera un id aleatorio corto.
    """
    if not raw or not raw.strip():
        return recovery.generate_worker_id()
    digest = hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()[:12]
    return f"wrk-{digest}"


def _cmd_reprocess(args) -> int:
    lease = args.lease_seconds if args.lease_seconds is not None else config.get_lease_seconds()
    batch = args.limit if args.limit is not None else config.get_batch_size()
    worker_id = _sanitize_worker_id(args.worker_id)

    result = recovery.reprocess(
        _session_factory,
        lease_seconds=lease,
        batch_size=batch,
        max_attempts=config.get_max_attempts(),
        worker_id=worker_id,
    )
    print(result.render())
    return EXIT_OPERATIONAL_ERROR if result.operational_error else EXIT_OK


def _cmd_purge(args) -> int:
    batch = args.limit if args.limit is not None else config.get_batch_size()
    result = recovery.purge(_session_factory, batch_size=batch)
    print(result.render())
    return EXIT_OPERATIONAL_ERROR if result.operational_error else EXIT_OK


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse ya imprimió el error de uso; se normaliza a EXIT_USAGE.
        return EXIT_USAGE if exc.code not in (0, None) else EXIT_OK

    if args.command == "reprocess":
        return _cmd_reprocess(args)
    if args.command == "purge":
        return _cmd_purge(args)
    parser.print_usage()
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
