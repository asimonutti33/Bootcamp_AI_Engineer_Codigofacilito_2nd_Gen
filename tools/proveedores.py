"""Herramienta `consultar_proveedor` sobre data/proveedores.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contracts.tool_schemas import ConsultarProveedorArgs

PROVEEDORES_DB = Path(__file__).resolve().parents[1] / "data" / "proveedores.json"


@lru_cache(maxsize=1)
def _proveedores() -> dict[str, dict]:
    proveedores = json.loads(PROVEEDORES_DB.read_text(encoding="utf-8"))
    return {p["nombre"].lower(): p for p in proveedores}


def consultar_proveedor(args: ConsultarProveedorArgs) -> dict:
    """Servicio, SLA, estado y contacto de un proveedor por nombre."""
    proveedor = _proveedores().get(args.nombre.strip().lower())
    if proveedor is None:
        return {"error": f"proveedor {args.nombre!r} no existe"}
    return {
        "nombre": proveedor["nombre"],
        "servicio": proveedor["servicio"],
        "sla_horas": proveedor["sla_horas"],
        "estado": proveedor["estado"],
        "contacto": proveedor["contacto"],
        "contratos_vigentes": proveedor["contratos_vigentes"],
    }
