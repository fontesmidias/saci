"""
Saci como aplicativo de desktop: ícone na bandeja + janela própria.

Um processo só: o servidor FastAPI sobe numa thread, a bandeja (`pystray`)
sobe em outra, e a janela (`pywebview`) roda na thread principal — essa
ordem foi validada nesta máquina antes de escrever este módulo (ver
PLAN.md, Etapa 4): inverter trava, porque os dois disputam o laço
principal do Windows.

Fechar a janela (X) não encerra o app — só a esconde. Sair é só pelo
menu da bandeja, ou pelo atalho do sistema para encerrar o processo.

Uso:
    python -m saci.app
"""

from __future__ import annotations

import socket
import threading
import time
import webbrowser

import httpx
import pystray
from PIL import Image, ImageDraw

from . import autostart, paths, prefs
from .logging_setup import setup_logging

_logger = setup_logging()

WINDOW_TITLE = "Saci"
WINDOW_SIZE = (1100, 780)
PORT_RANGE = range(8000, 8011)  # 8000..8010: 11 tentativas antes de desistir

# Cores do ícone. O gorro do Saci é vermelho; cinza = servidor fora do ar.
_COR_OK = (63, 185, 80)      # verde: cota tranquila
_COR_AVISO = (210, 153, 34)  # amarelo: >70% da cota
_COR_CRITICO = (248, 81, 73)  # vermelho: >90% da cota — também o vermelho do gorro
_COR_OFFLINE = (110, 118, 129)  # cinza: servidor fora do ar


# ---------------------------------------------------------------------
# Porta e segunda instância
# ---------------------------------------------------------------------

def _porta_livre(porta: int) -> bool:
    """
    True se ninguém está escutando nessa porta em 127.0.0.1.

    Usa `bind()`, não `connect()`: um `connect_ex` com timeout curto
    pode devolver WSAEWOULDBLOCK (10035) — "ainda tentando", não "porta
    livre" — e isso ficou mais fácil de acontecer depois de importar
    pystray/webview (o processo fica mais pesado para agendar a thread).
    Bug real, encontrado testando a Etapa 4 com uma porta ocupada por
    outro processo. `bind()` sem SO_REUSEADDR falha de forma síncrona e
    inequívoca se a porta já está em uso — é o teste correto aqui (não
    estamos tentando reaproveitar um socket em TIME_WAIT, só perguntar).
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", porta))
        return True
    except OSError:
        return False


def _saci_ja_rodando(porta: int) -> bool:
    """
    A porta está ocupada, mas por NÓS? Confirma via /health, para não
    confundir "outra instância do Saci já rodando" com "outro programa
    qualquer usando essa porta".
    """
    try:
        r = httpx.get(f"http://127.0.0.1:{porta}/health", timeout=1.0)
        return r.status_code == 200 and "profiles" in r.json()
    except Exception:
        return False


def escolher_porta() -> tuple[int, bool]:
    """
    Retorna (porta, ja_rodando). Tenta 8000 primeiro; se ocupada por
    OUTRO Saci, reaproveita. Se ocupada por outra coisa, sobe até achar
    uma livre. A porta escolhida é gravada em prefs.json — é de lá que
    a extensão do VSCode e outros clientes locais devem lê-la.
    """
    for porta in PORT_RANGE:
        if _saci_ja_rodando(porta):
            return porta, True
        if _porta_livre(porta):
            prefs.save(port=porta)
            return porta, False
    raise RuntimeError(
        f"Nenhuma porta livre entre {PORT_RANGE.start} e {PORT_RANGE.stop - 1}."
    )


# ---------------------------------------------------------------------
# Ícone (desenhado em memória — sem arquivo .ico externo)
# ---------------------------------------------------------------------

def _desenhar_icone(cor: tuple[int, int, int], tamanho: int = 64) -> Image.Image:
    """
    O gorro do Saci: um cone inclinado (a silhueta clássica do gorro),
    com um pompom branco no topo. Parametrizado por `tamanho` para
    servir tanto o ícone da bandeja (64px) quanto o `.ico` do
    executável, que precisa de resoluções maiores (ver
    scripts/build_icon.py).
    """
    img = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    e = tamanho / 64  # escala: as coordenadas abaixo foram desenhadas para 64px

    gorro = [
        (16 * e, 58 * e),
        (13 * e, 34 * e),
        (36 * e, 14 * e),   # ponta
        (50 * e, 34 * e),
        (47 * e, 58 * e),
    ]
    d.polygon(gorro, fill=cor)
    d.ellipse((11 * e, 52 * e, 51 * e, 62 * e), fill=cor)                 # aba/base
    d.ellipse((38 * e, 2 * e, 54 * e, 18 * e), fill=(255, 255, 255))      # pompom

    return img


def _cor_para_status(dados: dict | None) -> tuple[int, int, int]:
    """Decide a cor do ícone a partir de GET /status (ver server.py)."""
    if not dados:
        return _COR_OFFLINE
    pct = dados.get("used_pct")
    if pct is None:
        return _COR_OK
    if pct >= 90:
        return _COR_CRITICO
    if pct >= 70:
        return _COR_AVISO
    return _COR_OK


# ---------------------------------------------------------------------
# O aplicativo
# ---------------------------------------------------------------------

class SaciApp:
    def __init__(self, porta: int) -> None:
        self.porta = porta
        self.base_url = f"http://127.0.0.1:{porta}"
        self._janela = None
        self._tray: pystray.Icon | None = None
        self._parar = threading.Event()
        # `destroy()` dispara o MESMO evento `closing` que o clique no X —
        # sem este flag, o handler que esconde a janela no X também
        # cancelaria o destroy() de _sair(), e o app nunca encerraria de
        # verdade. Descoberto testando esta etapa (ver PLAN.md, Etapa 4).
        self._saindo = False

    # --- dados para o menu/ícone -------------------------------------

    def _status(self) -> dict | None:
        try:
            r = httpx.get(f"{self.base_url}/status", timeout=2.0)
            return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    def _prefs(self) -> dict:
        try:
            r = httpx.get(f"{self.base_url}/prefs", timeout=2.0)
            return r.json() if r.status_code == 200 else {}
        except Exception:
            return {}

    # --- ações do menu -------------------------------------------------

    def _mostrar_janela(self) -> None:
        if self._janela is not None:
            self._janela.show()
            self._janela.restore()

    def _abrir_painel(self, *_args) -> None:
        self._mostrar_janela()
        if self._janela is not None:
            self._janela.load_url(f"{self.base_url}/dashboard")

    def _abrir_config(self, *_args) -> None:
        self._mostrar_janela()
        if self._janela is not None:
            self._janela.load_url(f"{self.base_url}/settings")

    def _abrir_logs(self, *_args) -> None:
        import os
        os.startfile(paths.logs_dir())  # noqa: S606 — Windows-only por natureza

    def _verificar_catalogo(self, *_args) -> None:
        try:
            httpx.post(f"{self.base_url}/catalog/refresh", timeout=2.0)
        except Exception as exc:
            _logger.warning("bandeja: falha ao pedir verificação do catálogo: %s", exc)

    def _trocar_perfil(self, nome: str):
        def acao(*_args) -> None:
            try:
                httpx.post(f"{self.base_url}/prefs",
                          json={"profile": nome}, timeout=2.0)
            except Exception as exc:
                _logger.warning("bandeja: falha ao trocar perfil: %s", exc)
        return acao

    def _sair(self, *_args) -> None:
        self._saindo = True  # deixa o handler de "closing" saber que é de verdade
        self._parar.set()
        if self._tray is not None:
            self._tray.stop()
        if self._janela is not None:
            self._janela.destroy()

    def _alternar_autostart(self, *_args) -> None:
        try:
            novo = autostart.alternar()
            _logger.info("bandeja: iniciar com o Windows -> %s", novo)
        except Exception as exc:
            _logger.warning("bandeja: falha ao alternar autostart: %s", exc)

    # --- construção do menu (dinâmico: perfis vêm do servidor) ---------

    def _montar_menu(self) -> pystray.Menu:
        prefs_atuais = self._prefs()
        perfil_ativo = prefs_atuais.get("profile")
        nomes_perfis = [p["profile"] for p in prefs_atuais.get("profiles", [])]

        submenu_perfis = pystray.Menu(
            pystray.MenuItem(
                "auto", self._trocar_perfil(""),
                checked=lambda item: not perfil_ativo, radio=True,
            ),
            *[
                pystray.MenuItem(
                    nome, self._trocar_perfil(nome),
                    checked=lambda item, n=nome: perfil_ativo == n, radio=True,
                )
                for nome in nomes_perfis
            ],
        )

        return pystray.Menu(
            pystray.MenuItem("Abrir painel", self._abrir_painel, default=True),
            pystray.MenuItem("Configurações", self._abrir_config),
            pystray.MenuItem("Perfil", submenu_perfis),
            pystray.MenuItem("Verificar catálogo agora", self._verificar_catalogo),
            pystray.MenuItem("Abrir pasta de logs", self._abrir_logs),
            pystray.MenuItem(
                "Iniciar com o Windows", self._alternar_autostart,
                checked=lambda item: autostart.ligado(),
                enabled=autostart.disponivel(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", self._sair),
        )

    def _loop_bandeja(self) -> None:
        """
        Atualiza ícone e tooltip a cada 30s. Roda na thread da bandeja
        (pystray.Icon.run bloqueia essa thread até .stop()).
        """
        while not self._parar.is_set():
            status = self._status()
            cor = _cor_para_status(status)
            if self._tray is not None:
                self._tray.icon = _desenhar_icone(cor)
                if status and status.get("active"):
                    pct = status.get("used_pct") or 0
                    reset = status.get("reset_in")
                    reset_txt = f" · reseta {reset}" if reset else ""
                    self._tray.title = f"Saci — {status['active']} {pct:.0f}%{reset_txt}"
                elif status is not None:
                    self._tray.title = "Saci — sem provedor configurado"
                else:
                    self._tray.title = "Saci — servidor indisponível"
            self._parar.wait(30)

    def run(self) -> None:
        """
        Ponto de entrada. Bloqueia na thread principal (pywebview) até
        o usuário sair pelo menu.
        """
        self._tray = pystray.Icon(
            "saci", _desenhar_icone(_COR_OFFLINE), "Saci — iniciando…",
            menu=self._montar_menu(),
        )
        threading.Thread(target=self._tray.run, name="saci-tray", daemon=True).start()
        threading.Thread(target=self._loop_bandeja, name="saci-tray-loop", daemon=True).start()

        import webview

        def ao_fechar() -> bool:
            """
            Retornar False cancela o fechamento — só esconde a janela.

            `destroy()` dispara este mesmo evento, então quando `_sair()`
            já pediu para sair de verdade (`self._saindo`), deixamos
            passar (retorna None/True) em vez de cancelar de novo —
            senão o app nunca encerra pelo menu.
            """
            if self._saindo:
                return None
            if self._janela is not None:
                self._janela.hide()
            return False

        self._janela = webview.create_window(
            WINDOW_TITLE, url=f"{self.base_url}/dashboard",
            width=WINDOW_SIZE[0], height=WINDOW_SIZE[1],
        )
        self._janela.events.closing += ao_fechar

        webview.start()  # bloqueia até destroy(); a bandeja segue em paralelo


def _subir_servidor_em_thread(porta: int) -> None:
    from . import server
    threading.Thread(
        target=server.main, kwargs={"port": porta}, name="saci-server", daemon=True,
    ).start()


def _aguardar_servidor(porta: int, tentativas: int = 40) -> bool:
    """Espera até /health responder, ou desiste após ~10s (40 x 0.25s)."""
    for _ in range(tentativas):
        try:
            if httpx.get(f"http://127.0.0.1:{porta}/health", timeout=0.5).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def main() -> None:
    porta, ja_rodando = escolher_porta()

    if ja_rodando:
        _logger.info("Saci já está rodando na porta %s — abrindo o navegador.", porta)
        webbrowser.open(f"http://127.0.0.1:{porta}/dashboard")
        return

    _subir_servidor_em_thread(porta)
    if not _aguardar_servidor(porta):
        _logger.warning("servidor não respondeu a tempo na porta %s; abrindo mesmo assim.", porta)

    SaciApp(porta).run()


if __name__ == "__main__":
    main()
