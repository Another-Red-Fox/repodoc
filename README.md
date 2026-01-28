# repodoc

A command-line tool that downloads all Markdown files from a GitHub repository and optionally compiles them into a single PDF using [md2pdf](https://github.com/Another-Red-Fox/md2pdf).

## Features

- Downloads the default branch (`main` or `master`) as a zip and extracts all `.md` files
- Disambiguates filename collisions by prepending the parent directory name
- Optionally compiles the downloaded files into a single ordered PDF via md2pdf

## Requirements

- Python 3.10+
- [md2pdf](https://github.com/Another-Red-Fox/md2pdf) installed at `~/md2pdf` (for PDF compilation)

## Installation

```bash
cd ~/repodoc
bash install.sh
```

This creates a virtual environment, installs dependencies, and generates a `repodoc` wrapper script.

## Usage

```bash
~/repodoc/repodoc
```

The tool will prompt you for a GitHub repository URL (e.g. `https://github.com/owner/repo`), download all `.md` files into a local directory named after the repo, and offer to compile them into a PDF.

## Dependencies

| Package    | Purpose                        |
|------------|--------------------------------|
| `requests` | Downloads repository archives  |
| `rich`     | Interactive TUI                |
