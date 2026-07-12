"""Nomad CLI — terminal interface for the mobile-first AI agent."""
import asyncio
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from nomad import __version__
from nomad.core.agent import NomadAgent
from nomad.config import NomadConfig, NOMAD_HOME


console = Console()


@click.group()
@click.version_option(__version__, prog_name="nomad")
def cli():
    """Nomad — Mobile-first AI agent OS."""
    pass


@cli.command()
@click.option("--provider", "-p", help="Force a specific provider")
def chat(provider: str):
    """Start an interactive chat session."""
    agent = NomadAgent()

    console.print(Panel(
        f"[bold cyan]Nomad[/bold cyan] v{__version__}\n"
        f"Mobile-first AI agent. Battery-aware, offline-first.\n"
        f"Session: [dim]{agent.session_id}[/dim]",
        title="🤖 Welcome",
        border_style="cyan",
    ))

    # Show provider status
    providers = agent.router.list_providers()
    if providers:
        console.print(f"[green]Providers:[/green] {', '.join(p['name'] for p in providers)}")
    else:
        console.print("[yellow]No providers configured.[/yellow] Set DEEPSEEK_API_KEY or OPENROUTER_API_KEY.")

    console.print("[dim]Type 'quit' to exit, 'stats' for stats.[/dim]\n")

    async def run_chat():
        while True:
            try:
                user_input = console.input("[bold cyan]you>[/bold cyan] ")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if user_input.strip().lower() in ("quit", "exit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if user_input.strip().lower() == "stats":
                stats = agent.get_stats()
                console.print(Panel(str(stats), title="Stats", border_style="dim"))
                continue

            if not user_input.strip():
                continue

            with console.status("[bold cyan]thinking...[/bold cyan]"):
                response = await agent.chat(user_input)

            console.print(Panel(
                Markdown(response),
                border_style="cyan",
                padding=(0, 1),
            ))
            console.print()

    asyncio.run(run_chat())


@cli.command()
def stats():
    """Show agent statistics."""
    agent = NomadAgent()
    stats = agent.get_stats()
    console.print(Panel(str(stats), title="Nomad Stats", border_style="cyan"))


@cli.command()
def setup():
    """Initial setup — configure API keys."""
    console.print(Panel(
        "[bold]Nomad Setup[/bold]\n\n"
        "Configure your API keys for free-tier model access.\n"
        "You can set these in your environment or in ~/.nomad/config.json",
        border_style="cyan",
    ))

    config = NomadConfig.load()

    # DeepSeek
    deepseek_key = console.input("[cyan]DeepSeek API key (optional, press Enter to skip):[/cyan] ")
    if deepseek_key:
        import os
        os.environ["DEEPSEEK_API_KEY"] = deepseek_key
        console.print("[green]✓ DeepSeek configured[/green]")

    # OpenRouter
    openrouter_key = console.input("[cyan]OpenRouter API key (optional, press Enter to skip):[/cyan] ")
    if openrouter_key:
        import os
        os.environ["OPENROUTER_API_KEY"] = openrouter_key
        console.print("[green]✓ OpenRouter configured[/green]")

    console.print("\n[green]Setup complete![/green] API keys are set for this session.")
    console.print("[dim]Add them to your shell profile for permanent use.[/dim]")


if __name__ == "__main__":
    cli()
