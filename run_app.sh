#!/bin/bash
# ─────────────────────────────────────────────────────────
# Sprint Analytics — spouštěcí skript
# Použití:  ./run_app.sh
# ─────────────────────────────────────────────────────────

set -e

cd "$(dirname "$0")"

echo "🔍 Kontroluji Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 není nainstalovaný. Nainstaluj ho z https://www.python.org/"
    exit 1
fi
echo "✓ Python3 nalezen: $(python3 --version)"

# Vytvoř virtuální prostředí, pokud neexistuje
if [ ! -d ".venv" ]; then
    echo ""
    echo "📦 Vytvářím virtuální prostředí (.venv)..."
    python3 -m venv .venv
fi

# Aktivuj venv
source .venv/bin/activate

# Doinstaluj dependencies
echo ""
echo "📥 Kontroluji a instaluji knihovny (jen co chybí)..."
pip install --quiet --upgrade pip
pip install --quiet streamlit pandas matplotlib numpy python-dotenv pytz python-dateutil jira

# Zkontroluj, že CSV existuje
if [ ! -f "sprint_3132_MOB.csv" ]; then
    echo ""
    echo "⚠️  CSV soubor 'sprint_3132_MOB.csv' nenalezen ve složce."
    echo "   Můžeš ho vygenerovat příkazem:  python3 sprint_data.py"
    echo "   Aplikace půjde stále spustit, ale budeš muset CSV nahrát ručně."
fi

# Spusť Streamlit
echo ""
echo "🚀 Spouštím Sprint Analytics..."
echo "   Otevře se prohlížeč na http://localhost:8501"
echo "   Pro ukončení stiskni Ctrl+C"
echo ""

streamlit run "sprint_analytics .py"
