"""Interface de linha de comando: `emporio` ou `python -m emporio_agent.cli`."""
from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv
from rich.console import Console

from . import config
from .agent import FALLBACK, Agent, ToolCall


def main(argv: list[str] | None = None) -> int:
    load_dotenv(config.ROOT / ".env")
    ap = argparse.ArgumentParser(description="Téo, assistente virtual da Empório da Música")
    ap.add_argument("--session", help="ID da sessão para retomar/continuar uma conversa salva")
    ap.add_argument("--debug", action="store_true", help="mostra as ferramentas chamadas")
    args = ap.parse_args(argv)

    console = Console()
    try:
        agent = Agent(session_id=args.session)
    except Exception as exc:  # ex.: ANTHROPIC_API_KEY ausente
        console.print(f"[red]Não foi possível iniciar o agente:[/red] {exc}")
        return 1

    def show_tool(call: ToolCall) -> None:
        if args.debug:
            console.print(f"  [dim]🔧 {call.name}({call.args})[/dim]")

    console.print(f"[bold]Empório da Música[/bold] · sessão [cyan]{agent.session_id}[/cyan] · "
                  "digite 'sair' para encerrar\n")
    if agent.messages:
        console.print(f"[dim]({len(agent.messages)} mensagens restauradas da sessão)[/dim]\n")
    while True:
        try:
            text = console.input("[bold green]Você:[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if text.lower() in {"sair", "exit", "quit"}:
            break
        if not text:
            continue
        try:
            turn = agent.reply(text, on_tool=show_tool)
            console.print(f"[bold blue]Téo:[/bold blue] {turn.reply}\n")
        except Exception as exc:
            if args.debug:
                console.print(f"[red]{type(exc).__name__}: {exc}[/red]")
            console.print(f"[bold blue]Téo:[/bold blue] {FALLBACK}\n")
    console.print(f"Sessão salva: [cyan]{agent.session_id}[/cyan] (retome com --session {agent.session_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
