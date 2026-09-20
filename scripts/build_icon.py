#!/usr/bin/env python
"""
Gera saci/saci.ico a partir do mesmo desenho usado no ícone da bandeja
(saci.app._desenhar_icone) — sem arquivo de imagem externo no repositório,
o ícone do executável e o da bandeja nunca podem ficar dessincronizados.

Cor usada: o vermelho do gorro (_COR_CRITICO), que é a cor "de identidade"
do Saci — o ícone do .exe não muda de cor com o status, só o da bandeja.

Uso:
    python scripts/build_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from saci.app import _COR_CRITICO, _desenhar_icone  # noqa: E402

# Windows usa o maior disponível para o Explorer/barra de tarefas e os
# menores para a barra de título e atalhos — incluir todos evita que o
# SO tenha que reamostrar (o que deixa o ícone borrado em telas de alto DPI).
TAMANHOS = [16, 24, 32, 48, 64, 128, 256]

DESTINO = Path(__file__).resolve().parent.parent / "saci" / "saci.ico"


def main() -> int:
    imagens = [_desenhar_icone(_COR_CRITICO, tamanho=t) for t in TAMANHOS]
    imagens[-1].save(
        DESTINO,
        format="ICO",
        sizes=[(t, t) for t in TAMANHOS],
    )
    print(f"Gerado: {DESTINO} ({DESTINO.stat().st_size} bytes, {len(TAMANHOS)} resoluções)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
