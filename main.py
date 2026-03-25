import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def cmd_api():
    from api import start_api
    console.print(Panel.fit(
        "[bold green]🌟 Good News AI[/bold green]\n"
        "Canal de Boas Notícias — Powered by Anthropic + agno",
        border_style="green",
    ))
    start_api()


def cmd_collect():
    from scheduler import run_collection
    run_collection()


def cmd_status():
    from database import db
    from config import settings

    stats = db.get_stats()

    console.print(Panel.fit("[bold green]📊 Status do Good News AI[/bold green]", border_style="green"))

    table = Table(show_header=False, box=None)
    table.add_row("[cyan]Total de notícias[/cyan]", str(stats["total_news"]))
    table.add_row("[cyan]Score médio de positividade[/cyan]", f"{stats['avg_positivity_score']}/10")
    table.add_row("[cyan]Modelo IA[/cyan]", settings.ANTHROPIC_MODEL)
    table.add_row("[cyan]Horário da coleta[/cyan]", settings.DAILY_RUN_TIME)
    console.print(table)

    if stats["by_category"]:
        console.print("\n[bold]Por Categoria:[/bold]")
        cat_table = Table("Categoria", "Notícias", box=None)
        for cat, count in stats["by_category"].items():
            cat_table.add_row(cat, str(count))
        console.print(cat_table)

    if stats["last_run"]:
        run = stats["last_run"]
        console.print(f"\n[bold]Última coleta:[/bold] {run.get('started_at', 'N/A')}")
        console.print(f"  Status: {run.get('status', 'N/A')}")
        console.print(f"  Salvas: {run.get('total_saved', 0)}")


def cmd_setup():
    from config import settings

    ok = True

    if settings.ANTHROPIC_API_KEY and settings.ANTHROPIC_API_KEY != "sua_chave_aqui":
        console.print("[green]✓ ANTHROPIC_API_KEY configurada[/green]")
    else:
        console.print("[red]✗ ANTHROPIC_API_KEY não configurada (copie .env.example para .env)[/red]")
        ok = False

    deps = ["agno", "fastapi", "apscheduler", "duckduckgo_search"]
    for dep in deps:
        try:
            __import__(dep.replace("-", "_"))
            console.print(f"[green]✓ {dep} instalado[/green]")
        except ImportError:
            console.print(f"[red]✗ {dep} não instalado — rode: pip install -r requirements.txt[/red]")
            ok = False

    if ok:
        console.print("\n[bold green]✅ Tudo pronto! Use: python main.py api[/bold green]")
    else:
        console.print("\n[bold red]❌ Corrija os problemas acima antes de continuar.[/bold red]")


COMMANDS = {
    "api": cmd_api,
    "collect": cmd_collect,
    "status": cmd_status,
    "setup": cmd_setup,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "api"
    if cmd not in COMMANDS:
        console.print(f"[red]Comando desconhecido: {cmd}[/red]")
        console.print(f"Comandos disponíveis: {', '.join(COMMANDS.keys())}")
        sys.exit(1)
    COMMANDS[cmd]()