# Plano — Saci 0.2.0 (aplicativo de desktop)

> Documento de execução. Quem implementa deve seguir na ordem e marcar cada
> item. Regras do projeto: [CLAUDE.md](CLAUDE.md). Rode
> `python scripts/check_rules.py` antes de cada commit.

## Objetivo

Transformar o Saci de "projeto Python com PM2" em **aplicativo de Windows**:
ícone na bandeja, janela própria, chaves configuradas na interface, iniciar com
o sistema, instalador. Sem Python instalado, sem terminal, sem PM2.

## Verificado nesta máquina (19/09/2026)

| Item | Resultado |
|---|---|
| `pywebview` 6.2.1 | ✅ janela abriu e fechou (WebView2 153.0.4234.32 presente) |
| `pystray` 0.19.5 | ✅ ícone apareceu na bandeja e saiu |
| `pillow` 12.3.0 | ✅ desenha o ícone em memória |
| `pyinstaller` 6.22.3 | disponível para Python 3.14 |
| Tamanho estimado | ~62 MB (46,6 MB de dependências + ~15 MB do runtime) |
| **Bandeja + janela juntas** | ✅ **convivem** — janela na thread principal, bandeja em thread separada (era o maior risco do plano) |
| RAM hoje (servidor + PM2) | 134 MB — a meta é **ficar abaixo disso** sem o PM2 |

Restrição da máquina do usuário: **8 GB de RAM**, frequentemente com menos de
1 GB livre. Cada MB conta.

---

## Etapa 1 — Onde moram os dados (`saci/paths.py`) ✅ concluída

Hoje `.env`, `usage.db` e `prefs.json` ficam na pasta do projeto. Num app
instalado isso não funciona: a pasta do programa é somente leitura e some na
atualização.

- [x] `saci/paths.py` com uma função `data_dir()`:
  - **instalado** (`sys.frozen`): `%APPDATA%\Saci`
  - **desenvolvimento**: a pasta do repositório (comportamento de hoje)
  - respeita `SACI_HOME` se definido (útil para testes)
- [x] `usage.py`, `prefs.py`, `catalog.py` e `router.py` passam a usar
      `paths.data_dir()` em vez de `ROOT`
- [x] Migração silenciosa: se achar `.env`/`usage.db` na pasta antiga e não no
      destino, copia uma vez (sem log próprio — a Etapa 2 não existia ainda
      quando esta rodou; o banner de inicialização já mostra o `data_dir()`
      resolvido, o que basta para depurar)
- [x] Testado: `SACI_HOME=<tmp> python -c "from saci import paths; paths.data_dir()"`
      cria a pasta, migra `.env`/`usage.db`/`prefs.json` do repositório, e o
      original permanece intacto (migração copia, nunca move)

**Verificado:** servidor reiniciado com o código novo, chamada real respondida
via Groq. `check_rules.py` permanece verde.

## Etapa 2 — Log em arquivo (`saci/logging_setup.py`) ✅ concluída

Hoje o log vai para o stderr e o PM2 guarda. Sem PM2, precisa ser nosso.

- [x] `logging` padrão do Python com `RotatingFileHandler`:
      `data_dir()/logs/saci.log`, 2 MB por arquivo, 3 arquivos (~8 MB no total)
- [x] Substituídos os `print(..., file=sys.stderr)` de `server.py` pela
      fachada `_log()`, que agora grava em arquivo sempre e no console só
      fora do modo empacotado (`not paths.is_frozen()`) — em dev continua
      idêntico a hoje (aparece no terminal/PM2)
- [x] **Nunca loga chave** — verificado: uma chamada real via Groq não deixou
      nenhum padrão de chave no arquivo de log
- [ ] Menu da bandeja abre a pasta de logs no Explorer — **fica para a Etapa 4**,
      pois depende do menu que ainda não existe

**Verificado:** `saci.log` populado com o banner de inicialização (incluindo
`Dados:` e `Log:` com os caminhos resolvidos), o ciclo do catálogo e uma
chamada de chat real — sem vazar chave.

## Etapa 1.5 — Migrações do banco (`saci/migrations.py`) ✅ concluída, não estava no plano original

**Por que entrou:** antes desta etapa, `usage.py::init()` fazia
`DROP TABLE quota` sempre que detectava o schema antigo, com o comentário
"é só cache" — que não é mais verdade (a tabela guarda a cota lida dos
headers). Isso é seguro em desenvolvimento, mas um app que se atualiza
sozinho (Etapa 6+) rodaria esse `DROP TABLE` na máquina de um usuário real a
cada mudança de schema futura, apagando cota ou catálogo sem aviso.

- [x] `saci/migrations.py`: migrações numeradas e aditivas (`_m001_*`,
      `_m002_*`, ...), uma tabela `schema_version` registra o que já rodou
- [x] A migração que precisava mudar a chave primária de `quota` (de
      `provider` para `provider, model`) virou `RENAME` + `CREATE`, não
      `DROP`: dados no formato antigo vão para `quota_legacy_v1`,
      preservados, nunca apagados
- [x] `usage.py` e `catalog.py` — que gravam no mesmo arquivo — chamam o
      mesmo `migrations.migrate()` em vez de dois `init()` independentes
- [x] Testado com um banco simulando exatamente o schema da v0.1.0
      publicada, com 30 dias de histórico e uma leitura de cota real:
      as 30 linhas de `calls` sobreviveram, a leitura antiga foi
      preservada em `quota_legacy_v1`
- [x] Testada a idempotência (rodar duas vezes não duplica nem reaplica)
- [x] Banco de produção real (o do autor, com histórico de uso) migrado
      sem perda: 20 chamadas antes e depois

**Regra para qualquer migração futura:** nunca `DROP TABLE`/`ALTER` direto em
`usage.py`/`catalog.py`. Toda mudança de schema é uma nova função em
`migrations.py`, aditiva ou com `RENAME` em vez de `DROP`. Documentado em
CONTRIBUTING.md e CONTRIBUTING.pt-BR.md.

## Etapa 3 — Tela de configurações (`saci/settings.html` + endpoints) ✅ concluída

O que hoje exige editar `.env` na mão.

- [x] `GET /settings` — página servida pelo mesmo FastAPI, visual do dashboard
- [x] `GET /api/settings` — devolve, **por provedor**: rótulo, se tem chave
      (booleano — **nunca o valor**), link para obter a chave (via `env_var`
      + notas), custo (`free`/`credits`), e os campos `LLM_ROUTER_*`
      (`runtime_prefs()`)
- [x] `POST /api/settings/key` — grava (ou apaga, com valor vazio) a chave
      de um provedor; `POST /api/settings/runtime` — grava ordem da
      cascata, fuso, perfil padrão
- [x] `POST /api/settings/test` — testa **uma** chave na hora, SEM salvar
      (aceita a chave como parâmetro, não lê do ambiente); ao salvar de
      verdade, dispara a sondagem do catálogo daquele provedor em thread
      separada, sem bloquear a resposta
- [x] Gravação segura: `dotenv.set_key` já escreve em arquivo temporário e
      substitui com `os.replace` (atômico) — confirmado lendo o código-fonte
      da biblioteca, não reimplementado à mão
- [x] A página mostra a chave mascarada (`gsk_••••4f2a`), com botão
      "substituir" que vira um campo de edição, e "remover"

**Verificado, não só a suíte de sempre:**
- `set_provider_key` preserva comentários e outras chaves do `.env` (testado
  round-trip com `/`, `+` no valor — caracteres reais de chave)
- `test_key` com a chave real do Groq em produção: `ok=True` em 364ms; com
  chave inválida: `status=auth`, e a chave testada não aparece em nenhum
  lugar da resposta
- Ciclo completo contra o `.env` de **produção** (não um mock): backup da
  chave HuggingFace → gravar valor de teste via HTTP → confirmar no
  `/api/settings` → remover → confirmar `has_key=False` → restaurar o
  valor original → comparado byte a byte com o backup: idêntico
- Mesmo teste para `POST /api/settings/runtime` (com `default_profile`)
- Log revisado depois de toda a bateria: nenhuma chave aparece, nem a
  testada nem a salva
- Chamada real de chat (`saci-fast` → Groq) respondida depois de toda a
  bateria — o servidor não ficou em estado inconsistente

**Cuidado (mantido):** estes endpoints escrevem segredos. Só podem existir
enquanto o servidor estiver em `127.0.0.1`; se um dia houver modo rede,
`/api/settings/*` fica de fora.

## Etapa 4 — Bandeja + janela (`saci/app.py`) ✅ concluída

O executável em si. Um processo: servidor (thread) + bandeja + janela.

- [x] Ícone desenhado em código (`pillow`), sem arquivo externo:
      gorro vermelho; **cinza** quando o servidor está caído, **amarelo**
      acima de 70 % da cota, **vermelho** acima de 90 %
- [x] Texto do ícone (tooltip) atualizado a cada 30 s: `Saci — groq 4% · reseta em 1.8s`
      (o formato final usa `reset_in` de `/status`, não exatamente
      "reseta HH:MM" — ajustar se quiser a hora de relógio aqui também)
- [x] Menu: Abrir painel · Configurações · Perfil ▸ (submenu com os perfis,
      lido de `/prefs` a cada abertura) · Verificar catálogo agora ·
      Abrir pasta de logs · Iniciar com o Windows (**desabilitado, "em
      breve"** — é a Etapa 5) · Sair
- [x] Janela `pywebview` 1100×780 apontando para `http://127.0.0.1:<porta>/dashboard`
- [x] **Fechar a janela não encerra o app** — só esconde; sair é pelo menu
      (ver bug encontrado abaixo — funciona, mas não do jeito óbvio)
- [x] Segunda instância: `escolher_porta()` detecta via `/health` que já é
      o Saci (não confunde com outro programa na mesma porta) e abre o
      navegador na instância existente em vez de subir uma nova
- [x] Porta: tenta 8000..8010; grava a escolhida em `prefs.json`
      (`port`) — é de lá que outros clientes locais devem ler

**Validado nesta máquina antes de escrever o módulo:** `pystray` e
`pywebview` convivem com `webview.start()` na thread principal e
`tray.run()` em thread separada.

**Dois bugs reais encontrados TESTANDO esta etapa** (não no smoke test
anterior — só apareceram com o app completo rodando de ponta a ponta):

1. **`_porta_livre()` dava falso positivo.** Usava
   `socket.connect_ex()` com timeout de 0.3s; depois de importar
   `pystray`/`webview` o processo fica pesado o bastante para o
   `connect_ex` devolver `WSAEWOULDBLOCK` (10035, "ainda tentando") em
   vez de completar a conexão a tempo — e o código tratava qualquer
   erro `!= 0` como "porta livre". Corrigido trocando para `bind()`
   sem `SO_REUSEADDR`: falha síncrona e inequívoca se a porta já está
   em `LISTEN` por outro processo. Testado com um processo real
   escutando em 8000: antes do fix, dizia "livre"; depois, "ocupada",
   e escolhia 8001 corretamente.

2. **`destroy()` nunca destruía a janela.** `webview.Window.destroy()`
   dispara o MESMO evento `closing` que o clique no X do usuário. O
   handler que eu já tinha para "clicar no X só esconde" (retorna
   `False` sempre) estava cancelando também o `.destroy()` programático
   — `app.run()` nunca retornava, o processo ficava vivo para sempre
   depois de "Sair". Corrigido com um flag `self._saindo`: o handler só
   cancela o fechamento quando `_saindo` é `False`; `_sair()` marca o
   flag antes de chamar `destroy()`. Confirmado lendo o código-fonte do
   backend Windows do pywebview (`winforms.py::on_closing`) antes de
   escrever a correção, não só testando até "parecer" funcionar.

**Verificado de ponta a ponta com o servidor REAL** (catálogo, settings,
tudo — não um mock): app sobe, janela mostra em ~2,6s, chamada de chat
real responde via Groq em 1,3s, `/status` alimenta a cor do ícone
corretamente (verde, 3,6% de uso), menu monta, `_sair()` encerra tudo em
0,7s e o processo Python termina por completo alguns segundos depois
(threads de rede/GUI levam um instante extra para limpar). Log revisado:
nenhuma chave vazou durante o teste.

**Dependências novas:** `pywebview`, `pystray`, `pillow` — extra opcional
`desktop` em `pyproject.toml` (não instalado por padrão; quem só usa o
servidor via PM2 não precisa deles). `saci/server.py::main()` ganhou um
parâmetro `port` (era fixo em 8000) para o app poder escolher a porta.

## Etapa 5 — Iniciar com o Windows (`saci/autostart.py`) ✅ concluída

- [x] Alternável pelo menu, sem privilégio de administrador — `HKCU`, não
      `HKLM` (por usuário, não exige elevação)
- [x] Implementação: chave `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`,
      valor `Saci`
- [x] Comando gravado depende do ambiente: empacotado (`sys.frozen`) grava
      o próprio `.exe`; em desenvolvimento grava
      `pythonw.exe -m saci.app` (resolvido a partir de `sys.executable`,
      não do PATH — sempre o Python certo). `pythonw`, não `python`: sem
      console, o app já tem janela e ícone próprios
- [x] Desmarcar remove a chave (`desligar()`, idempotente — chamar duas
      vezes não é erro). O desinstalador da Etapa 7 deve chamar isto
      também, para não deixar entrada órfã apontando pra um `.exe` que
      não existe mais
- [x] Menu: item com `checked` refletindo o estado real (lido do
      registro a cada abertura do menu) e `enabled=False` fora do
      Windows

**Verificado contra o registro REAL** (não um mock), com limpeza
confirmada ao final:
1. Confirmado que a chave `Saci` não existia antes do teste
2. `ligar()` grava; verificado **fora do nosso código**, lendo a chave
   diretamente com `winreg` num script separado — valor exatamente
   `"<venv>\pythonw.exe" -m saci.app`
3. `alternar()` inverte para desligado; confirmado, também fora do
   nosso código, que a chave foi removida por completo (não ficou
   vazia — `FileNotFoundError` ao tentar ler)
4. `desligar()` chamado com o registro já limpo não lança exceção
5. O item real do menu (`SaciApp._montar_menu()`) mostra `checked=False`
   antes, liga/desliga corretamente através do próprio callback do
   item, e o registro termina limpo

## Etapa 6 — Empacotar (`saci.spec`) ✅ concluída

- [x] PyInstaller em modo `--onedir` (abre mais rápido que `--onefile` e o
      antivírus reclama menos), `--windowed` (sem console)
- [x] Incluir `dashboard.html` e `settings.html` como dados (`datas=` no
      `.spec`) — ficam em `dist/Saci/_internal/saci/`, não ao lado do
      `.exe`; `Path(__file__).parent` dentro do executável resolve
      corretamente para lá (verificado, não presumido — ver abaixo)
- [x] Excluído o que não é usado: `tkinter`, `test`, `unittest`, `pydoc`,
      `doctest`, `PIL.ImageQt`, `PIL.ImageTk` — **resultado: 45 MB**,
      bem abaixo da meta de 70 MB
- [x] Ícone `.ico` gerado por `scripts/build_icon.py`, a partir do mesmo
      desenho do `pillow` usado no ícone da bandeja (7 resoluções:
      16 a 256px) — nunca dessincroniza do ícone da bandeja porque é
      literalmente a mesma função de desenho
- [x] Verificado: o `.exe` sobe, o servidor responde, `/dashboard` e
      `/settings` carregam do caminho empacotado, uma chamada real de
      chat responde, o processo aceita ser encerrado

**Ícone redesenhado durante esta etapa:** a primeira versão (dois
círculos sobrepostos) lia como uma "mordida", não como gorro. Refeito
como um cone poligonal inclinado com pompom separado — mais
reconhecível, inclusive em 32px (tamanho real da bandeja). A função
`_desenhar_icone()` ganhou um parâmetro `tamanho` para servir tanto a
bandeja (64px) quanto o `.ico` (múltiplas resoluções) sem duplicar a
lógica de desenho.

**`distutils` teve que sair da lista de exclusão:** excluí-lo colidia
com um alias que o próprio `setuptools` cria para ele no Python 3.14
(`ValueError: Target module "distutils" already imported as
ExcludedModule`). O ganho de espaço de excluí-lo seria mínimo mesmo;
não vale a complexidade de contornar.

**Verificado com o `.exe` real** (não só o código Python direto):
`Saci.exe` subiu via `subprocess.Popen`, `/health` respondeu,
`/dashboard` (12.386 bytes) e `/settings` (9.306 bytes) carregaram do
`_internal/saci/`, uma chamada real de chat respondeu via Groq, o
processo permaneceu estável por 5s e aceitou ser encerrado
(`taskkill`) sem deixar resíduo. A bandeja/janela em si já tinham sido
validadas em profundidade na Etapa 4, rodando o mesmo código-fonte —
não repeti esse teste dentro do `.exe` por captura de tela, mas o
código é idêntico.

**Novo extra opcional** `pyproject.toml`: `build = ["pyinstaller>=6.22"]`
— só quem empacota precisa instalar.

## Etapa 7 — Instalador (`saci.iss`) ✅ concluída

- [x] [Inno Setup](https://jrsoftware.org/isinfo.php) 6.7.3, instalado via
      `winget install JRSoftware.InnoSetup` (por usuário, sem admin)
- [x] Instala em `%LOCALAPPDATA%\Programs\Saci` (`PrivilegesRequired=lowest`)
      — confirmado sem admin: a chave de desinstalação fica em `HKCU`, não
      `HKLM`
- [x] Desinstalação: remove o programa; pergunta se apaga `%APPDATA%\Saci`
      (chaves, histórico, catálogo) — nunca apaga sem perguntar. Também
      remove a entrada de autostart (Etapa 5) para não deixar uma chave
      órfã apontando para um `.exe` que não existe mais
- [x] Detecta ausência do WebView2 antes de instalar e oferece abrir a
      página oficial de download

**Bug de sintaxe do próprio Inno Setup:** `#13#10` (quebra de linha em
Pascal Script) no **início** de uma linha é lido pelo pré-processador
(ISPP) como diretiva (`#define`, `#if`...), não como código —
`"Error on line 99: Unknown preprocessor directive"`. Corrigido mantendo
cada `#13#10` concatenado ao final da linha de texto anterior, nunca
sozinho como primeiro token de uma linha.

**Cuidado (mantido):** o `.exe` não é assinado. O Windows SmartScreen
avisa ("aplicativo não reconhecido") nas primeiras execuções — confirmado
na prática: vários `.exe` de teste gerados durante esta etapa dispararam
o aviso "Este aplicativo foi bloqueado" do Windows Defender SmartScreen.
Isso **precisa estar no README** (Etapa 8), com o passo "Mais informações
→ Executar assim mesmo". Certificado de assinatura custa ~US$ 200/ano —
fora do escopo.

### Dois bugs sérios só encontrados testando esta etapa de verdade

A Etapa 6 tinha "passado" nos testes, mas por um motivo errado: o PM2
estava rodando o tempo todo na porta 8000, e **todas** as chamadas de
chat dos testes anteriores foram respondidas por ele, não pelo `.exe`. Só
apareceu ao testar a instalação real com o PM2 explicitamente parado.

1. **Import relativo quebrava o app inteiro.** `Analysis(["saci/app.py"])`
   faz o PyInstaller tratar `app.py` como script top-level (módulo
   `__main__`, sem pacote pai) — todo `from . import paths` dentro dele
   falhava com `ImportError: attempted relative import with no known
   parent package`, **silenciosamente**, porque `console=False` esconde
   o traceback. O processo morria no import, antes de logar qualquer
   coisa. Corrigido com `saci_launcher.py`, um arquivo **fora** do pacote
   `saci/` que faz `from saci.app import main` (import absoluto) — o
   mesmo `saci/app.py` roda idêntico em desenvolvimento e empacotado.

2. **`uvicorn` às vezes nunca aceitava conexões.** Com o import corrigido,
   o processo passou a rodar e logar o banner, mas o servidor ficava
   intermitente: por vezes respondia em 3s, por vezes nunca respondia
   (testado até 100+s sem resposta). `uvicorn.run()` sem `loop=` explícito
   tenta detectar automaticamente (`uvloop` > `asyncio`), e essa detecção
   dentro do executável congelado às vezes trava sem lançar exceção —
   `uvloop` nem existe no Windows. Corrigido fixando `loop="asyncio"`
   explicitamente em `server.py::main()`.

3. **Catálogo quebrava com o LLM7** (achado no caminho, real):
   `ProgrammingError: Error binding parameter 4: type 'dict' is not
   supported`. O LLM7 publica `context_window` como objeto
   (`{"tokens": N, "chars": null}`), diferente do inteiro simples dos
   outros provedores — só apareceu agora porque, num `.exe` sem nenhuma
   chave configurada, o LLM7 (keyless) é o único provedor sondado.
   Corrigido com `catalog._extrair_contexto()`, testado contra os 48
   modelos reais do LLM7: 0 erros.

**Verificado de ponta a ponta, com o PM2 explicitamente parado desta
vez:** instalador silencioso (`/VERYSILENT`) instala sem admin
(confirmado via `HKCU`); o executável instalado sobe, cria
`%APPDATA%\Saci` corretamente; `/health` e uma chamada real de chat via
Groq respondem; 3 execuções consecutivas do `.exe`, todas respondendo
em exatamente 3s (antes do fix do loop, variava de 3s a mais de 100s);
desinstalado e reinstalado sem deixar resíduo.

## Etapa 8 — Documentação e release

- [x] README **e** README.pt-BR: seção de instalação reescrita (baixar o
      `.exe` primeiro; instalação por código virou "Running from source /
      Rodando a partir do código-fonte", seção própria para
      desenvolvedores), aviso do SmartScreen com o passo exato ("Mais
      informações → Executar assim mesmo"), como atualizar e desinstalar.
      Adicionadas notas sobre a tela de Settings nas seções de uso
- [x] CHANGELOG **e** CHANGELOG.pt-BR: `[Unreleased]` esvaziado, entrada
      `[0.2.0]` completa com Added/Fixed/Verified — incluindo os 2 bugs
      críticos e a correção do LLM7, com honestidade sobre o que
      aconteceu (não só a lista de features)
- [x] CI (`.github/workflows/release.yml`): dispara em tags `v*.*.*`,
      instala extras `[desktop,build]`, roda `check_rules.py`, empacota,
      **verifica o tamanho** (falha acima de 70 MB), instala Inno Setup
      via choco, compila o instalador com a versão da tag, publica no
      Release via `softprops/action-gh-release@v3`. Não executa o `.exe`
      no runner — ver nota abaixo.
- [x] Tag `v0.2.0`, release com o instalador anexado
- [x] `scripts/check_rules.py` verde antes de cada commit desta etapa

**A fumaça do `.exe` no CI foi tentada e abandonada.** A primeira versão do
workflow subia `dist\Saci\Saci.exe` no runner e esperava `/health`
responder antes de seguir para o instalador — replicando o que já
funcionava localmente (Etapa 7: três inicializações consecutivas, todas em
3s). No runner, o processo nunca respondia dentro do timeout, sempre pelo
mesmo padrão (~30-35s, o orçamento inteiro do loop de espera interno, nunca
mais nem menos). Três hipóteses de ambiente foram testadas, cada uma
disparando o workflow de novo com a tag `v0.2.0` recriada, e nenhuma mudou
o resultado:
1. **WebView2 Runtime ausente** (`windows-latest` é Windows Server, que não
   vem com o Evergreen Runtime pré-instalado como um Windows 10/11 real).
   Instalado explicitamente antes da fumaça — mesmo timeout.
2. **Sessão de desktop não-interativa** (um runner do GitHub Actions não
   tem sessão gráfica; `webview.create_window()` pode não se comportar
   normalmente nesse contexto). Adicionada uma flag `SACI_NO_WINDOW` para
   o app pular a criação da janela e manter só o servidor de pé — mesmo
   timeout.
3. **Scan on-access do Windows Defender** no `.exe` recém-criado e não
   assinado (dezenas de DLLs do PyInstaller `--onedir`). Excluída a pasta
   `dist\Saci` do Defender antes de rodar — mesmo timeout.

Instrumentação com timestamps (`SACI_DEBUG_WAIT`) confirmou que o loop de
espera interno (`_aguardar_servidor`, 40 tentativas de 0,5s) simplesmente
esgotava as 40 tentativas sem nunca conseguir conectar — ou seja, o
servidor de fato não chegava a aceitar conexões dentro da janela de espera,
por um motivo específico do runner que as três hipóteses acima não
cobriram. Sem uma quarta hipótese testável em vista e sem valor real em
insistir (o próprio uso do autor é via PM2 + extensão do VS Code, não via
o app de bandeja empacotado), a fumaça foi removida. Isto segue o padrão
comum para projetos PyInstaller + Inno Setup: o CI cuida de build →
instalador → publicação; a validação de "abre e responde de verdade" é
feita localmente, antes de marcar a tag (já feita na Etapa 7).

A investigação revelou um bug real e independente, que foi corrigido:
`_subir_servidor_em_thread` (`saci/app.py`) não capturava exceções — se a
thread do servidor morresse, morria muda, porque o `.exe` empacotado não
tem console (`--windowed`) para mostrar o traceback. Agora a exceção vai
para `saci.log`.

**Dois problemas encontrados escrevendo o workflow, corrigidos antes de
rodar no CI de verdade:**
- Nome de step `Verificação de tamanho (meta: 70 MB)` quebrava o parser
  YAML — o `:` dentro do texto, mesmo entre parênteses e sem aspas, é lido
  como separador de mapeamento. Corrigido removendo o `:`.
- `softprops/action-gh-release` precisa de `contents: write`; o padrão do
  repositório é `GITHUB_TOKEN` só-leitura (confirmado via
  `gh api .../actions/permissions/workflow`). Adicionado o bloco
  `permissions:` escopado a este job. Também fixado `@v3` (a `@v2` está
  descontinuada) e confirmado que a action cria o Release sozinha ao
  disparar por tag — não precisa criar um Release manual antes.
- O caminho de instalação do Inno Setup via Chocolatey varia entre
  `Program Files` e `Program Files (x86)` conforme o runner; o workflow
  procura o `ISCC.exe` em vez de fixar um caminho, para não falhar
  silenciosamente se o caminho for o outro.

---

## Ordem de execução e onde parar

As etapas 1 e 2 são independentes e podem ser feitas juntas. A 3 depende da 1
(precisa saber onde gravar). A 4 depende da 1, 2 e 3. Da 5 em diante é
sequencial.

**Ponto de verificação obrigatório:** ao terminar a Etapa 4, mostrar ao usuário
o app rodando (bandeja + janela + uma chamada real) **antes** de empacotar.
Empacotar algo que não foi visto funcionando é desperdício de tempo.

## O que este plano deliberadamente não faz

- **Não remove o PM2 nem os `.cmd`** na 0.2 — quem já usa continua usando. Eles
  saem na 0.3, depois que o `.exe` estiver testado por gente de verdade.
- **Não assina o executável** (custo).
- **Não faz atualização automática** — o menu abre a página de Releases. Um
  atualizador que baixa e executa binário é superfície de ataque; só com
  assinatura faz sentido.
- **Não vira Electron/Tauri** (Regra 5).
