"""Reporte de llamadas al LLM a partir de logs/llm_calls.jsonl.

Uso:
    uv run scripts/report.py [ruta/al/archivo.jsonl]
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

DEFAULT_PATH = Path("logs/llm_calls.jsonl")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else DEFAULT_PATH

    # --- 1. ¿Existe el archivo? ---
    # Si no existe, avisamos y devolvemos 1 (código de error en Unix).
    if not path.exists():
        print(f"No existe el archivo: {path}")
        return 1

    # --- 2. Leer y parsear cada línea como JSON ---
    # splitlines() separa por saltos de línea.
    # Filtramos líneas vacías y parseamos cada una.
    lines = path.read_text(encoding="utf-8").splitlines()
    events: list[dict] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # Línea malformada: la ignoramos pero avisamos por stderr.
            print(f"Advertencia: línea inválida ignorada: {line[:60]}...", file=sys.stderr)

    # --- 3. ¿Log vacío? ---
    if not events:
        print("El log está vacío.")
        return 0

    print(f"Llamadas registradas: {len(events)}")

    # --- 4. Costo total ---
    # .get() con default evita KeyError si algún evento no tiene el campo.
    total_cost = sum(e.get("cost_usd", 0.0) for e in events)
    print(f"Costo total: ${total_cost:.7f} USD")

    # --- 5. Latencias SOLO de llamadas exitosas ---
    latencies = [e.get("latency_ms", 0.0) for e in events if e.get("success")]

    # statistics.quantiles necesita al menos 2 datos.
    if len(latencies) >= 2:
        # n=100 devuelve 99 cortes: q[49] = p50, q[94] = p95
        q = statistics.quantiles(latencies, n=100)
        p50, p95 = q[49], q[94]
        print(f"Latencia exitosa p50: {p50:.2f} ms · p95: {p95:.2f} ms")
    elif len(latencies) == 1:
        # Con un solo dato, p50 = p95 = ese dato.
        print(f"Latencia exitosa (única muestra): {latencies[0]:.2f} ms")
    else:
        print("Latencia exitosa: N/A (no hay llamadas exitosas)")

    # --- 6. % de llamadas con fallback ---
    with_fallback = sum(1 for e in events if e.get("fallback"))
    pct = with_fallback / len(events) * 100
    print(f"Fallback: {pct:.1f}% ({with_fallback}/{len(events)})")

    # --- 7. Conteo por proveedor ---
    by_provider = Counter(e.get("provider", "desconocido") for e in events)
    resumen = ", ".join(f"{prov}={count}" for prov, count in by_provider.most_common())
    print(f"Por proveedor: {resumen}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
