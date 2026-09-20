# -*- mode: python ; coding: utf-8 -*-
"""
Especificação do PyInstaller para o Saci — o aplicativo de desktop
(bandeja + janela), não o servidor/CLI que já rodam via PM2.

Uso:
    .venv\\Scripts\\python.exe -m PyInstaller saci.spec --noconfirm

Gera dist\\Saci\\Saci.exe (modo --onedir: uma pasta com o .exe e as
dependências ao lado, não um único binário). Escolhido deliberadamente
(ver PLAN.md, Etapa 6):
  - abre mais rápido que --onefile (que descompacta tudo em um
    diretório temporário a cada execução)
  - antivírus reclama menos de uma pasta com muitos arquivos pequenos
    do que de um único .exe gigante que se autoextraí

Meta de tamanho: ≤ 70 MB (medido após o build).
"""

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# dashboard.html e settings.html são lidos em runtime por caminho relativo
# ao pacote (Path(__file__).parent / "dashboard.html" em server.py) — têm
# que ir como dados, não como código.
dados_saci = [
    ("saci/dashboard.html", "saci"),
    ("saci/settings.html", "saci"),
]

a = Analysis(
    ["saci_launcher.py"],
    pathex=["."],
    binaries=[],
    datas=dados_saci,
    hiddenimports=[
        # uvicorn descobre alguns workers/loops por plugin; o modo
        # --onedir do PyInstaller não segue esses imports dinâmicos.
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Nada aqui usa GUI do Tk, nem roda a própria suíte de testes
        # dentro do executável — cada um destes economiza alguns MB.
        # ("distutils" fica de fora da lista: excluí-lo colide com um
        # alias que o próprio setuptools cria para ele no Python 3.14 —
        # "Target module distutils already imported as ExcludedModule" —
        # e o ganho de espaço seria mínimo mesmo.)
        "tkinter",
        "test",
        "unittest",
        "pydoc",
        "doctest",
        # Backends de imagem do Pillow que o ícone (PNG/ICO em memória)
        # não usa. Mantém "PIL.Image", "PIL.ImageDraw", "PIL.IcoImagePlugin"
        # e "PIL.PngImagePlugin" implícitos (o PyInstaller resolve pela
        # cadeia de imports reais; só listamos aqui o que sabemos que
        # NÃO é usado, plugins pesados de formatos que o app não abre).
        "PIL.ImageQt",
        "PIL.ImageTk",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Saci",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX comprime mas dispara mais falsos-positivos de antivírus
    console=False,  # --windowed: sem janela de console atrás do app
    icon="saci/saci.ico",
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Saci",
)
