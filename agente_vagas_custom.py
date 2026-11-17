import os
import time
import requests
from serpapi import GoogleSearch
from openai import OpenAI

# Pega as chaves de forma segura das Variáveis de Ambiente do GitHub
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

# Domínios extraídos da sua lista
SITES_ALVO = [
    "vagasprajr.com.br",
    "viumavaga.com.br",
    "grupodevagas.com.br",
    "ciadeestagios.com.br",
    "indeed.com",
    "linkedin.com/jobs",
    "glassdoor.com.br",
    "gupy.io"
]

# Cargos e palavras-chave desejadas
CARGOS_ALVO = (
    '("estágio" OR "estagio" OR "júnior" OR "junior") AND '
    '("dados" OR "analista de dados" OR "cientista de dados" OR '
    '"engenheiro de dados" OR "banco de dados" OR "suporte n1" OR '
    '"suporte n2" OR "analista de suporte")'
)

def buscar_vagas_na_web():
    resultados_consolidados = []
    
    # Agrupa os sites de 3 em 3 para otimizar o uso de créditos da API de busca
    blocos_sites = [SITES_ALVO[i:i + 3] for i in range(0, len(SITES_ALVO), 3)]
    
    for bloco in blocos_sites:
        filtro_sites = " OR ".join([f"site:{site}" for site in bloco])
        query_completa = f"({filtro_sites}) {CARGOS_ALVO}"
        
        print(f"Executando busca: {query_completa}")
        
        params = {
            "engine": "google",
            "q": query_completa,
            "location": "Rio de Janeiro, State of Rio de Janeiro, Brazil",
            "hl": "pt",
            "gl": "br",
            "tbs": "qdr:d",  # Filtra apenas resultados das últimas 24 horas
            "num": 15,
            "api_key": SERPAPI_KEY
        }
        
        try:
            search = GoogleSearch(params)
            dados = search.get_dict()
            organicos = dados.get("organic_results", [])
            
            for item in organicos:
                titulo = item.get("title", "Sem título")
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                resultados_consolidados.append(f"Título: {titulo}\nResumo: {snippet}\nLink: {link}\n---")
        except Exception as e:
            print(f"Erro na busca do bloco {bloco}: {e}")
            
    return "\n".join(resultados_consolidados)

def filtrar_e_montar_relatorio(texto_bruto):
    if not texto_bruto.strip():
        return "Nenhuma vaga nova encontrada nas últimas 24 horas para os filtros selecionados."

    prompt_sistema = """
    Você é um assistente de recrutamento especializado em tecnologia e dados.
    Analise os resultados de busca abaixo e filtre ESTRITAMENTE vagas abertas para:
    - Nível: Estágio ou Júnior (descarte vagas Pleno, Sênior, Especialista ou Coordenação).
    - Áreas: Análise de Dados, Ciência de Dados, Engenharia de Dados, Banco de Dados, BI, ou Suporte Técnico (N1/N2).
    
    Regras de saída:
    1. Remova links que sejam apenas páginas genéricas de busca sem uma vaga específica (exceto se indicarem listagens recém-atualizadas).
    2. Elimine vagas duplicadas.
    3. Formate em tópicos limpos contendo: Cargo, Empresa/Portal, Resumo dos requisitos (se houver) e o Link direto.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Rápido, econômico e excelente para triagem
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"Resultados encontrados hoje:\n\n{texto_bruto}"}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    # Divide a mensagem se passar do limite de 4096 caracteres do Telegram
    partes = [mensagem[i:i+4000] for i in range(0, len(mensagem), 4000)]
    
    for parte in partes:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": parte,
            "disable_web_page_preview": True
        }
        requests.post(url, json=payload)

def rotina_diaria():
    print("Iniciando varredura diária de vagas...")
    brutos = buscar_vagas_na_web()
    relatorio = filtrar_e_montar_relatorio(brutos)
    cabecalho = "🚀 *RELATÓRIO DE VAGAS - DADOS & SUPORTE (20:00)*\n\n"
    enviar_telegram(cabecalho + relatorio)
    print("Relatório enviado com sucesso!")

# Roda todo dia às 19:50 para você receber pontualmente às 20:00
schedule.every().day.at("19:50").do(rotina_diaria)

if __name__ == "__main__":
    print("Agente de Vagas ativo! Aguardando horário agendado...")
    # Descomente a linha abaixo se quiser testar imediatamente ao rodar o script:
    # rotina_diaria()
    while True:
        schedule.run_pending()
        time.sleep(30)