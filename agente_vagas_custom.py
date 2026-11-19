<<<<<<< HEAD
=======
"""Busca vagas de dados e suporte, filtra com IA e envia o resumo no Telegram."""
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
from __future__ import annotations

import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from openai import OpenAI, OpenAIError
from serpapi import GoogleSearch

<<<<<<< HEAD
logger = logging.getLogger("agente_vagas")
=======
log = logging.getLogger("vagas")
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)

SITES_ALVO = (
    "vagasprajr.com.br",
    "viumavaga.com.br",
    "grupodevagas.com.br",
    "ciadeestagios.com.br",
    "indeed.com",
    "linkedin.com/jobs",
    "glassdoor.com.br",
    "gupy.io",
<<<<<<< HEAD
)

CARGOS_ALVO = (
    '("estágio" OR "estagio" OR "júnior" OR "junior") AND '
    '("dados" OR "analista de dados" OR "cientista de dados" OR '
    '"engenheiro de dados" OR "banco de dados" OR "suporte n1" OR '
    '"suporte n2" OR "analista de suporte")'
)

SITES_POR_BUSCA = 3
LOCALIZACAO = "Rio de Janeiro, State of Rio de Janeiro, Brazil"
FUSO = ZoneInfo("America/Sao_Paulo")

MODELO_OPENAI = "gpt-4o-mini"
LIMITE_PROMPT = 60_000
LIMITE_TELEGRAM = 4_000
TENTATIVAS_TELEGRAM = 3

MSG_SEM_RESULTADO_SERPAPI = "hasn't returned any results"

PROMPT_SISTEMA = """\
Você é um assistente de recrutamento especializado em tecnologia e dados.
Analise os resultados de busca e mantenha apenas vagas abertas para:
- Nível: estágio ou júnior (descarte pleno, sênior, especialista e coordenação).
- Áreas: análise de dados, ciência de dados, engenharia de dados, banco de
  dados, BI ou suporte técnico (N1/N2).
=======
)

# consulta curta: o Google ignora o que passa de ~32 termos
NIVEIS = '("estágio" OR "estagio" OR "júnior" OR "junior")'
LOCAIS = '("Rio de Janeiro" OR "RJ" OR "remoto")'
AREAS = '("dados" OR "suporte n1" OR "suporte n2" OR "analista de suporte")'

# triagem local antes de chamar a OpenAI
NIVEL_OK = re.compile(r"est[aá]gi|j[uú]nior|\bjr\b", re.I)
NIVEL_EXCLUIDO = re.compile(
    r"\b(pleno|s[eê]nior|especialista|coordena\w+|gerente|l[ií]der|head)\b", re.I
)
AREA_OK = re.compile(
    r"dados|\bdata\b|\bbi\b|power\s?bi|\bsql\b|analytics|suporte|help\s?desk|service\s?desk",
    re.I,
)
LOCAL_OK = re.compile(r"rio de janeiro|\brj\b|niter[oó]i|remot[oa]|home\s?office", re.I)
OUTRA_CIDADE = re.compile(
    r"s[aã]o paulo|belo horizonte|curitiba|porto alegre|bras[ií]lia|salvador|recife|"
    r"fortaleza|goi[aâ]nia|florian[oó]polis|campinas|vit[oó]ria|manaus|bel[eé]m",
    re.I,
)
# sem re.I: só siglas em maiúsculo
OUTRA_UF = re.compile(
    r"[,/\-–]\s*(SP|MG|PR|RS|DF|BA|PE|CE|GO|SC|ES|AM|PA|MT|MS|RN|PB|AL|SE|PI|MA|TO|RO|AC|AP|RR)\b"
)

SITES_POR_BUSCA = 3
LOCALIZACAO = "Rio de Janeiro, State of Rio de Janeiro, Brazil"
FUSO = ZoneInfo("America/Sao_Paulo")

MODELO = "gpt-4o-mini"
LIMITE_PROMPT = 60_000
LIMITE_TELEGRAM = 4_000
TENTATIVAS_TELEGRAM = 3

HORA_ENVIO = (20, 0)
JANELA_ESPERA = 45 * 60  # só espera se o horário estiver a menos de 45 min

PROMPT = """\
Você é um assistente de recrutamento especializado em tecnologia e dados.
Analise os resultados de busca e mantenha apenas vagas abertas que atendam
a TODOS os critérios abaixo:
- Nível: estágio ou júnior (descarte pleno, sênior, especialista e coordenação).
- Área: análise de dados, ciência de dados, engenharia de dados, banco de
  dados, BI ou suporte técnico (N1/N2). Descarte qualquer outra área, mesmo
  que seja estágio ou júnior (vendas, marketing, RH, financeiro,
  desenvolvimento de software etc.). Na dúvida, descarte.
- Local: Rio de Janeiro (RJ) ou remoto. Descarte vagas presenciais ou
  híbridas de outras cidades ou estados. Se o local não aparecer no
  resultado, mantenha a vaga e escreva "Local: não informado".
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)

Regras de saída:
1. Remova links que sejam apenas páginas genéricas de busca, sem vaga específica.
2. Elimine duplicatas.
<<<<<<< HEAD
3. Para cada vaga, informe: cargo, empresa ou portal, resumo dos requisitos
   (se houver) e o link direto.
4. Use texto simples, sem Markdown.
5. Se nenhuma vaga atender aos critérios, responda apenas:
=======
3. Use somente o que está nos resultados; não invente empresa, local ou requisitos.
4. Para cada vaga, informe: cargo, empresa ou portal, local, resumo dos
   requisitos (se houver) e o link direto.
5. Use texto simples, sem Markdown.
6. Se nenhuma vaga atender aos critérios, responda apenas:
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
   "Nenhuma vaga compatível encontrada hoje."
"""


class ConfigError(Exception):
    pass


class SearchError(Exception):
    pass


class TelegramError(Exception):
    pass


@dataclass(frozen=True)
class Config:
<<<<<<< HEAD
    openai_api_key: str
=======
    openai_key: str
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
    serpapi_key: str
    telegram_token: str
    telegram_chat_id: str

    @classmethod
    def from_env(cls) -> Config:
<<<<<<< HEAD
        nomes = (
            "OPENAI_API_KEY",
            "SERPAPI_KEY",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
        )
        valores = {nome: os.getenv(nome, "").strip() for nome in nomes}
        ausentes = [nome for nome, valor in valores.items() if not valor]
        if ausentes:
            raise ConfigError(
                "Variáveis de ambiente ausentes: " + ", ".join(ausentes)
            )
=======
        nomes = ("OPENAI_API_KEY", "SERPAPI_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
        valores = {n: os.getenv(n, "").strip() for n in nomes}
        ausentes = [n for n, v in valores.items() if not v]
        if ausentes:
            raise ConfigError("Variáveis de ambiente ausentes: " + ", ".join(ausentes))
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
        return cls(*valores.values())


@dataclass(frozen=True)
class Vaga:
    titulo: str
    resumo: str
    link: str

<<<<<<< HEAD
    def como_texto(self) -> str:
        return f"Título: {self.titulo}\nResumo: {self.resumo}\nLink: {self.link}"


def montar_query(sites: tuple[str, ...]) -> str:
    filtro = " OR ".join(f"site:{site}" for site in sites)
    return f"({filtro}) {CARGOS_ALVO}"
=======
    def texto(self) -> str:
        return f"Título: {self.titulo}\nResumo: {self.resumo}\nLink: {self.link}"


def passa_triagem(vaga: Vaga) -> bool:
    texto = f"{vaga.titulo} {vaga.resumo}"
    if NIVEL_EXCLUIDO.search(texto):
        return False
    if not (NIVEL_OK.search(texto) and AREA_OK.search(texto)):
        return False
    if LOCAL_OK.search(texto):
        return True
    # sem RJ/remoto: só barra se houver outro local explícito
    return not (OUTRA_CIDADE.search(texto) or OUTRA_UF.search(texto))


def montar_query(sites: tuple[str, ...]) -> str:
    filtro = " OR ".join(f"site:{s}" for s in sites)
    return f"({filtro}) {NIVEIS} {LOCAIS} {AREAS}"
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)


def buscar_bloco(api_key: str, sites: tuple[str, ...]) -> list[Vaga]:
    params = {
        "engine": "google",
        "q": montar_query(sites),
        "location": LOCALIZACAO,
        "hl": "pt",
        "gl": "br",
<<<<<<< HEAD
        "tbs": "qdr:d",  # últimas 24 horas
=======
        "tbs": "qdr:d",  # últimas 24h
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
        "num": 15,
        "api_key": api_key,
    }
    try:
        dados = GoogleSearch(params).get_dict()
    except Exception as exc:
        raise SearchError(f"falha ao consultar a SerpAPI: {exc}") from exc

<<<<<<< HEAD
    # A SerpAPI sinaliza problemas no corpo da resposta, sem lançar exceção.
    erro = dados.get("error")
    if erro:
        if MSG_SEM_RESULTADO_SERPAPI in erro.lower():
=======
    # a SerpAPI devolve erro no corpo, sem lançar exceção
    erro = dados.get("error")
    if erro:
        if "hasn't returned any results" in erro.lower():
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
            return []
        raise SearchError(erro)

    return [
<<<<<<< HEAD
        Vaga(
            titulo=item.get("title", "Sem título"),
            resumo=item.get("snippet", ""),
            link=item["link"],
        )
=======
        Vaga(item.get("title", "Sem título"), item.get("snippet", ""), item["link"])
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
        for item in dados.get("organic_results", [])
        if item.get("link")
    ]


def buscar_vagas(api_key: str) -> list[Vaga]:
    blocos = [
        SITES_ALVO[i : i + SITES_POR_BUSCA]
        for i in range(0, len(SITES_ALVO), SITES_POR_BUSCA)
    ]
    vagas: dict[str, Vaga] = {}
    falhas = 0

    for sites in blocos:
<<<<<<< HEAD
        logger.info("Buscando em: %s", ", ".join(sites))
        try:
            encontradas = buscar_bloco(api_key, sites)
        except SearchError as exc:
            logger.warning("Busca falhou para %s: %s", sites, exc)
=======
        log.info("Buscando em: %s", ", ".join(sites))
        try:
            encontradas = buscar_bloco(api_key, sites)
        except SearchError as exc:
            log.warning("Busca falhou para %s: %s", sites, exc)
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
            falhas += 1
            continue
        for vaga in encontradas:
            vagas.setdefault(vaga.link, vaga)

    if falhas == len(blocos):
        raise SearchError("todas as buscas falharam; verifique SERPAPI_KEY e o limite do plano")

<<<<<<< HEAD
    logger.info("%d resultados únicos (%d buscas com falha)", len(vagas), falhas)
    return list(vagas.values())


def filtrar_com_ia(client: OpenAI, vagas: list[Vaga]) -> str | None:
    """Devolve o relatório filtrado, ou None se a OpenAI não responder."""
    texto = "\n---\n".join(vaga.como_texto() for vaga in vagas)[:LIMITE_PROMPT]
    try:
        resposta = client.chat.completions.create(
            model=MODELO_OPENAI,
            temperature=0.2,
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA},
=======
    relevantes = [v for v in vagas.values() if passa_triagem(v)]
    log.info(
        "%d resultados únicos, %d após a triagem (%d buscas com falha)",
        len(vagas), len(relevantes), falhas,
    )
    return relevantes


def filtrar_com_ia(client: OpenAI, vagas: list[Vaga]) -> str | None:
    texto = "\n---\n".join(v.texto() for v in vagas)[:LIMITE_PROMPT]
    try:
        resposta = client.chat.completions.create(
            model=MODELO,
            temperature=0,
            messages=[
                {"role": "system", "content": PROMPT},
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
                {"role": "user", "content": f"Resultados encontrados hoje:\n\n{texto}"},
            ],
        )
    except OpenAIError as exc:
<<<<<<< HEAD
        logger.error("Falha na OpenAI (%s): %s", type(exc).__name__, exc)
=======
        log.error("Falha na OpenAI (%s): %s", type(exc).__name__, exc)
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
        return None

    conteudo = (resposta.choices[0].message.content or "").strip()
    if not conteudo:
<<<<<<< HEAD
        logger.error("A OpenAI devolveu uma resposta vazia")
=======
        log.error("A OpenAI devolveu uma resposta vazia")
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
        return None
    return conteudo


def relatorio_sem_filtro(vagas: list[Vaga]) -> str:
<<<<<<< HEAD
    itens = "\n".join(f"- {vaga.titulo}\n  {vaga.link}" for vaga in vagas)
=======
    itens = "\n".join(f"- {v.titulo}\n  {v.link}" for v in vagas)
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
    return f"Filtro por IA indisponível; resultados sem triagem:\n\n{itens}"


def dividir_mensagem(texto: str, limite: int = LIMITE_TELEGRAM) -> list[str]:
    partes: list[str] = []
    atual = ""
    for linha in texto.splitlines(keepends=True):
<<<<<<< HEAD
        while len(linha) > limite:
=======
        while len(linha) > limite:  # linha maior que o limite
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
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


def enviar_parte(url: str, chat_id: str, texto: str) -> None:
<<<<<<< HEAD
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "disable_web_page_preview": True,
    }
=======
    payload = {"chat_id": chat_id, "text": texto, "disable_web_page_preview": True}
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
    for _ in range(TENTATIVAS_TELEGRAM):
        try:
            resp = requests.post(url, json=payload, timeout=30)
        except requests.RequestException as exc:
            raise TelegramError(f"falha de rede: {exc}") from exc

        if resp.status_code == 429:
            espera = resp.json().get("parameters", {}).get("retry_after", 5)
<<<<<<< HEAD
            logger.warning("Rate limit do Telegram; aguardando %ss", espera)
=======
            log.warning("Rate limit do Telegram; aguardando %ss", espera)
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
            time.sleep(espera)
            continue

        if not resp.ok:
            try:
                detalhe = resp.json().get("description", resp.text)
            except ValueError:
                detalhe = resp.text
            raise TelegramError(f"HTTP {resp.status_code}: {detalhe}")
        return

    raise TelegramError("limite de tentativas excedido")


def enviar_telegram(config: Config, texto: str) -> None:
    url = f"https://api.telegram.org/bot{config.telegram_token}/sendMessage"
    for parte in dividir_mensagem(texto):
        enviar_parte(url, config.telegram_chat_id, parte)
        time.sleep(0.5)


<<<<<<< HEAD
def avisar_falha(config: Config, motivo: str) -> None:
    try:
        enviar_telegram(config, f"Agente de vagas falhou: {motivo}")
    except TelegramError as exc:
        logger.error("Não foi possível avisar a falha no Telegram: %s", exc)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
    )
=======
def aguardar_horario() -> None:
    # o cron do GitHub é impreciso; roda mais cedo e segura o envio até a hora certa
    if os.getenv("GITHUB_EVENT_NAME") != "schedule":
        return
    agora = datetime.now(FUSO)
    alvo = agora.replace(hour=HORA_ENVIO[0], minute=HORA_ENVIO[1], second=0, microsecond=0)
    falta = (alvo - agora).total_seconds()
    if 0 < falta <= JANELA_ESPERA:
        log.info("Aguardando %d min até o horário de envio", falta // 60)
        time.sleep(falta)


def avisar_falha(config: Config, motivo: str) -> None:
    try:
        enviar_telegram(config, f"Agente de vagas falhou: {motivo}")
    except TelegramError as exc:
        log.error("Não foi possível avisar a falha no Telegram: %s", exc)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)

    try:
        config = Config.from_env()
    except ConfigError as exc:
<<<<<<< HEAD
        logger.error("%s", exc)
=======
        log.error("%s", exc)
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
        return 1

    try:
        vagas = buscar_vagas(config.serpapi_key)
    except SearchError as exc:
<<<<<<< HEAD
        logger.error("%s", exc)
=======
        log.error("%s", exc)
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
        avisar_falha(config, str(exc))
        return 1

    if not vagas:
        corpo = "Nenhuma vaga nova nas últimas 24 horas para os filtros selecionados."
    else:
<<<<<<< HEAD
        client = OpenAI(api_key=config.openai_api_key, timeout=60, max_retries=2)
        corpo = filtrar_com_ia(client, vagas) or relatorio_sem_filtro(vagas)

    data = datetime.now(FUSO).strftime("%d/%m/%Y")
    mensagem = f"Vagas de dados e suporte - {data}\n\n{corpo}"
=======
        client = OpenAI(api_key=config.openai_key, timeout=60, max_retries=2)
        corpo = filtrar_com_ia(client, vagas) or relatorio_sem_filtro(vagas)
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)

    aguardar_horario()
    data = datetime.now(FUSO).strftime("%d/%m/%Y")
    try:
<<<<<<< HEAD
        enviar_telegram(config, mensagem)
    except TelegramError as exc:
        logger.error("Falha ao enviar o relatório: %s", exc)
        return 1

    logger.info("Relatório enviado")
=======
        enviar_telegram(config, f"Vagas de dados e suporte - {data}\n\n{corpo}")
    except TelegramError as exc:
        log.error("Falha ao enviar o relatório: %s", exc)
        return 1

    log.info("Relatório enviado")
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
    return 0


if __name__ == "__main__":
<<<<<<< HEAD
    sys.exit(main())
=======
    sys.exit(main())
>>>>>>> de696ad (Atualiza cronograma do workflow para execução às 19:30 e ajusta script para melhor organização e legibilidade)
