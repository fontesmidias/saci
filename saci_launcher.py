"""
Ponto de entrada do PyInstaller para o app de desktop.

Existe porque `saci/app.py` usa imports relativos (`from . import
paths`, etc.) — corretos para um módulo dentro do pacote `saci`, mas
inválidos se o PyInstaller o tratar como script top-level (o que faz
quando `Analysis()` aponta direto para `saci/app.py`): nesse caso
`app.py` vira o módulo `__main__` sem pacote pai, e todo `from . import`
falha com "attempted relative import with no known parent package".

Este arquivo fica FORA do pacote `saci/` de propósito, importa
`saci.app` como módulo normal (absoluto) e chama `main()` — assim o
`saci/app.py` continua fazendo parte do pacote de verdade, e o mesmo
código roda idêntico em desenvolvimento (`python -m saci.app`) e
empacotado.

Descoberto testando a Etapa 7 (PLAN.md): o .exe anterior crashava no
import, silenciosamente (console=False esconde o traceback), e os
testes anteriores "passaram" porque conversaram com o servidor de
desenvolvimento (PM2) que estava rodando na mesma porta o tempo todo,
não com o .exe.
"""

from saci.app import main

if __name__ == "__main__":
    main()
