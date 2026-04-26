import os
from typing import Any

import requests
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

app = typer.Typer(help="SpecMem developer CLI. Calls the FastAPI backend only.")
console = Console()


def request_error_message(exc: requests.exceptions.RequestException) -> str:
    response = getattr(exc, "response", None)
    if response is None:
        return f"Could not reach backend at {BACKEND_URL}: {exc}"

    try:
        detail = response.json()
    except ValueError:
        detail = response.text

    return f"Backend error {response.status_code}: {detail}"


def post(path: str, payload: dict[str, Any]) -> dict[str, Any] | list[Any]:
    try:
        response = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        console.print(f"[red]{request_error_message(exc)}[/red]")
        raise typer.Exit(1) from exc
    except ValueError as exc:
        console.print("[red]Backend returned a non-JSON response.[/red]")
        raise typer.Exit(1) from exc


def get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
    try:
        response = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        console.print(f"[red]{request_error_message(exc)}[/red]")
        raise typer.Exit(1) from exc
    except ValueError as exc:
        console.print("[red]Backend returned a non-JSON response.[/red]")
        raise typer.Exit(1) from exc


def split_values(value: str) -> list[str]:
    return [item.strip() for item in value.replace(",", "\n").splitlines() if item.strip()]


def extract_memories(data: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    for key in ("memories", "items", "results", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    return []


def print_memory(memory: dict[str, Any]) -> None:
    title = memory.get("bug_title", "Untitled bug")
    description = memory.get("description", "No description provided.")
    module = memory.get("module", "unknown module")
    file_path = memory.get("file_path", "unknown file")
    failed_fixes = ", ".join(map(str, memory.get("failed_fixes") or [])) or "None"
    root_cause = memory.get("root_cause", "Unknown")
    final_fix = memory.get("final_fix", "Unknown")

    console.print(
        Panel(
            f"{description}\n\n"
            f"[bold]Module:[/bold] {module}\n"
            f"[bold]File:[/bold] {file_path}\n"
            f"[bold red]Failed fixes:[/bold red] {failed_fixes}\n"
            f"[bold]Root cause:[/bold] {root_cause}\n"
            f"[bold green]Final fix:[/bold green] {final_fix}",
            title=title,
            border_style="cyan",
        )
    )


@app.command()
def remember(
    project_id: str = typer.Option(..., "--project-id", prompt=True),
    bug_title: str = typer.Option(..., "--bug-title", prompt=True),
    description: str = typer.Option(..., "--description", prompt=True),
    file_path: str = typer.Option(..., "--file-path", prompt=True),
    module: str = typer.Option(..., "--module", prompt=True),
    failed_fixes: str = typer.Option("", "--failed-fixes", prompt="Failed fixes, comma-separated"),
    root_cause: str = typer.Option(..., "--root-cause", prompt=True),
    final_fix: str = typer.Option(..., "--final-fix", prompt=True),
    tags: str = typer.Option("", "--tags", prompt="Tags, comma-separated"),
) -> None:
    """Save a bug memory through POST /memory."""
    payload = {
        "project_id": project_id,
        "bug_title": bug_title,
        "description": description,
        "file_path": file_path,
        "module": module,
        "failed_fixes": split_values(failed_fixes),
        "root_cause": root_cause,
        "final_fix": final_fix,
        "tags": split_values(tags),
    }
    data = post("/memory", payload)
    console.print("[green]Memory saved.[/green]")
    console.print_json(data=data)


@app.command()
def debug(
    query: str = typer.Argument(..., help="Bug query to debug."),
    project_id: str = typer.Option(..., "--project-id", "-p"),
    module: str | None = typer.Option(None, "--module", "-m"),
    file_path: str | None = typer.Option(None, "--file-path", "-f"),
) -> None:
    """Debug a new bug through POST /debug."""
    payload = {
        "project_id": project_id,
        "query": query,
        "module": module,
        "file_path": file_path,
    }
    data = post("/debug", payload)
    if not isinstance(data, dict):
        console.print("[red]Unexpected response from backend.[/red]")
        raise typer.Exit(1)

    console.print(Panel(data.get("answer", "No answer returned."), title="SpecMem Answer", border_style="green"))

    warning = data.get("failed_fix_warning")
    if warning:
        console.print(Panel(str(warning), title="Failed Fix Warning", border_style="red"))

    similar_bugs = data.get("similar_bugs") or []
    if similar_bugs:
        console.print("[bold]Similar bugs[/bold]")
        for bug in similar_bugs:
            if isinstance(bug, dict):
                print_memory(bug)

    token_savings = data.get("token_savings")
    if isinstance(token_savings, dict):
        table = Table(title="Token Savings")
        table.add_column("Before")
        table.add_column("After")
        table.add_column("Savings")
        table.add_row(
            str(token_savings.get("before_tokens", "N/A")),
            str(token_savings.get("after_tokens", "N/A")),
            f"{token_savings.get('savings_percent', 'N/A')}%",
        )
        console.print(table)


@app.command()
def check(
    proposed_fix: str = typer.Argument(..., help="Proposed fix to check."),
    project_id: str = typer.Option(..., "--project-id", "-p"),
    module: str | None = typer.Option(None, "--module", "-m"),
) -> None:
    """Check a proposed fix through POST /check."""
    payload = {
        "project_id": project_id,
        "proposed_fix": proposed_fix,
        "module": module,
    }
    data = post("/check", payload)
    if not isinstance(data, dict):
        console.print("[red]Unexpected response from backend.[/red]")
        raise typer.Exit(1)

    warning = data.get("warning")
    if warning:
        console.print(Panel(str(warning), title="Warning", border_style="red"))
    else:
        console.print("[green]No matching failed fix found.[/green]")

    matched_failed_fix = data.get("matched_failed_fix")
    if matched_failed_fix:
        console.print_json(data=matched_failed_fix)


@app.command()
def memories(project_id: str = typer.Option(..., "--project-id", "-p")) -> None:
    """List recent memories through GET /memory."""
    data = get("/memory", params={"project_id": project_id})
    memories_list = extract_memories(data)

    if not memories_list:
        console.print("[yellow]No memories found for this project.[/yellow]")
        return

    for memory in memories_list:
        print_memory(memory)


if __name__ == "__main__":
    app()
