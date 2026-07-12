"""Nomad CLI — terminal interface for the mobile-first AI agent."""
import asyncio
import sys
import json

import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table

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
def chat():
    """Start an interactive chat session."""
    agent = NomadAgent()

    console.print(Panel(
        f"[bold cyan]Nomad[/bold cyan] v{__version__}\n"
        f"Mobile-first AI agent with tools.\n"
        f"Session: [dim]{agent.session_id}[/dim]",
        title="🤖 Welcome",
        border_style="cyan",
    ))

    # Show status
    providers = []
    import os
    if (os.getenv("OPENROUTER_API_KEY") or "").strip():
        providers.append("OpenRouter")
    if (os.getenv("DEEPSEEK_API_KEY") or "").strip():
        providers.append("DeepSeek")

    tools = [t.name for t in agent.get_stats()["tools"]]
    
    if providers:
        console.print(f"[green]Providers:[/green] {', '.join(providers)}")
    else:
        console.print("[yellow]No API keys found.[/yellow] Set OPENROUTER_API_KEY.")
    
    console.print(f"[green]Tools:[/green] {', '.join(tools)}")
    console.print("[dim]Commands: 'quit' to exit, 'stats' for info, 'tools' to list tools[/dim]\n")

    async def approve_tool(name: str, args: dict) -> bool:
        """Ask user to approve dangerous tool calls."""
        args_str = json.dumps(args, indent=2)[:200]
        console.print(f"\n[yellow]⚠ Tool request:[/yellow] [bold]{name}[/bold]")
        console.print(f"[dim]{args_str}[/dim]")
        
        try:
            response = console.input("[cyan]Allow? (y/n):[/cyan] ").strip().lower()
            return response in ("y", "yes", "")
        except (EOFError, KeyboardInterrupt):
            return False

    async def run_chat():
        while True:
            try:
                user_input = console.input("[bold cyan]you>[/bold cyan] ")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye![/dim]")
                break

            cmd = user_input.strip().lower()
            if cmd in ("quit", "exit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if cmd == "stats":
                stats = agent.get_stats()
                table = Table(title="Nomad Stats", border_style="cyan")
                table.add_column("Key", style="bold")
                table.add_column("Value")
                for k, v in stats.items():
                    table.add_row(k, str(v))
                console.print(table)
                continue

            if cmd == "tools":
                from nomad.tools.registry import registry
                table = Table(title="Available Tools", border_style="cyan")
                table.add_column("Name", style="bold")
                table.add_column("Risk")
                table.add_column("Description")
                for t in registry.list_tools():
                    risk_style = {"safe": "green", "moderate": "yellow", "dangerous": "red"}
                    table.add_row(
                        t.name,
                        f"[{risk_style.get(t.risk.value, 'white')}]{t.risk.value}[/{risk_style.get(t.risk.value, 'white')}]",
                        t.description[:60],
                    )
                console.print(table)
                continue

            if not user_input.strip():
                continue

            with console.status("[bold cyan]thinking...[/bold cyan]"):
                response = await agent.chat(user_input, approve_callback=approve_tool)

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
    
    table = Table(title="Nomad Stats", border_style="cyan")
    table.add_column("Key", style="bold")
    table.add_column("Value")
    for k, v in stats.items():
        table.add_row(k, str(v))
    console.print(table)


@cli.command()
def tools():
    """List available tools."""
    import nomad.tools.builtins  # trigger registration
    
    from nomad.tools.registry import registry
    table = Table(title="Nomad Tools", border_style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Risk")
    table.add_column("Description")
    
    for t in registry.list_tools():
        risk_style = {"safe": "green", "moderate": "yellow", "dangerous": "red"}
        style = risk_style.get(t.risk.value, "white")
        table.add_row(
            t.name,
            f"[{style}]{t.risk.value}[/{style}]",
            t.description[:70],
        )
    console.print(table)


@cli.command()
def setup():
    """Initial setup — configure API keys."""
    console.print(Panel(
        "[bold]Nomad Setup[/bold]\n\n"
        "Configure your API keys for free-tier model access.\n",
        border_style="cyan",
    ))

    import os
    
    deepseek_key = console.input("[cyan]DeepSeek API key (optional):[/cyan] ").strip()
    if deepseek_key:
        os.environ["DEEPSEEK_API_KEY"] = deepseek_key
        console.print("[green]✓ DeepSeek configured[/green]")

    openrouter_key = console.input("[cyan]OpenRouter API key (optional):[/cyan] ").strip()
    if openrouter_key:
        os.environ["OPENROUTER_API_KEY"] = openrouter_key
        console.print("[green]✓ OpenRouter configured[/green]")

    console.print("\n[green]Done![/green] Add to ~/.bashrc for permanent use:")
    console.print("[dim]export OPENROUTER_API_KEY='your-key'[/dim]")


if __name__ == "__main__":
    cli()
