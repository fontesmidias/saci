# Segurança

*English version: [SECURITY.md](SECURITY.md).*

## O que o Saci faz com as suas chaves de API

- As chaves ficam no **seu** `.env` (e, a partir da 0.2, em `%APPDATA%\Saci`).
  Elas são lidas na hora da requisição e enviadas **somente** ao provedor a que
  pertencem.
- As chaves nunca vão para o log. Mensagens de erro são higienizadas antes de
  serem guardadas ou impressas (`router.py::_scrub`).
- O servidor escuta apenas em `127.0.0.1` e **não tem autenticação**. Não exponha
  a porta 8000 à rede sem colocar um proxy reverso autenticado na frente. Quem
  alcançar essa porta gasta a sua cota.
- A sondagem do catálogo envia um prompt fixo de três palavras a cada modelo
  novo, uma vez. Nada das suas conversas vai para lugar nenhum além do provedor
  que está respondendo àquela conversa.
- O painel, a extensão do VS Code e a CLI falam apenas com o servidor local. Sem
  telemetria, sem chamar casa, sem verificação de atualização na 0.1.

## Relatar uma vulnerabilidade

Por favor, **não abra uma issue pública** para problemas de segurança. Use o
relato privado do GitHub: *Security → Report a vulnerability* no repositório.
Você recebe resposta em até uma semana; correções de problemas confirmados são
publicadas assim que ficam prontas e creditadas no changelog, a menos que você
prefira o contrário.

## Versões com suporte

Apenas o último lançamento recebe correções.
