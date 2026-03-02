# Guide de Contribution - OKTAGON SAV

Merci de vouloir contribuer au projet OKTAGON SAV ! 🎉

## Code de Conduite

En participant à ce projet, vous acceptez de maintenir un environnement respectueux et professionnel.

## Comment Contribuer

### 1. Fork et Clone

```bash
# Fork le repo sur GitHub, puis :
git clone https://github.com/VOTRE-USERNAME/oktagon-sav.git
cd oktagon-sav
git remote add upstream https://github.com/oktagon/oktagon-sav.git
```

### 2. Créer une Branche

```bash
# Toujours créer une branche depuis main
git checkout main
git pull upstream main
git checkout -b feature/ma-nouvelle-fonctionnalite
```

Conventions de nommage :
- `feature/` : nouvelles fonctionnalités
- `fix/` : corrections de bugs
- `refactor/` : refactoring sans changement de comportement
- `test/` : ajout/amélioration de tests
- `docs/` : documentation uniquement

### 3. Environnement de Développement

```bash
# Créer un environnement virtuel
python3.10 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configurer pre-commit hooks
pre-commit install
```

### 4. Standards de Code

#### Style Python
- **Black** : formatage automatique (line-length=127)
- **isort** : tri des imports
- **flake8** : linting
- **mypy** : type checking (optionnel mais encouragé)

```bash
# Formatter le code
black core/ storage/ connectors/ handlers/ domain/ workers/

# Trier les imports
isort core/ storage/ connectors/ handlers/ domain/ workers/

# Vérifier le style
flake8 core/ storage/ connectors/ handlers/ domain/ workers/
```

#### Conventions
- **Langue** : code et commentaires en anglais, docstrings en français OK
- **Docstrings** : Google style pour les fonctions publiques
- **Type hints** : fortement encouragés pour les signatures publiques
- **Async** : toujours utiliser asyncio, jamais de code bloquant

#### Exemple de Bonne Fonction

```python
async def fetch_shopify_order(
    client: ShopifyClient,
    order_number: str
) -> Optional[dict]:
    """
    Récupère une commande Shopify par son numéro.

    Args:
        client: Client Shopify authentifié
        order_number: Numéro de commande (ex: "8650")

    Returns:
        dict: Données de la commande ou None si introuvable

    Raises:
        ShopifyAPIError: En cas d'erreur API
    """
    try:
        response = await client.get_order(order_number)
        return response.get('order')
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise ShopifyAPIError(f"API error: {e}") from e
```

### 5. Tests

**Tous les PRs doivent inclure des tests !**

```bash
# Lancer les tests
pytest tests/unit/ -v

# Avec couverture
pytest tests/unit/ --cov=core --cov=storage --cov=connectors --cov-report=html

# Tests spécifiques
pytest tests/unit/test_lie_detector.py -v -k "test_detect_temporal_lie"

# Ouvrir le rapport HTML
open htmlcov/index.html
```

#### Guidelines Tests
- **Coverage minimum** : 80% pour les nouveaux modules
- **Tests unitaires** : mocker les dépendances externes (Shopify, Anthropic, DB)
- **Tests async** : utiliser `pytest-asyncio` et `AsyncMock`
- **Nommage** : `test_<fonction>_<scenario>_<resultat_attendu>`

#### Exemple de Test

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_lie_detector_blocks_temporal_lie():
    """Le lie detector doit bloquer les mensonges temporels"""
    response_text = "Je viens de relancer votre dossier aujourd'hui même"

    is_clean, violations = detect_lies(response_text)

    assert is_clean is False
    assert len(violations) == 2
    assert any(v['type'] == 'ACTION_HUMAINE' for v in violations)
    assert any(v['type'] == 'TEMPS_IMPOSSIBLE' for v in violations)
```

### 6. Commits

#### Messages de Commit
Format : `type(scope): description`

Types :
- `feat` : nouvelle fonctionnalité
- `fix` : correction de bug
- `refactor` : refactoring
- `test` : ajout/modification de tests
- `docs` : documentation
- `chore` : tâches de maintenance
- `perf` : amélioration de performance

Exemples :
```
feat(lie-detector): add pattern for invented urgency
fix(pipeline): handle None in validate_response
test(validators): add test for placeholder detection
docs(readme): update installation instructions
refactor(database): simplify connection pool logic
```

### 7. Pull Request

#### Avant de Soumettre
- [ ] Le code passe tous les tests : `pytest tests/unit/`
- [ ] Le linting est OK : `flake8 .`
- [ ] Le formatage est correct : `black --check .`
- [ ] La couverture n'a pas baissé : `pytest --cov`
- [ ] La documentation est à jour
- [ ] Les secrets sont dans `.env` (jamais committés)

#### Créer le PR

1. **Push vers votre fork**
```bash
git push origin feature/ma-nouvelle-fonctionnalite
```

2. **Ouvrir le PR sur GitHub**
- Titre descriptif (même format que commits)
- Description détaillée avec :
  - Contexte et motivation
  - Changements effectués
  - Tests ajoutés
  - Screenshots si UI

3. **Template de Description**
```markdown
## Problème
[Décrivez le problème ou le besoin]

## Solution
[Expliquez votre approche]

## Changements
- [ ] Ajout de X dans le module Y
- [ ] Modification de Z pour supporter W
- [ ] Tests pour couvrir les cas A, B, C

## Tests
- [ ] Tests unitaires ajoutés (coverage: X%)
- [ ] Tests manuels effectués
- [ ] CI/CD passe en vert

## Screenshots
[Si applicable]

## Checklist
- [ ] Code formaté (black + isort)
- [ ] Tests passent
- [ ] Documentation mise à jour
- [ ] Pas de secrets committés
```

### 8. Review Process

1. **Automated checks** : CI/CD doit passer (tests, linting, security)
2. **Code review** : au moins 1 approbation requise
3. **Changes requested** : adresser les commentaires
4. **Merge** : squash & merge vers main

### 9. Bonnes Pratiques

#### Sécurité
- ❌ **Jamais** committer de secrets (API keys, passwords)
- ✅ Utiliser `.env` pour les credentials
- ✅ Ajouter `chmod 600 .env` dans les docs
- ✅ Scanner avec `bandit` avant PR

#### Performance
- ✅ Toujours utiliser `async/await` pour I/O
- ✅ Pool de connexions DB (asyncpg)
- ✅ Circuit breakers sur APIs externes
- ✅ Caching intelligent (Redis si nécessaire)

#### Logs
- ✅ Utiliser `logger.info/warning/error` (pas `print`)
- ✅ Inclure `extra={'action': 'xxx'}` pour Sentry
- ❌ Ne jamais logger de PII (emails, numéros de commande en clair)

#### Base de Données
- ✅ Toujours utiliser des paramètres bindés (protection SQL injection)
- ✅ Transactions pour les opérations critiques
- ✅ Index sur les colonnes fréquemment requêtées

### 10. Architecture Decisions

Pour les changements majeurs :
1. Ouvrir une **GitHub Discussion** d'abord
2. Expliquer le problème et les alternatives
3. Obtenir consensus avant d'implémenter
4. Documenter la décision dans `docs/adr/` (Architecture Decision Records)

### 11. Release Process

(Réservé aux mainteneurs)

1. Créer une branche `release/vX.Y.Z`
2. Mettre à jour `APP_VERSION` dans `.env.example`
3. Mettre à jour `CHANGELOG.md`
4. Créer un tag : `git tag vX.Y.Z`
5. Push le tag : `git push --tags`
6. GitHub Actions déploie automatiquement

## Questions ?

- 📧 Email : dev@oktagon-shop.com
- 💬 Discussions GitHub : [Discussions](https://github.com/oktagon/oktagon-sav/discussions)
- 🐛 Issues : [Issues](https://github.com/oktagon/oktagon-sav/issues)

## Remerciements

Merci de contribuer à faire d'OKTAGON SAV le meilleur système de service client IA ! 🚀
