"""
Preferências em tempo de execução: perfil ativo e travas manuais.

Guardadas em prefs.json (fora do git) para sobreviverem a reinícios do
servidor. Quem escreve é o seletor do VSCode, o painel ou a CLI; quem lê
é o router, a cada chamada.

Duas coisas distintas:

    profile  — qual perfil usar quando a requisição não pede um
    pin      — travar um (provedor, modelo) específico, ignorando a
               cascata. Útil quando você SABE qual quer usar agora.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFS_PATH = ROOT / "prefs.json"

_lock = threading.Lock()

DEFAULTS = {
    "profile": None,   # None = usa o do .env / o pedido na requisição
    "pin": None,       # {"provider": "groq", "model": "openai/gpt-oss-20b"}
}


def load() -> dict:
    """Lê as preferências. Arquivo ausente ou corrompido cai no padrão."""
    try:
        data = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {**DEFAULTS, **data}
    except Exception:
        pass
    return dict(DEFAULTS)


def save(**changes) -> dict:
    """Grava mudanças. Passar None limpa o campo."""
    with _lock:
        current = load()
        current.update(changes)
        try:
            PREFS_PATH.write_text(
                json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass
        return current


def active_profile(fallback: str) -> str:
    """Perfil escolhido manualmente, se houver; senão o informado."""
    return load().get("profile") or fallback


def pinned() -> tuple[str, str] | None:
    """(provedor, modelo) travado manualmente, se houver."""
    pin = load().get("pin")
    if isinstance(pin, dict) and pin.get("provider") and pin.get("model"):
        return pin["provider"], pin["model"]
    return None


def clear_pin() -> dict:
    return save(pin=None)
