from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from config import settings
from database import NewsItem

console = Console()

# ── Prompts ────────────────────────────────────────────────────────────────────

SEARCH_AGENT_SYSTEM = """Você é um curador especializado em boas notícias do mundo inteiro.
Seu trabalho é encontrar notícias genuinamente positivas, inspiradoras e construtivas.

CRITÉRIOS DE BOA NOTÍCIA:
- Avanços científicos ou médicos
- Histórias de superação e resiliência humana
- Ações de solidariedade, voluntariado e bondade
- Descobertas ambientais positivas ou recuperação da natureza
- Inovações tecnológicas benéficas para a sociedade
- Conquistas educacionais e culturais
- Animais salvos ou espécies se recuperando
- Comunidades se unindo para resolver problemas
- Marcos históricos positivos

EVITE absolutamente:
- Notícias com sofrimento, violência, tragédias, mesmo que com "final feliz" superficial
- "Boas notícias" que dependem de comparar com algo ruim
- Notícias de cunho político ou partidário
- Fake news ou histórias não verificáveis

Responda SEMPRE em português do Brasil, de forma clara e engajante."""


EVALUATION_PROMPT = """Avalie as notícias encontradas e retorne APENAS um JSON válido com esta estrutura exata:

{{
  "news": [
    {{
      "title": "Título claro e engajante em português",
      "summary": "Resumo de 2-3 frases explicando a boa notícia de forma inspiradora",
      "url": "URL original da notícia",
      "source": "Nome do veículo de comunicação",
      "category": "{category}",
      "positivity_score": 8.5,
      "tags": ["tag1", "tag2", "tag3"],
      "published_at": "data aproximada se conhecida, senão null"
    }}
  ]
}}

REGRAS:
- positivity_score: número de 0 a 10 (somente notícias ≥ {min_score} serão publicadas)
- Inclua APENAS notícias que você considera genuinamente boas e verificáveis
- tags: 3-5 palavras-chave relevantes em português
- Se não encontrar nenhuma boa notícia, retorne {{"news": []}}
- NÃO inclua markdown, blocos de código ou texto fora do JSON

Notícias encontradas para avaliar:
{raw_results}"""


# ── Agent ──────────────────────────────────────────────────────────────────────

class GoodNewsAgent:

    def __init__(self):
        self._setup_agent()

    def _setup_agent(self):
        try:
            from agno.agent import Agent
            from agno.models.anthropic import Claude
            from agno.tools.duckduckgo import DuckDuckGoTools

            self.agent = Agent(
                model=Claude(
                    id=settings.ANTHROPIC_MODEL,
                    api_key=settings.ANTHROPIC_API_KEY,
                ),
                tools=[DuckDuckGoTools()],
                system_message=SEARCH_AGENT_SYSTEM,
                markdown=False,
            )
            console.print("[green]✓ Agente agno inicializado com sucesso[/green]")
        except Exception as e:
            console.print(f"[red]✗ Erro ao inicializar agente: {e}[/red]")
            raise

    def _build_search_query(self, category: str) -> str:
        
        query_map = {
            "ciência": "scientific breakthrough discovery good news 2025 or 2026",
            "meio ambiente": "environmental recovery nature conservation good news 2025 or 2026",
            "saúde": "medical breakthrough health achievement positive news 2025 or 2026",
            "inovação": "technology innovation positive impact humanity 2025 or 2026",
            "comunidade": "community kindness solidarity inspiring stories 2025 or 2026",
            "educação": "education achievement learning inspiring youth 2025 or 2026",
            "animais": "animals rescued wildlife conservation success 2025 or 2026",
            "espaço": "space exploration discovery milestone 2025 or 2026",
        }
        return query_map.get(
            category.lower(),
            f"good positive inspiring news {category} 2025",
        )

    def _parse_news_response(self, response_text: str, category: str) -> list[NewsItem]:
        # Tenta extrair JSON da resposta (o LLM pode adicionar texto extra)
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            console.print(f"[yellow]⚠ Nenhum JSON encontrado para categoria: {category}[/yellow]")
            return []

        try:
            data = json.loads(json_match.group())
            raw_items = data.get("news", [])
        except json.JSONDecodeError as e:
            console.print(f"[yellow]⚠ JSON inválido para {category}: {e}[/yellow]")
            return []

        items: list[NewsItem] = []
        for item in raw_items:
            score = float(item.get("positivity_score", 0))
            if score < settings.MIN_POSITIVITY_SCORE:
                continue

            url = item.get("url", "").strip()
            if not url or not url.startswith("http"):
                continue

            news = NewsItem(
                title=item.get("title", "").strip(),
                summary=item.get("summary", "").strip(),
                url=url,
                source=item.get("source", "Desconhecido"),
                category=category,
                positivity_score=score,
                tags=item.get("tags", []),
                published_at=item.get("published_at"),
                collected_at=datetime.utcnow().isoformat(),
            )

            if news.title and news.summary:
                items.append(news)

        return items

    def search_category(self, category: str) -> list[NewsItem]:

        query = self._build_search_query(category)

        search_prompt = f"""Busque notícias boas e positivas sobre: {category}

Use a ferramenta de busca com a query: "{query}"

Após obter os resultados, avalie cada notícia encontrada e retorne a avaliação 
no formato JSON solicitado."""

        evaluation_instructions = EVALUATION_PROMPT.format(
            category=category,
            min_score=settings.MIN_POSITIVITY_SCORE,
            raw_results="[veja os resultados da busca acima]",
        )

        full_prompt = f"{search_prompt}\n\n{evaluation_instructions}"

        try:
            response = self.agent.run(full_prompt)
            response_text = response.content if hasattr(response, "content") else str(response)
            items = self._parse_news_response(response_text, category)
            return items[: settings.NEWS_PER_CATEGORY]
        except Exception as e:
            console.print(f"[red]✗ Erro na busca de '{category}': {e}[/red]")
            return []

    def run_daily_collection(self) -> tuple[list[NewsItem], dict]:
        all_news: list[NewsItem] = []
        stats = {
            "started_at": datetime.utcnow().isoformat(),
            "categories_processed": 0,
            "categories_with_news": 0,
            "total_found": 0,
        }

        console.print(
            Panel.fit(
                f"[bold green]🌟 Iniciando coleta diária de boas notícias[/bold green]\n"
                f"Categorias: {', '.join(settings.SEARCH_CATEGORIES)}",
                border_style="green",
            )
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for category in settings.SEARCH_CATEGORIES:
                task = progress.add_task(
                    f"[cyan]Buscando: {category}...", total=None
                )
                items = self.search_category(category)

                stats["categories_processed"] += 1
                if items:
                    stats["categories_with_news"] += 1
                    all_news.extend(items)
                    console.print(
                        f"  [green]✓ {category}:[/green] {len(items)} notícias encontradas"
                    )
                else:
                    console.print(
                        f"  [yellow]○ {category}:[/yellow] nenhuma notícia boa encontrada"
                    )

                progress.remove_task(task)

        stats["total_found"] = len(all_news)
        stats["finished_at"] = datetime.utcnow().isoformat()

        console.print(
            Panel.fit(
                f"[bold green]✅ Coleta concluída![/bold green]\n"
                f"Total: [bold]{len(all_news)}[/bold] boas notícias de "
                f"[bold]{stats['categories_with_news']}[/bold] categorias",
                border_style="green",
            )
        )

        return all_news, stats


# Instância global reutilizável
_agent_instance: Optional[GoodNewsAgent] = None


def get_agent() -> GoodNewsAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GoodNewsAgent()
    return _agent_instance