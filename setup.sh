#!/bin/bash

# ============================================
# OKTAGON SAV - Script d'installation rapide
# ============================================

set -e  # Exit on error

echo "🚀 OKTAGON SAV - Installation"
echo "======================================"
echo ""

# Vérifier Python 3.10
echo "📋 Vérification de Python 3.10..."
if ! command -v python3.10 &> /dev/null; then
    echo "❌ Python 3.10 non trouvé. Installation requise :"
    echo "   brew install python@3.10  (macOS)"
    echo "   ou télécharger depuis https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3.10 --version)
echo "✅ $PYTHON_VERSION détecté"
echo ""

# Créer environnement virtuel
echo "📦 Création de l'environnement virtuel..."
if [ -d ".venv" ]; then
    echo "⚠️  .venv existe déjà, on le réutilise"
else
    python3.10 -m venv .venv
    echo "✅ Environnement virtuel créé"
fi
echo ""

# Activer l'environnement
echo "🔌 Activation de l'environnement..."
source .venv/bin/activate
echo "✅ Environnement activé"
echo ""

# Installer les dépendances
echo "📥 Installation des dépendances..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ Dépendances installées"
echo ""

# Créer .env si n'existe pas
if [ ! -f ".env" ]; then
    echo "📝 Création du fichier .env..."
    cp .env.example .env
    chmod 600 .env
    echo "✅ .env créé depuis .env.example"
    echo ""
    echo "⚠️  IMPORTANT : Éditer .env avec vos credentials !"
    echo "   nano .env"
    echo ""
else
    echo "✅ .env existe déjà"

    # Vérifier les permissions
    PERMS=$(stat -f "%A" .env 2>/dev/null || stat -c "%a" .env 2>/dev/null)
    if [ "$PERMS" != "600" ]; then
        echo "⚠️  Correction permissions .env (actuellement $PERMS)"
        chmod 600 .env
        echo "✅ Permissions .env fixées à 600"
    fi
    echo ""
fi

# Vérifier PostgreSQL
echo "🐘 Vérification de PostgreSQL..."
if command -v psql &> /dev/null; then
    PG_VERSION=$(psql --version | head -1)
    echo "✅ $PG_VERSION détecté"
else
    echo "⚠️  PostgreSQL non détecté"
    echo "   Installation recommandée :"
    echo "   brew install postgresql@15  (macOS)"
    echo "   ou Docker : docker run -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:15"
fi
echo ""

# Vérifier la base de données (optionnel)
echo "🗄️  Test de connexion PostgreSQL..."
source .env 2>/dev/null || true
if [ -n "$DB_HOST" ] && [ -n "$DB_USER" ]; then
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" &>/dev/null; then
        echo "✅ Connexion PostgreSQL OK"
    else
        echo "⚠️  Impossible de se connecter à PostgreSQL"
        echo "   Vérifiez les credentials dans .env"
        echo "   Ou créez la base : createdb -U $DB_USER $DB_NAME"
    fi
else
    echo "⚠️  Variables DB_* non définies dans .env"
fi
echo ""

# Lancer les tests (optionnel)
echo "🧪 Lancement des tests (optionnel)..."
read -p "Voulez-vous lancer les tests ? (y/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if pip list | grep -q pytest; then
        echo "▶️  pytest tests/unit/ -v"
        pytest tests/unit/ -v || true
    else
        echo "⚠️  pytest non installé, installation..."
        pip install pytest pytest-asyncio pytest-mock pytest-cov -q
        pytest tests/unit/ -v || true
    fi
else
    echo "⏭️  Tests ignorés"
fi
echo ""

# Résumé
echo "======================================"
echo "✅ Installation terminée !"
echo "======================================"
echo ""
echo "📋 Prochaines étapes :"
echo ""
echo "1️⃣  Configurer vos credentials :"
echo "   nano .env"
echo ""
echo "2️⃣  Lancer le système :"
echo "   source .venv/bin/activate"
echo "   python main.py"
echo ""
echo "3️⃣  Accéder au dashboard :"
echo "   http://localhost:8888"
echo "   (Credentials dans .env : DASHBOARD_USERNAME/PASSWORD)"
echo ""
echo "📚 Documentation :"
echo "   - README.md : guide complet"
echo "   - CONTRIBUTING.md : guide de développement"
echo "   - CHANGELOG.md : historique des versions"
echo ""
echo "💡 Commandes utiles :"
echo "   python main.py              # Lancer le système"
echo "   pytest tests/unit/ -v       # Lancer les tests"
echo "   python dashboard.py         # Dashboard seul"
echo ""
echo "🆘 Besoin d'aide ?"
echo "   Email : contact@oktagon-shop.com"
echo "   Issues : https://github.com/oktagon/oktagon-sav/issues"
echo ""
echo "🚀 Bon développement avec OKTAGON SAV !"
echo ""
