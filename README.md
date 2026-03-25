# 🌱 Good News AI

Canal de boas notícias curadas por Inteligência Artificial.  
Busca diária automática no mundo todo, filtrando apenas notícias genuinamente positivas.

---

## Arquitetura

```
good-news-ai/
├── main.py           → CLI principal (api | collect | status | setup)
├── news_agent.py     → Agente agno + DuckDuckGo + Anthropic
├── scheduler.py      → Agendador diário (APScheduler)
├── api.py            → API REST (FastAPI)
├── database.py       → Persistência SQLite
├── config.py         → Configurações via .env
├── requirements.txt
├── .env.example
└── frontend/
    └── dashboard.html → Dashboard editorial do canal
```

## Stack

| Componente     | Tecnologia                       |
|----------------|----------------------------------|
| Agente IA      | [agno](https://github.com/agno-agi/agno) |
| LLM            | Anthropic Claude (Sonnet 4)      |
| Busca web      | DuckDuckGo (sem API key)         |
| API            | FastAPI + uvicorn                |
| Banco de dados | SQLite                           |
| Agendamento    | APScheduler                      |
| Frontend       | HTML puro (editorial magazine)   |

---

## API Endpoints

| Método | Endpoint        | Descrição                              |
|--------|-----------------|----------------------------------------|
| GET    | `/news`         | Lista notícias paginadas               |
| GET    | `/news?category=ciência` | Filtra por categoria          |
| GET    | `/news/{id}`    | Notícia específica                     |
| GET    | `/categories`   | Lista categorias disponíveis           |
| GET    | `/stats`        | Estatísticas gerais + próxima coleta   |
| POST   | `/collect`      | Aciona coleta manual (background)      |
| GET    | `/health`       | Health check                           |

---
## Fluxo do Agente

```
Para cada categoria:
  1. Gera query de busca otimizada
  2. DuckDuckGo busca notícias recentes
  3. Claude avalia positividade (0–10)
  4. Filtra score ≥ MIN_POSITIVITY_SCORE
  5. Traduz e formata em português
  6. Salva no SQLite (deduplica por URL)

Diariamente às DAILY_RUN_TIME (APScheduler)
```

---

## Frontend

Conecta automaticamente à API em `localhost:8000`.

Para servir em produção, use nginx ou qualquer servidor estático.
# good-news
# Good-News
