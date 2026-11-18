from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from openai import OpenAI, OpenAIError
from serpapi import GoogleSearch

logger = logging.getLogger("agente_vagas")

SITES_ALVO = (
    "vagasprajr.com.br",
    "viumavaga.com.br",
    "grupodevagas.com.br",
    "ciadeestagios.com.br",
    "indeed.com",
    "linkedin.com/jobs",
    "glassdoor.com.br",
    "gupy.io",
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

Regras de saída:
1. Remova links que sejam apenas páginas genéricas de busca, sem vaga específica.
2. Elimine duplicatas.
3. Para cada vaga, informe: cargo, empresa ou portal, resumo dos requisitos
   (se houver) e o link direto.
4. Use texto simples, sem Markdown.
5. Se nenhuma vaga atender aos critérios, responda apenas:
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
    openai_api_key: str
    serpapi_key: str
    telegram_token: str
    telegram_chat_id: str

    @classmethod
    def from_env(cls) -> Config:
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
        return cls(*valores.values())


@dataclass(frozen=True)
class Vaga:
    titulo: str
    resumo: str
    link: str

    def como_texto(self) -> str:
        return f"Título: {self.titulo}\nResumo: {self.resumo}\nLink: {self.link}"


def montar_query(sites: tuple[str, ...]) -> str:
    filtro = " OR ".join(f"site:{site}" for site in sites)
    return f"({filtro}) {CARGOS_ALVO}"


def buscar_bloco(api_key: str, sites: tuple[str, ...]) -> list[Vaga]:
    params = {
        "engine": "google",
        "q": montar_query(sites),
        "location": LOCALIZACAO,
        "hl": "pt",
        "gl": "br",
        "tbs": "qdr:d",  # últimas 24 horas
        "num": 15,
        "api_key": api_key,
    }
    try:
        dados = GoogleSearch(params).get_dict()
    except Exception as exc:
        raise SearchError(f"falha ao consultar a SerpAPI: {exc}") from exc

    # A SerpAPI sinaliza problemas no corpo da resposta, sem lançar exceção.
    erro = dados.get("error")
    if erro:
        if MSG_SEM_RESULTADO_SERPAPI in erro.lower():
            return []
        raise SearchError(erro)

    return [
        Vaga(
            titulo=item.get("title", "Sem título"),
            resumo=item.get("snippet", ""),
            link=item["link"],
        )
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
        logger.info("Buscando em: %s", ", ".join(sites))
        try:
            encontradas = buscar_bloco(api_key, sites)
        except SearchError as exc:
            logger.warning("Busca falhou para %s: %s", sites, exc)
            falhas += 1
            continue
        for vaga in encontradas:
            vagas.setdefault(vaga.link, vaga)

    if falhas == len(blocos):
        raise SearchError("todas as buscas falharam; verifique SERPAPI_KEY e o limite do plano")

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
                {"role": "user", "content": f"Resultados encontrados hoje:\n\n{texto}"},
            ],
        )
    except OpenAIError as exc:
        logger.error("Falha na OpenAI (%s): %s", type(exc).__name__, exc)
        return None

    conteudo = (resposta.choices[0].message.content or "").strip()
    if not conteudo:
        logger.error("A OpenAI devolveu uma resposta vazia")
        return None
    return conteudo


def relatorio_sem_filtro(vagas: list[Vaga]) -> str:
    itens = "\n".join(f"- {vaga.titulo}\n  {vaga.link}" for vaga in vagas)
    return f"Filtro por IA indisponível; resultados sem triagem:\n\n{itens}"


def dividir_mensagem(texto: str, limite: int = LIMITE_TELEGRAM) -> list[str]:
    partes: list[str] = []
    atual = ""
    for linha in texto.splitlines(keepends=True):
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


def enviar_parte(url: str, chat_id: str, texto: str) -> None:
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "disable_web_page_preview": True,
    }
    for _ in range(TENTATIVAS_TELEGRAM):
        try:
            resp = requests.post(url, json=payload, timeout=30)
        except requests.RequestException as exc:
            raise TelegramError(f"falha de rede: {exc}") from exc

        if resp.status_code == 429:
            espera = resp.json().get("parameters", {}).get("retry_after", 5)
            logger.warning("Rate limit do Telegram; aguardando %ss", espera)
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

    try:
        config = Config.from_env()
    except ConfigError as exc:
        logger.error("%s", exc)
        return 1

    try:
        vagas = buscar_vagas(config.serpapi_key)
    except SearchError as exc:
        logger.error("%s", exc)
        avisar_falha(config, str(exc))
        return 1

    if not vagas:
        corpo = "Nenhuma vaga nova nas últimas 24 horas para os filtros selecionados."
    else:
        client = OpenAI(api_key=config.openai_api_key, timeout=60, max_retries=2)
        corpo = filtrar_com_ia(client, vagas) or relatorio_sem_filtro(vagas)

    data = datetime.now(FUSO).strftime("%d/%m/%Y")
    mensagem = f"Vagas de dados e suporte - {data}\n\n{corpo}"

    try:
        enviar_telegram(config, mensagem)
    except TelegramError as exc:
        logger.error("Falha ao enviar o relatório: %s", exc)
        return 1

    logger.info("Relatório enviado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
