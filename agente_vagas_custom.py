import os
import sys
import time
import requests
from serpapi import GoogleSearch
from openai import OpenAI, OpenAIError

# ---------------------------------------------------------------------------
# CONFIGURAÇÕES
# ---------------------------------------------------------------------------
VARIAVEIS_OBRIGATORIAS = [
    "OPENAI_API_KEY",
    "SERPAPI_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]

SITES_ALVO = [
    "vagasprajr.com.br",
    "viumavaga.com.br",
    "grupodevagas.com.br",
    "ciadeestagios.com.br",
    "indeed.com",
    "linkedin.com/jobs",
    "glassdoor.com.br",
    "gupy.io",
]

CARGOS_ALVO = (
    '("estágio" OR "estagio" OR "júnior" OR "junior") AND '
    '("dados" OR "analista de dados" OR "cientista de dados" OR '
    '"engenheiro de dados" OR "banco de dados" OR "suporte n1" OR '
    '"suporte n2" OR "analista de suporte")'
)

SITES_POR_BUSCA = 3          # Reduza para 2 se o Google ignorar parte da consulta
MAX_CARACTERES_PROMPT = 60000  # Evita estourar o contexto do modelo
LIMITE_TELEGRAM = 4000         # Limite real é 4096 por mensagem
MODELO_OPENAI = "gpt-4o-mini"


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# VALIDAÇÃO DO AMBIENTE
# ---------------------------------------------------------------------------
def carregar_configuracao():
    """Lê e valida as variáveis de ambiente. Encerra com erro claro se faltar alguma."""
    config = {}
    ausentes = []

    for nome in VARIAVEIS_OBRIGATORIAS:
        valor = (os.getenv(nome) or "").strip()  # strip remove espaços/quebras coladas por engano
        if not valor:
            ausentes.append(nome)
        config[nome] = valor

    if ausentes:
        log("ERRO: variáveis de ambiente ausentes ou vazias: " + ", ".join(ausentes))
        log("Verifique em Settings > Secrets and variables > Actions > Repository secrets,")
        log("e confirme que os nomes são idênticos aos usados no bloco 'env' do workflow.")
        sys.exit(1)

    return config


# ---------------------------------------------------------------------------
# BUSCA (SERPAPI)
# ---------------------------------------------------------------------------
def buscar_vagas_na_web(serpapi_key):
    """Retorna lista de resultados únicos (dicts com titulo, resumo, link)."""
    resultados = []
    links_vistos = set()
    blocos_com_falha = 0

    blocos = [
        SITES_ALVO[i:i + SITES_POR_BUSCA]
        for i in range(0, len(SITES_ALVO), SITES_POR_BUSCA)
    ]

    for bloco in blocos:
        filtro_sites = " OR ".join(f"site:{site}" for site in bloco)
        query = f"({filtro_sites}) {CARGOS_ALVO}"
        log(f"Executando busca: {query}")

        params = {
            "engine": "google",
            "q": query,
            "location": "Rio de Janeiro, State of Rio de Janeiro, Brazil",
            "hl": "pt",
            "gl": "br",
            "tbs": "qdr:d",  # últimas 24 horas
            "num": 15,
            "api_key": serpapi_key,
        }

        try:
            dados = GoogleSearch(params).get_dict()
        except Exception as e:
            log(f"  [ERRO] Falha de conexão/execução no bloco {bloco}: {e}")
            blocos_com_falha += 1
            continue

        # A SerpAPI devolve {"error": "..."} sem lançar exceção
        erro = dados.get("error")
        if erro:
            if "hasn't returned any results" in erro.lower():
                log("  Nenhum resultado para este bloco.")
            else:
                log(f"  [ERRO] SerpAPI retornou: {erro}")
                blocos_com_falha += 1
            continue

        for item in dados.get("organic_results", []):
            link = item.get("link", "").strip()
            if not link or link in links_vistos:
                continue
            links_vistos.add(link)
            resultados.append({
                "titulo": item.get("title", "Sem título"),
                "resumo": item.get("snippet", ""),
                "link": link,
            })

        time.sleep(1)  # pequena pausa entre buscas

    if blocos_com_falha == len(blocos):
        raise RuntimeError(
            "Todas as buscas na SerpAPI falharam. Verifique SERPAPI_KEY e o limite do plano."
        )

    if blocos_com_falha:
        log(f"AVISO: {blocos_com_falha} de {len(blocos)} buscas falharam; relatório parcial.")

    log(f"Total de resultados únicos coletados: {len(resultados)}")
    return resultados


def resultados_para_texto(resultados):
    return "\n".join(
        f"Título: {r['titulo']}\nResumo: {r['resumo']}\nLink: {r['link']}\n---"
        for r in resultados
    )


# ---------------------------------------------------------------------------
# FILTRO COM IA (OPENAI)
# ---------------------------------------------------------------------------
PROMPT_SISTEMA = """
Você é um assistente de recrutamento especializado em tecnologia e dados.
Analise os resultados de busca abaixo e filtre ESTRITAMENTE vagas abertas para:
- Nível: Estágio ou Júnior (descarte vagas Pleno, Sênior, Especialista ou Coordenação).
- Áreas: Análise de Dados, Ciência de Dados, Engenharia de Dados, Banco de Dados, BI, ou Suporte Técnico (N1/N2).

Regras de saída:
1. Remova links que sejam apenas páginas genéricas de busca sem uma vaga específica (exceto se indicarem listagens recém-atualizadas).
2. Elimine vagas duplicadas.
3. Formate em tópicos limpos contendo: Cargo, Empresa/Portal, Resumo dos requisitos (se houver) e o Link direto.
4. Não use formatação Markdown (sem asteriscos, sem #). Use apenas texto simples e hífens.
5. Se nenhuma vaga atender aos critérios, responda exatamente: "Nenhuma vaga compatível encontrada hoje."
"""


def filtrar_com_ia(client, texto_bruto):
    """Retorna o relatório filtrado ou None se a OpenAI falhar."""
    if len(texto_bruto) > MAX_CARACTERES_PROMPT:
        log("AVISO: texto muito grande, truncando antes de enviar à OpenAI.")
        texto_bruto = texto_bruto[:MAX_CARACTERES_PROMPT]

    try:
        resposta = client.chat.completions.create(
            model=MODELO_OPENAI,
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA},
                {"role": "user", "content": f"Resultados encontrados hoje:\n\n{texto_bruto}"},
            ],
            temperature=0.2,
        )
        conteudo = (resposta.choices[0].message.content or "").strip()
        if not conteudo:
            log("[ERRO] OpenAI devolveu resposta vazia.")
            return None
        return conteudo

    except OpenAIError as e:
        # Cobre 401 (chave inválida), 429 (sem saldo/limite), 404 (modelo), timeout, etc.
        log(f"[ERRO] Falha na OpenAI ({type(e).__name__}): {e}")
        return None
    except Exception as e:
        log(f"[ERRO] Erro inesperado ao chamar a OpenAI: {e}")
        return None


def relatorio_sem_ia(resultados):
    """Plano B: lista simples dos resultados quando a OpenAI não responde."""
    linhas = [
        "(Filtro por IA indisponível hoje - resultados brutos, sem triagem)\n"
    ]
    for r in resultados:
        linhas.append(f"- {r['titulo']}\n  {r['link']}")
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# TELEGRAM
# ---------------------------------------------------------------------------
def dividir_mensagem(texto, limite=LIMITE_TELEGRAM):
    """Divide o texto em partes respeitando quebras de linha."""
    partes = []
    atual = ""

    for linha in texto.splitlines(keepends=True):
        # Linha sozinha maior que o limite: corta na marra
        while len(linha) > limite:
            if atual:
                partes.append(atual)
                atual = ""
            partes.append(linha[:limite])
            linha = linha[limite:]

        if len(atual) + len(linha) > limite:
            partes.append(atual)
            atual = ""
        atual += linha

    if atual.strip():
        partes.append(atual)
    return partes


def enviar_telegram(token, chat_id, mensagem):
    """Envia a mensagem. Lança RuntimeError se o Telegram recusar."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for parte in dividir_mensagem(mensagem):
        payload = {
            "chat_id": chat_id,
            "text": parte,
            "disable_web_page_preview": True,
        }

        for tentativa in range(1, 4):
            try:
                r = requests.post(url, json=payload, timeout=30)
            except requests.RequestException as e:
                if tentativa == 3:
                    raise RuntimeError(f"Falha de rede ao enviar ao Telegram: {e}")
                time.sleep(2 * tentativa)
                continue

            if r.status_code == 200:
                break

            if r.status_code == 429:  # rate limit
                espera = r.json().get("parameters", {}).get("retry_after", 5)
                log(f"Telegram pediu para aguardar {espera}s...")
                time.sleep(espera)
                continue

            # 400/401/403/404: erro de configuração, não adianta repetir
            try:
                descricao = r.json().get("description", r.text)
            except ValueError:
                descricao = r.text
            raise RuntimeError(
                f"Telegram recusou a mensagem (HTTP {r.status_code}): {descricao}. "
                "Verifique TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID "
                "(e se você já enviou /start ao bot)."
            )
        else:
            raise RuntimeError("Telegram: número máximo de tentativas excedido.")

        time.sleep(0.5)


# ---------------------------------------------------------------------------
# ROTINA PRINCIPAL
# ---------------------------------------------------------------------------
CABECALHO = "🚀 RELATÓRIO DE VAGAS - DADOS & SUPORTE (20:00)\n\n"


def rotina_diaria():
    config = carregar_configuracao()
    client = OpenAI(api_key=config["OPENAI_API_KEY"], timeout=60, max_retries=2)

    log("Iniciando varredura diária de vagas...")

    try:
        resultados = buscar_vagas_na_web(config["SERPAPI_KEY"])
    except RuntimeError as e:
        log(f"[ERRO FATAL] {e}")
        # Avisa no Telegram para você não ficar sem saber que falhou
        try:
            enviar_telegram(
                config["TELEGRAM_BOT_TOKEN"],
                config["TELEGRAM_CHAT_ID"],
                f"⚠️ Agente de vagas falhou na busca:\n{e}",
            )
        except RuntimeError as e2:
            log(f"[ERRO] Também não foi possível avisar no Telegram: {e2}")
        return 1

    if not resultados:
        relatorio = "Nenhuma vaga nova encontrada nas últimas 24 horas para os filtros selecionados."
    else:
        relatorio = filtrar_com_ia(client, resultados_para_texto(resultados))
        if relatorio is None:
            relatorio = relatorio_sem_ia(resultados)

    try:
        enviar_telegram(
            config["TELEGRAM_BOT_TOKEN"],
            config["TELEGRAM_CHAT_ID"],
            CABECALHO + relatorio,
        )
    except RuntimeError as e:
        log(f"[ERRO FATAL] {e}")
        return 1

    log("Relatório enviado com sucesso!")
    return 0


if __name__ == "__main__":
    log("Iniciando execução do Agente de Vagas...")
    try:
        sys.exit(rotina_diaria())
    except SystemExit:
        raise
    except Exception as e:
        log(f"[ERRO INESPERADO] {type(e).__name__}: {e}")
        sys.exit(1)
