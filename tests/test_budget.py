from __future__ import annotations

import json

from agents import AgentBudget, AgentStep, TraceStep
from agents.react_agent import ReActAgent
from contracts import BUSCAR_TICKET
from core.llm_client import LLMClient
from tests.conftest import FakeProvider, make_response


def step(tokens: int = 100, cost: float = 0.001) -> TraceStep:
    paso = AgentStep(
        pensamiento="Busco el ticket.",
        accion="usar_herramienta",
        herramienta="buscar_ticket",
        argumentos_json='{"ticket_id": "T-1042"}',
        respuesta=None,
    )
    return TraceStep(paso, {"estado": "abierto"}, tokens, cost, 10.0)


def test_defaults_match_slide():
    budget = AgentBudget()
    assert (budget.max_pasos, budget.max_tokens, budget.max_usd, budget.max_segundos) == (
        6,
        12_000,
        0.02,
        45,
    )


def test_not_exhausted_with_room():
    assert AgentBudget().exhausted([step()], elapsed_s=1) is None


def test_max_pasos():
    assert AgentBudget(max_pasos=2).exhausted([step(), step()], elapsed_s=0) == "max_pasos"


def test_presupuesto_by_tokens():
    budget = AgentBudget(max_tokens=250)
    assert budget.exhausted([step(tokens=200)], 0) is None
    assert budget.exhausted([step(tokens=200), step(tokens=50)], 0) == "presupuesto"


def test_presupuesto_by_usd():
    budget = AgentBudget(max_usd=0.002)
    assert budget.exhausted([step(cost=0.0015)], 0) is None
    assert budget.exhausted([step(cost=0.0015), step(cost=0.0005)], 0) == "presupuesto"


def test_timeout():
    budget = AgentBudget(max_segundos=10)
    assert budget.exhausted([], elapsed_s=9.9) is None
    assert budget.exhausted([], elapsed_s=10) == "timeout"


def test_exhausted_totals_uses_same_rules():
    budget = AgentBudget(max_pasos=3, max_tokens=100, max_usd=0.01, max_segundos=5)
    assert budget.exhausted_totals(1, 50, 0.001, 1) is None
    assert budget.exhausted_totals(3, 0, 0, 0) == "max_pasos"
    assert budget.exhausted_totals(0, 100, 0, 0) == "presupuesto"
    assert budget.exhausted_totals(0, 0, 0.01, 0) == "presupuesto"
    assert budget.exhausted_totals(0, 0, 0, 5) == "timeout"


# --- Práctica guiada Clase 4: detección de sin_progreso ---------------------------


def test_sin_progreso_dos_pasos_iguales():
    """Misma herramienta con los mismos argumentos dos pasos seguidos → sin_progreso."""
    budget = AgentBudget()
    traza = [step(), step()]
    assert budget.exhausted(traza, elapsed_s=0) == "sin_progreso"


def test_no_sin_progreso_si_argumentos_distintos():
    """Distinto ticket_id → no es sin_progreso."""
    budget = AgentBudget()
    otro = TraceStep(
        AgentStep(
            pensamiento="Busco otro ticket.",
            accion="usar_herramienta",
            herramienta="buscar_ticket",
            argumentos_json='{"ticket_id": "T-1043"}',
            respuesta=None,
        ),
        {"estado": "abierto"},
        100,
        0.001,
        10.0,
    )
    assert budget.exhausted([step(), otro], elapsed_s=0) is None


def test_no_sin_progreso_si_solo_un_paso():
    """Con un solo paso no hay 'dos últimos' que comparar."""
    budget = AgentBudget()
    assert budget.exhausted([step()], elapsed_s=0) is None


def test_react_agent_detecta_sin_progreso(logger, fake_sleep):
    """El agente repite buscar_ticket(T-1042) dos veces y para con sin_progreso."""

    def _step_json(ticket_id: str = "T-1042") -> str:
        return json.dumps(
            {
                "pensamiento": "Necesito ver el ticket.",
                "accion": "usar_herramienta",
                "herramienta": "buscar_ticket",
                "argumentos_json": json.dumps({"ticket_id": ticket_id}),
                "respuesta": None,
            }
        )

    script = [
        make_response("gemini", _step_json("T-1042")),
        make_response("gemini", _step_json("T-1042")),
        # No debería consumir más: el 3er chequeo es antes de la 3ª llamada.
    ]
    provider = FakeProvider("gemini", script)
    client = LLMClient([provider], logger, sleep=fake_sleep)

    agent = ReActAgent(client, [BUSCAR_TICKET])
    result = agent.run("Revisa el T-1042 varias veces")

    assert result.motivo == "sin_progreso"
    assert len(provider.calls) == 2
    assert len(result.traza) == 2
