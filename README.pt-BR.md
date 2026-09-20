# Saci

> **Um roteador de LLMs gratuitas. Quando uma acaba, ele pula para a próxima.**
> *Sempre dá um jeito.* — [English version](README.md)

[![CI](https://github.com/fontesmidias/saci/actions/workflows/ci.yml/badge.svg)](https://github.com/fontesmidias/saci/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.pt-BR.md)
[![Status: beta](https://img.shields.io/badge/status-beta-orange.svg)](CHANGELOG.pt-BR.md)

O Saci é para quem **não pode pagar APIs de LLM** — estudantes, times pequenos,
quem está entre uma assinatura e outra. Ele transforma as camadas gratuitas de
Groq, Google AI Studio, Mistral, NVIDIA NIM, OpenRouter e outros em **um único
endpoint local compatível com a OpenAI** que nunca fica sem resposta:

- **Cascata de fallback, por modelo.** Cota estourada (429), modelo removido
  (404/410), provedor fora do ar (5xx), prompt grande demais (413) — o Saci tenta
  o próximo modelo. Ele controla a cota *por modelo*, porque o Groq conta tokens
  por modelo, não por conta.
- **Cota que você enxerga.** Barras ao vivo, a hora em que cada cota reseta *no
  seu fuso*, e um rótulo honesto em cada número: `oficial` (dos headers do
  provedor) ou `estimado` (nossa contagem local).
- **Um catálogo que se mantém sozinho.** A cada hora o Saci busca a lista de
  modelos de cada provedor, descarta os que não são de chat e sonda cada modelo
  *novo* uma vez. Só o que respondeu `200` com a sua chave entra na cascata.
  Coloque uma chave e o provedor entra sozinho.
- **Funciona com as ferramentas que você já usa.** Verificado com **Cline**
  (VS Code) e **Aider** (terminal). Qualquer coisa que fale a API da OpenAI serve.

O nome vem do [Saci](https://pt.wikipedia.org/wiki/Saci_(folclore)), o travesso de
uma perna só do folclore brasileiro, que sempre dá um jeito.

---

## Começo rápido (Windows)

1. Baixe `Saci-Setup-<versão>.exe` em
   [Releases](https://github.com/fontesmidias/saci/releases) e execute. Não
   precisa de administrador — instala só para o seu usuário.
2. **O Windows vai avisar** que o app é de um publicador não reconhecido
   (SmartScreen — o `.exe` não é assinado digitalmente; veja o
   [motivo](#instalar-atualizar-desinstalar-windows)). Clique em
   **Mais informações → Executar assim mesmo**.
3. Um ícone aparece na bandeja (o gorro vermelho do Saci). Clique nele →
   **Configurações** para colar pelo menos uma chave de API gratuita (veja a
   tabela abaixo) — sem precisar editar arquivo `.env` na mão.
4. Clique no ícone da bandeja de novo → **Abrir painel**.

Pronto, é toda a configuração. Quem quer rodar a partir do código-fonte — para
mexer no próprio Saci, ou em Linux/macOS, onde o instalador ainda não existe —
veja [Rodando a partir do código-fonte](#rodando-a-partir-do-código-fonte-para-desenvolvimento)
mais abaixo.

### Chaves gratuitas (sem cartão de crédito)

| Provedor | Onde pegar a chave | Por que está na cascata |
|---|---|---|
| Groq | https://console.groq.com/keys | Disparado o mais rápido (~0,5 s); 1.000 req/dia |
| Google AI Studio | https://aistudio.google.com/apikey | Maior contexto, 1.500 req/dia |
| Mistral | https://console.mistral.ai/ | O `codestral` é excelente para código |
| NVIDIA NIM | https://build.nvidia.com/ | Modelos abertos grandes (lento, mas grátis) |
| OpenRouter | https://openrouter.ai/keys | Dezenas de modelos `:free` — o único que publica preço |
| SambaNova | https://cloud.sambanova.ai/ | Llama/DeepSeek, 30 RPM |
| Hugging Face | https://huggingface.co/settings/tokens | Modelos abertos serverless |
| LLM7.io | *não precisa de chave* | Último recurso, sem cadastro |

O Hyperbolic também é suportado, mas gasta **crédito pré-pago** — o Saci sinaliza
isso em todos os lugares.

---

## Como usar

Se você instalou pelo `.exe`, as chaves e configurações ficam na tela de
**Configurações** (ícone da bandeja → Configurações), não num arquivo `.env`
— cole uma chave, clique em **Testar**, depois em **Salvar**; entra em vigor
na hora, sem precisar reiniciar nada.

### No Cline, no Aider ou em qualquer cliente OpenAI

| Campo | Valor |
|---|---|
| Base URL | `http://127.0.0.1:8000/v1` |
| API key | qualquer coisa (o servidor é local e não verifica) |
| Modelo | `saci-code` · `saci-plan` · `saci-agent` · `saci-fast` · `saci-long` · `saci-pt` |

Cada "modelo" é um **perfil de tarefa** — uma cascata ordenada para aquele trabalho:

| Perfil | Para quê | Começa por |
|---|---|---|
| `saci-code` | escrever / refatorar código | Groq `gpt-oss-120b`, Mistral `codestral` |
| `saci-plan` | arquitetura, trade-offs | Groq `gpt-oss-120b`, Gemini |
| `saci-agent` | agentes de código (prompts enormes) | Mistral, Gemini — quem aceita requisições do tamanho que dá 413 |
| `saci-fast` | perguntas rápidas | Groq `gpt-oss-20b` |
| `saci-long` | documentos longos | Gemini (contexto de 1M) |
| `saci-pt` | português do Brasil, texto formal | Gemini, Groq |

Prompts acima de ~24 mil caracteres são promovidos para `saci-agent`
automaticamente, seja qual for o modelo pedido — por isso o Cline simplesmente
funciona.

Aider: use um [`~/.aider.conf.yml`](CONTRIBUTING.pt-BR.md) com
`openai-api-base: http://127.0.0.1:8000/v1` e `model: openai/saci-code`.

### No terminal

```powershell
saci "explique índices de banco de dados em uma frase"
saci -p code "função Python que valida CPF"
type app.py | saci -p code "adicione testes:"
saci --usage        # cota por provedor e modelo, horários de reset
saci --catalog      # todos os modelos descobertos e seus vereditos
saci --refresh      # descobrir e sondar agora
```

### O painel e a barra de status

Clique no ícone da bandeja → **Abrir painel** (ou, rodando a partir do
código-fonte, `saci-panel` abre `http://127.0.0.1:8000/dashboard`):

- barra de cota por provedor, **"reseta às 21:00"** com contagem regressiva ao vivo
- todo modelo descoberto com seu veredito — `ok`, `pago`, `removido`,
  `sem cota agora` — e um botão **usar** para fixar um deles
- troca de perfil, "verificar catálogo agora", consumo de RAM do servidor

A pasta `vscode-statusbar/` é uma extensão local minúscula do VS Code: ela mostra
`⚡ groq 1% · 21:00` na barra de status; clicar abre um seletor para trocar de
perfil ou fixar qualquer modelo verificado. Instale copiando a pasta para
`%USERPROFILE%\.vscode\extensions\local.saci-status-0.1.0` e recarregando a janela.

---

## Como o "grátis" é decidido

Esta é a parte que toda "lista de LLMs grátis" erra, então vamos ao ponto:

- **Só o OpenRouter publica preço** na sua lista de modelos.
- Groq, Google, Mistral, NVIDIA e o resto publicam *nomes*. Alguns desses nomes
  devolvem `404`, `410`, `402` ou `403` no instante em que você chama.
- Por isso o Saci **sonda**: uma requisição de três palavras por modelo novo, uma
  única vez. `200` → utilizável. `402/403` → pago, não é testado de novo por 30
  dias. `404/410` → removido. `429` → nova tentativa em uma hora. Os modelos `ok`
  são reconferidos a cada 14 dias, para pegar remoções silenciosas.

O resultado é uma lista que você não escreveu e não mantém — e esse é o objetivo.

## Controle de cota, com honestidade

| Provedor | Fonte | O que sabemos |
|---|---|---|
| Groq, Mistral | **oficial** — headers da resposta | requisições e tokens restantes, hora do reset |
| OpenRouter | oficial — `/v1/key` | uso acumulado |
| Google, NVIDIA, outros | **estimado** — contagem local | chamadas e tokens de hoje contra o limite diário conhecido |

Todo número na interface carrega seu rótulo. Um modelo que passou de 95% da cota
vai para o *fim* da cascata em vez de ser descartado: se a cota resetou desde a
última verificação, ele ainda tem a sua vez.

## Situação (verificada em 19/09/2026)

| Provedor | Funciona | Latência | Observações |
|---|---|---|---|
| Groq | ✅ | 0,3–2 s | 6 modelos de chat verificados; o mais rápido |
| Google AI Studio | ✅ | 1–25 s | Os `gemini-2.5-*` **sumiram** (404), apesar do que as listas dizem |
| Mistral | ✅ | 0,5–2 s | 12 grátis, 2 pagos (`labs-*`), camada gratuita é 1 req/s |
| NVIDIA NIM | ⚠️ | 15–70 s | 46 dos 62 modelos de chat listados devolvem 404/410/503 |
| OpenRouter | ⚠️ | varia | 25 grátis de 419; os `:free` são disputados |
| LLM7.io | ⚠️ | ~3 s | sem chave; saída instável, só como último recurso |
| Hyperbolic | 💳 | — | crédito pré-pago, sinalizado |
| Cerebras | ❌ | — | 402 em conta gratuita |

## Instalar, atualizar, desinstalar (Windows)

| Tarefa | Como |
|---|---|
| Instalar | Rode `Saci-Setup-<versão>.exe` em [Releases](https://github.com/fontesmidias/saci/releases). Instala em `%LOCALAPPDATA%\Programs\Saci` — sem administrador, sem Python, sem PM2, sem terminal. |
| Atualizar | Rode o instalador novo por cima do antigo — ele detecta e substitui a instalação anterior. Seus dados em `%APPDATA%\Saci` (chaves, histórico, catálogo) ficam intactos. |
| Desinstalar | Configurações do Windows → Aplicativos → Saci → Desinstalar. Vai perguntar se você também quer apagar `%APPDATA%\Saci` — diga não se pretende reinstalar depois. |

### Por que o Windows avisa sobre o instalador

O `.exe` não é assinado digitalmente — um certificado de assinatura custa
cerca de US$ 200/ano, fora do escopo de uma ferramenta gratuita feita por uma
pessoa só. Por causa disso, **o Windows SmartScreen vai mostrar "O Windows
protegeu seu PC"** na primeira vez que você (ou qualquer pessoa) executar.
Isso é esperado, não um sinal de que o arquivo foi adulterado:

1. Clique em **Mais informações**.
2. Clique em **Executar assim mesmo**.

Se o Saci não conseguir abrir a janela, provavelmente falta o **Microsoft
Edge WebView2 Runtime** (ele já vem na maioria das máquinas com Windows
10/11 atualizado, então isso é raro) — o instalador detecta isso e oferece a
página oficial de download da Microsoft antes de continuar.

## Planejado

- Aposentar de vez o PM2 e os atalhos `.cmd`, assim que o aplicativo de
  desktop tiver sido testado por mais gente além do autor.
- Inicializador multiplataforma (Linux/macOS ganham atalhos de primeira
  classe e, eventualmente, o próprio aplicativo empacotado).
- Limitador de taxa por modelo, para agentes que disparam requisições em paralelo.

Veja o [CHANGELOG.pt-BR.md](CHANGELOG.pt-BR.md).

## Rodando a partir do código-fonte (para desenvolvimento)

Você não precisa disso para *usar* o Saci — é para contribuir com o próprio
projeto, ou para Linux/macOS, onde o instalador ainda não existe.

```powershell
git clone https://github.com/fontesmidias/saci
cd saci
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
copy .env.example .env        # cole pelo menos uma chave
saci-on                       # servidor em http://127.0.0.1:8000 — fica de pé via PM2
saci-panel                    # painel no navegador
```

O `saci-on` precisa do [PM2](https://pm2.keymetrics.io/) (`npm i -g pm2`). Sem
ele, rode `.venv\Scripts\python.exe server.py` num terminal que você deixe
aberto. Linux/macOS: `python -m saci.server` — os atalhos `.cmd` são só para
Windows.

Para gerar o aplicativo de desktop você mesmo, em vez de baixar de um release:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[desktop,build]"
.venv\Scripts\python.exe -m PyInstaller saci.spec --noconfirm
# dist\Saci\Saci.exe agora roda sozinho

# opcional: gerar o instalador tambem (precisa do Inno Setup 6)
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" saci.iss
# Output\Saci-Setup-<versão>.exe
```

Nesse modo, suas chaves (`.env`), histórico (`usage.db`) e preferências
(`prefs.json`) ficam na pasta do projeto em vez de `%APPDATA%\Saci`, e nunca
são commitados (veja `.gitignore`).

## Como contribuir

O PR mais útil é um provedor que funciona ou um limite que mudou — veja
[CONTRIBUTING.pt-BR.md](CONTRIBUTING.pt-BR.md). Uma regra só: cole a saída da
sondagem. Catálogos mentem.

Notas de segurança em [SECURITY.pt-BR.md](SECURITY.pt-BR.md): as chaves ficam na
sua máquina, o servidor escuta em `127.0.0.1` e não tem autenticação — não o
exponha.

## Licença

[MIT](LICENSE) © Bruno Fontes
