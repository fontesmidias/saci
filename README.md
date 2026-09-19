# LLM Router

Cascata de fallback entre provedores de LLM **gratuitos**. Se um provedor
estoura a cota (429), cai (5xx) ou remove um modelo (404/410), o router
passa automaticamente para o próximo — sem intervenção.

Inspirado no [awesome-ai-free-tiers](https://github.com/4pixeltechBR/awesome-ai-free-tiers),
mas com uma diferença central: **nenhum modelo entra na configuração sem
ter respondido a uma chamada real**. Catálogos publicados (inclusive o
daquele repositório) listam modelos que retornam 404 ou 410 na prática.

## Instalação

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

Preencha o `.env` com suas chaves. Ele está no `.gitignore` e nunca é commitado.

### Onde pegar as chaves (todas sem cartão de crédito)

| Provedor | Link | Formato |
|---|---|---|
| Groq | https://console.groq.com/keys | `gsk_...` |
| Google AI Studio | https://aistudio.google.com/apikey | `AIzaSy...` ou `AQ.Ab8...` |
| Mistral | https://console.mistral.ai/ | 32 caracteres |
| NVIDIA NIM | https://build.nvidia.com/ | `nvapi-...` |
| OpenRouter | https://openrouter.ai/keys | `sk-or-v1-...` |

## Uso

```powershell
py ask.py "o que e um indice em banco de dados"

py ask.py -p code "funcao Python que valida CPF"
py ask.py -p plan "como estruturar um sistema de RH multi-empresa"

py ask.py -v -p code "refatore isso"     # mostra qual provedor atendeu
py ask.py --status                       # testa todos os provedores
py ask.py --profiles                     # lista os perfis

type arquivo.py | py ask.py -p code "adicione testes:"
```

### Perfis

| Perfil | Para quê | Primeiro da fila |
|---|---|---|
| `code` | gerar/refatorar código | Groq `gpt-oss-120b` (~2s) |
| `plan` | arquitetura, decisões, quebra de tarefas | Groq `gpt-oss-120b` (~5s) |
| `agent` | Cline/Continue — prompts grandes | Mistral `codestral-latest` |
| `fast` | perguntas rápidas | Groq `gpt-oss-20b` (~1s) |
| `long` | textos longos, contexto grande | Google `gemini-3.6-flash` |
| `pt` | português corporativo, documentos | Google `gemini-3.6-flash` |

## Servidor local (para extensões do VSCode)

Expõe o router como uma API compatível com a OpenAI, para plugar em
Cline, Continue, Aider e afins.

```powershell
llm-on       # liga (fica em segundo plano via PM2)
llm-status   # mostra estado + testa provedores
llm-usage    # consumo e cota restante por provedor
llm-logs     # logs ao vivo (Ctrl+C sai)
llm-off      # desliga
```

Com o PM2 você pode fechar o terminal: o servidor continua rodando e
reinicia sozinho se cair.

### Configuração na extensão

| Campo | Valor |
|---|---|
| Base URL | `http://127.0.0.1:8000/v1` |
| API Key | qualquer coisa (não é verificada) |
| Model | `router-code`, `router-plan`, `router-agent`, `router-fast`, `router-long` ou `router-pt` |

Cada perfil aparece como um "modelo" na extensão. A resposta traz um campo
extra `x_router` dizendo qual provedor de fato atendeu e em quanto tempo.

**Roteamento por tamanho:** prompts acima de ~24k caracteres são promovidos
automaticamente para o perfil `agent`. O Groq rejeita requisições grandes
com HTTP 413, então pular direto para quem aguenta o volume evita gastar
uma tentativa fadada ao erro. Isso vale mesmo se o Model ID for outro.

> O servidor escuta só em `127.0.0.1` e **não exige autenticação**.
> Não o exponha na rede sem antes adicionar uma.

### Como biblioteca

```python
from llmrouter import LLMRouter

router = LLMRouter(profile="code")
r = router.ask("funcao que valida CNPJ")

print(r.content)
print(r.provider, r.model, r.latency)   # quem atendeu
print(r.attempts)                        # quem falhou antes
```

## Monitoramento de consumo

```powershell
llm-usage
```

Mostra, por provedor, quantas chamadas e tokens foram gastos hoje e quanto
resta da cota — mais o endpoint `http://127.0.0.1:8000/usage` (JSON) enquanto
o servidor estiver no ar.

Há duas fontes de dado, e a saída diz qual está sendo usada:

| Provedor | Fonte | O que sabemos |
|---|---|---|
| Groq | `[oficial]` | headers: req e tokens restantes + quando reseta |
| Mistral | `[oficial]` | headers: req e tokens restantes por minuto |
| OpenRouter | endpoint | `/v1/key` informa uso acumulado |
| Google | `[estimado]` | não informa nada — contamos localmente |
| NVIDIA | `[estimado]` | não informa nada — contamos localmente |

### Troca automática ao esgotar

Quando um provedor passa de 95% da cota, ele vai para o **fim** da fila em
vez de ser tentado primeiro. Não é removido: se a cota tiver resetado, ele
ainda é tentado como último recurso.

O histórico fica em `usage.db` (SQLite local, fora do git), então sobrevive
a reinícios do servidor.

## Catálogo automático de modelos

Você não mantém lista de modelos. Ao subir, e depois a cada hora, o
servidor faz por provedor:

1. **descobre** — `GET /models`
2. **filtra** — descarta o que não é chat (embedding, TTS, imagem, guard…)
3. **sonda** — uma chamada mínima em cada modelo *novo*, uma vez só:
   `200` ok · `402/403` pago · `404/410` removido · `429` sem cota agora
4. **guarda** — veredito, latência e contexto em `usage.db`
5. **revisa** — sumiu do catálogo 2 vezes → removido; `429` re-testa em 1h;
   `ok` re-testa a cada 14 dias; pago a cada 30

Só o OpenRouter diz no catálogo o que é grátis. Nos outros, "grátis" é o
que respondeu `200` — por isso a sondagem existe.

Um provedor **novo** (chave recém-colada) entra na cascata sozinho: os
perfis aceitam `(provedor, None)` = "os 2 melhores verificados", e todo
provedor de `LLM_ROUTER_ORDER` que o perfil não cita entra no fim.

```powershell
ask --catalog    # o que foi descoberto, com veredito
ask --refresh    # verificar agora, no terminal
```

Ou no painel: **verificar agora**. Cada modelo mostra o veredito, e só os
`ok` têm o botão **usar**.

## Fuso horário

`LLM_ROUTER_TZ=-3` (São Paulo). O painel mostra o reset como hora de
relógio — *"reseta às 21:00"* — e cada provedor conta o "hoje" pelo seu
próprio ciclo (Groq vira à meia-noite UTC = 21:00 aqui; Google, à
meia-noite do Pacífico = 04:00 aqui).

## Manutenção

Quase nada: o catálogo se revisa sozinho. Se um perfil curado apontar para
um modelo que sumiu, a cascata pula para o próximo; para limpar, edite
`PROFILES` em `llmrouter/providers.py` guiado por `ask --catalog`.

## Estado verificado (19/09/2026)

| Provedor | Status | Latência | Observação |
|---|---|---|---|
| Groq | ✅ | 0.5–2s | Mais rápido e estável |
| Google AI Studio | ✅ | 1.5–24s | Cota alta; `gemini-3.8-flash` dá 503 em pico |
| Mistral | ✅ | 0.5–2s | `codestral-latest` é ótimo para código |
| NVIDIA NIM | ⚠️ | 15–70s | Muitos IDs dão 404/410/503 |
| OpenRouter | ⚠️ | — | Modelos `:free` quase sempre em 429 |
| LLM7.io | ⚠️ | 3s | Sem chave; instável, última rede |
| Hyperbolic | 💳 | — | US$ 1 de crédito — **gasta saldo** |
| Cerebras | ❌ | — | HTTP 402: exige plano pago |
| SiliconFlow | ❌ | — | Cadastro não liberado; removido |

### Modelos descontinuados que listas desatualizadas ainda citam

`gemini-2.5-flash` (404) · `gemini-2.5-pro` (404) · `meta/llama-3.3-70b-instruct`
na NVIDIA (410) · `qwen/qwen3-coder-480b` na NVIDIA (410)

## Nota sobre os modelos gratuitos

Eles têm corte de conhecimento e **não sabem quais LLMs existem hoje** —
ao serem perguntados sobre isso, sugerem modelos já descontinuados. Use-os
para executar tarefas, não para decidir sobre o próprio ecossistema de IA.
