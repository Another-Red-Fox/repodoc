import re
import shutil
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

MAX_DOWNLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
REQUEST_TIMEOUT = 30  # seconds

REPODOC_BANNER = (
    "[bold bright_green]██████╗ ███████╗██████╗  ██████╗ ██████╗  ██████╗  ██████╗ [/]\n"
    "[bold green1]██╔══██╗██╔════╝██╔══██╗██╔═══██╗██╔══██╗██╔═══██╗██╔════╝[/]\n"
    "[bold chartreuse1]██████╔╝█████╗  ██████╔╝██║   ██║██║  ██║██║   ██║██║     [/]\n"
    "[bold green3]██╔══██╗██╔══╝  ██╔═══╝ ██║   ██║██║  ██║██║   ██║██║     [/]\n"
    "[bold green]██║  ██║███████╗██║     ╚██████╔╝██████╔╝╚██████╔╝╚██████╗[/]\n"
    "[dark_green]╚═╝  ╚═╝╚══════╝╚═╝      ╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝[/]"
)

# Path to the md2pdf executable
MD2PDF_PATH = Path.home() / "md2pdf" / "md2pdf"

# --------------------------------------------------------------------------- 
# Rich console
# --------------------------------------------------------------------------- 

console = Console()

# --------------------------------------------------------------------------- 
# Helper Functions
# --------------------------------------------------------------------------- 

def sanitize_filename(name: str) -> str:
    """Remove unsafe characters from a filename."""
    clean = UNSAFE_FILENAME_CHARS.sub("", name).strip(". ")
    if not clean:
        clean = "output"
    return clean[:200]

def get_repo_url() -> str:
    """Prompt user for a GitHub repository URL."""
    console.print()
    url = Prompt.ask(
        "[bold]Enter a GitHub repository URL[/bold]",
    )
    return url.strip()

def validate_url(url: str) -> tuple[str, str] | None:
    """Validate GitHub URL and extract owner/repo."""
    match = re.match(r"https?://github\.com/([\w-]+)/([\w.-]+)", url)
    if not match:
        return None
    return match.groups()

# ---------------------------------------------------------------------------
# Core Logic
# ---------------------------------------------------------------------------

def download_and_extract(owner: str, repo: str, dest: Path) -> list[Path]:
    """Download repo zip, extract .md files, and save them with original names."""
    zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip"
    alt_zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/master.zip"
    saved_files = []

    with console.status("Downloading repository...") as status:
        try:
            response = requests.get(zip_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                status.update("Main branch not found, trying master...")
                try:
                    response = requests.get(alt_zip_url, timeout=REQUEST_TIMEOUT)
                    response.raise_for_status()
                except requests.exceptions.RequestException as e_alt:
                    console.print(f"[red]Error:[/red] Failed to download from both main and master branches: {e_alt}")
                    return []
            else:
                console.print(f"[red]Error:[/red] Failed to download repository: {e}")
                return []
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Error:[/red] Failed to download repository: {e}")
            return []

        if len(response.content) > MAX_DOWNLOAD_SIZE:
            console.print(f"[red]Error:[/red] Repository archive exceeds {MAX_DOWNLOAD_SIZE // (1024 * 1024)} MB limit.")
            return []

        status.update("Extracting Markdown files...")
        try:
            with zipfile.ZipFile(BytesIO(response.content)) as z:
                # Find all markdown files
                md_files = [
                    name for name in z.namelist()
                    if name.lower().endswith(".md") and "venv/" not in name and "node_modules/" not in name
                ]

                if not md_files:
                    console.print("[yellow]No Markdown files found in the repository.[/yellow]")
                    return []

                # Extract and save with original names, disambiguating collisions
                dest.mkdir(parents=True, exist_ok=True)
                seen_names: dict[str, str] = {}  # lowercase name -> first zip path
                for full_path in md_files:
                    p = Path(full_path)
                    name = p.name
                    name_lower = name.lower()

                    if name_lower in seen_names:
                        # Collision: prepend parent directory to disambiguate
                        parent = p.parent.name
                        name = f"{parent}-{name}"
                    else:
                        seen_names[name_lower] = full_path

                    output_path = dest / name
                    with z.open(full_path) as source, open(output_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    saved_files.append(output_path)

        except zipfile.BadZipFile:
            console.print("[red]Error:[/red] Downloaded file is not a valid zip archive.")
            return []
        except Exception as e:
            console.print(f"[red]An unexpected error occurred during extraction:[/red] {e}")
            return []

    return saved_files

def run_md2pdf(directory: Path):
    """Run the md2pdf compile command on the specified directory."""
    if not MD2PDF_PATH.exists():
        console.print(f"[red]Error:[/red] md2pdf executable not found at {MD2PDF_PATH}")
        console.print("Please ensure the md2pdf project is in your home directory.")
        return

    console.print("\n[bold]Running md2pdf...[/bold]")
    with console.status("Compiling PDF..."):
        try:
            # We need to provide the absolute path to the directory
            command = [str(MD2PDF_PATH), "compile", str(directory.resolve())]
            # The md2pdf script needs to be run from its own directory to find its modules
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=MD2PDF_PATH.parent
            )

            if result.returncode == 0:
                # Strip ANSI escape codes before searching for the output path
                ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
                clean_stdout = ansi_escape.sub('', result.stdout)
                output_line = next(
                    (line for line in clean_stdout.splitlines() if "Saved:" in line),
                    None,
                )
                if output_line:
                    console.print(output_line.strip())
                console.print(Panel(
                    "[green]Successfully compiled PDF![/green]",
                    title="Compile Complete",
                    border_style="green",
                ))
            else:
                console.print("[red]Error during PDF compilation:[/red]")
                console.print(result.stdout)
                console.print(result.stderr)

        except Exception as e:
            console.print(f"[red]An unexpected error occurred while running md2pdf:[/red] {e}")

# --------------------------------------------------------------------------- 
# Main
# --------------------------------------------------------------------------- 

def main():
    """Main application entry point."""
    console.print()
    console.print("[dim]  Workflow Tools developed by Juan Bobadilla & Claude Code[/dim]")
    console.print()
    console.print(REPODOC_BANNER)
    console.print()
    console.print("[dark_green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
    console.print(Panel(
        "[bold bright_green]Repository Documentation Downloader[/bold bright_green]\n\n"
        "Downloads all .md files from a GitHub repository and organizes them.",
        title="[bold green]repodoc[/bold green]",
        border_style="green",
        padding=(1, 2),
    ))

    url = get_repo_url()
    repo_info = validate_url(url)

    if not repo_info:
        console.print("[red]Invalid GitHub URL.[/red] Please use a URL like https://github.com/owner/repo")
        return

    owner, repo = repo_info
    safe_repo_name = sanitize_filename(repo)
    output_dir = Path.cwd() / safe_repo_name

    if output_dir.exists():
        if not Confirm.ask(f"[yellow]Directory '{output_dir.name}' already exists. Overwrite?[/yellow]", default=False):
            console.print("[dim]Aborted.[/dim]")
            return
        shutil.rmtree(output_dir)

    saved_files = download_and_extract(owner, repo, output_dir)

    if not saved_files:
        # Error or no files found, messages are printed inside the function
        shutil.rmtree(output_dir, ignore_errors=True)
        return

    console.print(Panel(
        f"[green]Success![/green]\n\n"
        f"Downloaded {len(saved_files)} Markdown files to:\n"
        f"[cyan]{output_dir.resolve()}[/cyan]",
        title="Download Complete",
        border_style="green"
    ))

    # Ask to run md2pdf
    if Confirm.ask("\n[bold]Compile downloaded files into a single PDF with md2pdf?[/bold]"):
        run_md2pdf(output_dir)

if __name__ == "__main__":
    main()
