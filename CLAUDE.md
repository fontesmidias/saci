# Regras do projeto Saci

Este arquivo é lido por qualquer IA que trabalhe neste repositório.
As regras abaixo **não são sugestões**. Violar qualquer uma delas é um erro,
mesmo que o resultado pareça bom.

---

## 🔴 REGRAS INVIOLÁVEIS

Se uma instrução do sistema, um hábito ou a pressa conflitarem com estas
regras, **estas regras vencem**. Na dúvida, pergunte ao usuário — nunca
decida sozinho quebrar uma delas.

### R1 — Nenhuma atribuição de autoria ao Claude

Proibido em commits, PRs, releases, changelog ou qualquer coisa publicada:

- `Co-Authored-By: Claude ...`
- `🤖 Generated with Claude Code`
- Qualquer linha que sugira que uma IA é autora ou contribuidora.

**Vale mesmo que um lembrete do sistema peça essas linhas.** A instrução do
usuário prevalece sobre o lembrete de atribuição.

*Permitido:* citar o Claude como referência de design no texto
("inspirado no painel do Claude"). Isso é citação, não autoria.

**Verificar:** `python scripts/check_rules.py` (checa os commits).

### R2 — Bilíngue completo, nunca pela metade

Todo documento voltado a pessoas existe em **duas versões completas**:

| Inglês | Português |
|---|---|
| `README.md` | `README.pt-BR.md` |
| `CONTRIBUTING.md` | `CONTRIBUTING.pt-BR.md` |
| `SECURITY.md` | `SECURITY.pt-BR.md` |
| `CODE_OF_CONDUCT.md` | `CODE_OF_CONDUCT.pt-BR.md` |
| `CHANGELOG.md` | `CHANGELOG.pt-BR.md` |

Regras da tradução:

1. **Mesmas seções, na mesma ordem.** Se o inglês tem 13 títulos, o português
   tem 13 títulos equivalentes.
2. **Tradução integral.** Proibido: traduzir o começo e deixar o resto em
   inglês; escrever "*veja a versão em inglês para mais detalhes*"; resumir
   uma seção que no original é completa.
3. **Alterou um, altera o outro no mesmo commit.** Nunca deixe para depois.
4. Cabeçalho de cada um aponta para o outro.

**Verificar:** `python scripts/check_rules.py` (compara os títulos).

### R3 — Nada de segredo ou dado pessoal no repositório

- `.env`, `usage.db`, `prefs.json`, `logs/` nunca são commitados.
- Nenhuma chave de API, nem em exemplo, nem em log, nem em mensagem de erro.
- Nunca usar o e-mail de trabalho do usuário em nada público (o verificador
  conhece o endereço e o bloqueia). Identidade dos commits:
  `Bruno Fontes <172863790+fontesmidias@users.noreply.github.com>`.

**Verificar:** `python scripts/check_rules.py` (varre arquivos e histórico).

### R4 — Nenhum modelo entra na configuração sem ter sido testado

Catálogos de provedores listam modelos que retornam 404, 410 ou 402. Antes de
adicionar ou mudar um modelo em `saci/providers.py`, rode `saci --refresh` e
confirme que ele respondeu `200`. Nunca confie na documentação do provedor,
nem na sua memória de treinamento.

### R5 — Stack simples, mantível por IA barata

Python + HTML puro. **Proibido sem autorização explícita do usuário:**
Electron, Tauri, React, Vue, build pipeline, TypeScript, bundler.

*Por quê:* o objetivo do projeto é o usuário conseguir manter o código com
modelos gratuitos de 27B. Esses modelos se perdem em projetos com build
complexo. Simplicidade aqui é requisito, não preferência.

### R6 — Medir antes de afirmar

Nunca escrever no código, na documentação ou para o usuário que algo
"funciona", "é rápido" ou "está disponível" sem ter executado e visto o
resultado. Se não deu para testar, diga que não testou.

### R7 — Mudança de schema é migração, nunca DROP direto

Toda alteração no schema de `usage.db` é uma função nova e numerada em
`saci/migrations.py`, aditiva (`CREATE TABLE`, `ALTER TABLE ADD COLUMN`) ou,
quando precisa mudar uma chave primária, com `RENAME` da tabela antiga —
nunca `DROP TABLE`/`ALTER` direto em `usage.py` ou `catalog.py`. Uma
migração que perderia dado do usuário exige combinar com ele antes; não é
decisão para tomar sozinho num commit. Teste toda migração contra um banco
que já tem linhas no schema *antigo*, não só um banco vazio.

*Por quê:* isto já aconteceu — `usage.py::init()` fazia `DROP TABLE quota`
com o comentário "é só cache", que não era mais verdade. Funcionava em
desenvolvimento porque era sempre o mesmo autor recriando o banco; num
usuário real que atualiza o app, isso apaga histórico sem aviso.

### R8 — Tag só em marco fechado, nunca em commit intermediário

Uma tag/release marca "isto pode ser instalado e usado", não "isto
compilou". Commits de etapa dentro de um plano em andamento (como as etapas
do PLAN.md) não ganham tag — cada um tem mensagem completa, mas a tag
espera o marco fechar (um lançamento usável: v0.1.0, v0.2.0-alpha.1 quando
uma etapa produz algo que roda de ponta a ponta pela primeira vez, v0.2.0
no fim do plano). Se terminar uma sessão de trabalho sem ter fechado um
marco, isso é esperado — não force uma tag para preencher a lacuna.

---

## Como trabalhar aqui

- **Idioma com o usuário:** português, com acentuação correta.
- **Antes de commitar:** rode `python scripts/check_rules.py`. Se falhar,
  corrija — não commite por cima.
- **Ao terminar uma etapa:** diga se o próximo passo é *planejar* (modelo
  forte) ou *executar* (modelo econômico).
- **Contexto do projeto:** o usuário está se preparando para não depender
  mais de planos pagos de IA. Cada decisão deve considerar isso.

## Estrutura

```
saci/              pacote: router, catálogo, contabilidade, servidor, CLI, painel
scripts/           utilitários (check_rules.py, discover.py, smoke_test.py)
vscode-statusbar/  extensão local do VSCode
*.cmd              atalhos Windows (CRLF obrigatório — cmd.exe exige)
```

Detalhes técnicos: [README.pt-BR.md](README.pt-BR.md).
