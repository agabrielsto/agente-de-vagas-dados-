# Agente de Vagas

Um script que procura vagas de estágio e júnior em dados e suporte técnico, filtra o que realmente interessa e manda o resumo no Telegram todo fim de dia. Roda sozinho no GitHub Actions, então não precisa de servidor nem de deixar o computador ligado.

## Como funciona

1. **Busca:** consulta o Google (via SerpAPI) nos sites de vagas configurados, olhando só os resultados das últimas 24 horas.
2. **Filtro:** manda os resultados para a OpenAI, que descarta vagas pleno/sênior, páginas genéricas de busca e duplicatas.
3. **Entrega:** envia a lista final para o seu chat no Telegram.

Se a OpenAI estiver fora do ar ou sem crédito, o script manda os resultados sem triagem, para você não ficar sem nada. Se a busca ou o Telegram falharem, o job fica vermelho na aba Actions com o motivo no log.

## Sites e áreas pesquisados

Vagas Pra Jr, Viu Uma Vaga, Grupo de Vagas, Cia de Estágios, Indeed, LinkedIn Jobs, Glassdoor e Gupy.

Áreas: análise, ciência e engenharia de dados, banco de dados, BI e suporte N1/N2.

Para mudar sites ou cargos, edite `SITES_ALVO` e `CARGOS_ALVO` no começo do `agente_vagas_custom.py`.

## Como usar

### 1. Faça um fork ou clone do repositório

O workflow precisa ficar em `.github/workflows/vagas.yml`, e o `agente_vagas_custom.py` e o `requirements.txt` na raiz.

### 2. Crie as chaves

| Secret | Onde conseguir |
|---|---|
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) (a API é paga à parte do ChatGPT) |
| `SERPAPI_KEY` | [serpapi.com](https://serpapi.com/) (o plano gratuito tem um limite mensal de buscas) |
| `TELEGRAM_BOT_TOKEN` | Converse com o [@BotFather](https://t.me/BotFather) e crie um bot |
| `TELEGRAM_CHAT_ID` | Mande uma mensagem para o seu bot e abra `https://api.telegram.org/bot<TOKEN>/getUpdates` |

Não esqueça de mandar `/start` para o seu bot, senão ele não consegue te escrever.

### 3. Cadastre os secrets

No repositório: **Settings → Secrets and variables → Actions → New repository secret**. Os nomes precisam ser exatamente os da tabela acima.

### 4. Rode

Vá em **Actions → Agente Diário de Vagas → Run workflow** para testar na hora. Depois disso, o agendamento cuida do resto.

## Horário de execução

O horário fica no `cron` do `vagas.yml` e o GitHub usa UTC. Para receber às 20h no horário de Brasília, use:

```yaml
cron: '0 23 * * *'
```

O GitHub pode atrasar execuções agendadas em alguns minutos.

## Rodando localmente

```bash
pip install -r requirements.txt

export OPENAI_API_KEY=...
export SERPAPI_KEY=...
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...

python agente_vagas_custom.py
```

## Custos

Cada execução faz 3 buscas na SerpAPI e uma chamada ao `gpt-4o-mini`, então o gasto com a OpenAI é de centavos por mês. O que costuma limitar é a cota gratuita da SerpAPI.

## Tecnologias

Python, SerpAPI, OpenAI API, Telegram Bot API e GitHub Actions.
