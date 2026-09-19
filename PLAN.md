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

## Etapa 4 — Bandeja + janela (`saci/app.py`)

O executável em si. Um processo: servidor (thread) + bandeja + janela.

- [ ] Ícone desenhado em código (`pillow`), sem arquivo externo:
      gorro vermelho; **cinza** quando o servidor está caído, **amarelo**
      acima de 70 % da cota, **vermelho** acima de 90 %
- [ ] Texto do ícone (tooltip) atualizado a cada 30 s: `groq 1% · reseta 21:00`
- [ ] Menu: Abrir painel · Configurações · Perfil ▸ (submenu com os perfis) ·
      Verificar catálogo · Abrir logs · Iniciar com o Windows (alternável) · Sair
- [ ] Janela `pywebview` 1100×780 apontando para `http://127.0.0.1:<porta>/dashboard`
- [ ] **Fechar a janela não encerra o app** — só esconde; sair é pelo menu
- [ ] Segunda instância: detectar (socket na porta) e apenas mostrar a janela
- [ ] Porta: tentar 8000; se ocupada, subir para a próxima livre e gravar a
      escolhida em `prefs.json` (a extensão do VSCode lê de lá)

**Já validado nesta máquina:** `pystray` e `pywebview` disputam o laço
principal no Windows, mas convivem com este padrão — `webview.start()` na
thread principal e `tray.run()` numa thread separada (testado: os dois subiram
e encerraram juntos). Use exatamente essa ordem; invertê-la trava.

## Etapa 5 — Iniciar com o Windows

- [ ] Alternável pelo menu, sem privilégio de administrador
- [ ] Implementação: chave `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- [ ] Desmarcar remove a chave; desinstalar também

## Etapa 6 — Empacotar (`build.py` + `saci.spec`)

- [ ] PyInstaller em modo `--onedir` (abre mais rápido que `--onefile` e o
      antivírus reclama menos), `--windowed` (sem console)
- [ ] Incluir `dashboard.html` e `settings.html` como dados
- [ ] Excluir o que não é usado: `tkinter`, `test`, `unittest`, backends de
      imagem do Pillow que não usamos — meta: **≤ 70 MB**
- [ ] Ícone `.ico` gerado por script a partir do mesmo desenho do pillow
- [ ] Verificar: o `.exe` sobe, a janela abre, uma chamada real responde

## Etapa 7 — Instalador

- [ ] [Inno Setup](https://jrsoftware.org/isinfo.php) (gratuito, gera um `.exe`
      instalador, cria atalhos e entrada em Aplicativos)
- [ ] Instala em `%LOCALAPPDATA%\Programs\Saci` (não pede administrador)
- [ ] Desinstalação: remove o programa; pergunta se apaga `%APPDATA%\Saci`
- [ ] Detectar ausência do WebView2 e oferecer o instalador oficial da Microsoft

**Cuidado:** o `.exe` não será assinado. O Windows SmartScreen vai avisar
("aplicativo não reconhecido") nas primeiras centenas de downloads. Isso
**precisa estar no README**, com o passo "Mais informações → Executar assim
mesmo". Certificado de assinatura custa ~US$ 200/ano — fora do escopo.

## Etapa 8 — Documentação e release

- [ ] README **e** README.pt-BR: seção de instalação reescrita (baixar o `.exe`
      primeiro; instalação por código vira "para desenvolvedores"), aviso do
      SmartScreen, como atualizar e desinstalar
- [ ] CHANGELOG **e** CHANGELOG.pt-BR: mover de *Unreleased* para `0.2.0`
- [ ] CI: job que empacota no Windows e anexa o `.exe` ao release na tag
- [ ] Tag `v0.2.0`, release com o instalador anexado
- [ ] `scripts/check_rules.py` verde antes de cada commit

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
