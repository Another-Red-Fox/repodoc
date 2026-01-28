#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Creating virtual environment..."
rm -rf .venv
python3 -m venv .venv

echo "Installing Python dependencies..."
.venv/bin/pip install --quiet -r requirements.txt

cat > "$SCRIPT_DIR/repodoc" <<WRAPPER
#!/usr/bin/env bash
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/repodoc.py" "\$@"
WRAPPER
chmod +x "$SCRIPT_DIR/repodoc"

echo ""
echo "Created wrapper script: ~/md2pdf/repodoc/repodoc"
echo ""
echo "Done! You can run the tool with:"
echo "  ~/md2pdf/repodoc/repodoc"
