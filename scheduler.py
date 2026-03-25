
import signal
import sys
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from rich.console import Console

from config import settings
from database import db

console = Console()


def run_collection():
    console.print(f"\n[bold cyan]⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')} — Iniciando coleta agendada...[/bold cyan]")

    from news_agent import get_agent

    run_id = db.start_run()
    error_msg = None
    all_news = []

    try:
        agent = get_agent()
        all_news, stats = agent.run_daily_collection()

        saved = db.save_many(all_news)
        db.cleanup_old_news()

        console.print(f"[green]💾 {saved}/{len(all_news)} notícias salvas no banco.[/green]")

    except Exception as e:
        error_msg = str(e)
        console.print(f"[red]✗ Erro na coleta: {e}[/red]")

    finally:
        db.finish_run(
            run_id=run_id,
            found=len(all_news),
            saved=len(all_news),
            error=error_msg,
        )


class DailyScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
        self._configure()

    def _configure(self):
        """Configura o job diário baseado em DAILY_RUN_TIME."""
        hour, minute = settings.DAILY_RUN_TIME.split(":")
        self.scheduler.add_job(
            run_collection,
            trigger=CronTrigger(hour=int(hour), minute=int(minute)),
            id="daily_news_collection",
            name="Coleta Diária de Boas Notícias",
            replace_existing=True,
            misfire_grace_time=3600, 
        )
        console.print(
            f"[green]📅 Coleta agendada para todos os dias às {settings.DAILY_RUN_TIME}[/green]"
        )

    def start(self):
        self.scheduler.start()
        console.print("[green]✓ Agendador iniciado[/green]")

    def stop(self):
        self.scheduler.shutdown()
        console.print("[yellow]Agendador encerrado.[/yellow]")

    def trigger_now(self):
        console.print("[cyan]▶ Executando coleta manual...[/cyan]")
        run_collection()

    def get_next_run(self) -> str:
        job = self.scheduler.get_job("daily_news_collection")
        if job and job.next_run_time:
            return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        return "Não agendado"


scheduler = DailyScheduler()


def setup_signal_handlers():
    def handler(sig, frame):
        console.print("\n[yellow]🛑 Encerrando...[/yellow]")
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)