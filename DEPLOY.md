# Guide de Déploiement GitHub - OKTAGON SAV

Ce guide explique comment pousser le code vers GitHub et activer le CI/CD automatique.

## 📋 Prérequis

- Compte GitHub
- Git installé localement
- Code OKTAGON SAV prêt (version 10.0)

## 🚀 Étapes de Déploiement

### 1. Créer un Repo GitHub

**Option A : Via l'interface web GitHub**

1. Aller sur https://github.com/new
2. Nom du repo : `oktagon-sav`
3. Description : "Système IA de service client multi-tenant propulsé par Claude Sonnet 4.5"
4. Visibilité : **Private** (recommandé pour les secrets)
5. NE PAS initialiser avec README/License/gitignore (on a déjà tout)
6. Cliquer **Create repository**

**Option B : Via GitHub CLI**

```bash
# Installer gh si nécessaire
brew install gh  # macOS
# ou télécharger depuis https://cli.github.com/

# Se connecter
gh auth login

# Créer le repo
gh repo create oktagon-sav --private --source=. --remote=origin
```

### 2. Initialiser Git Localement

```bash
cd ~/oktagon-sav

# Initialiser le repo si pas déjà fait
git init

# Vérifier que .gitignore est bien là
ls -la .gitignore

# Ajouter tous les fichiers
git add .

# Vérifier que .env n'est PAS ajouté (doit être dans .gitignore)
git status | grep .env
# Si .env apparaît, c'est MAUVAIS ! Vérifier .gitignore

# Premier commit
git commit -m "feat: initial release v10.0 - production ready CI/CD

- GitHub Actions avec tests automatiques
- 87% code coverage (44 tests passing)
- Sentry monitoring integration
- SSL/TLS PostgreSQL
- Lie detector avec 30+ patterns
- Score 10/10 Series B+ ready

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 3. Pousser vers GitHub

```bash
# Ajouter le remote (remplacer VOTRE-USERNAME)
git remote add origin https://github.com/VOTRE-USERNAME/oktagon-sav.git

# Créer la branche main
git branch -M main

# Pousser le code
git push -u origin main
```

### 4. Configurer les Secrets GitHub

Les secrets GitHub sont nécessaires pour que le CI/CD fonctionne.

**Via l'interface web :**

1. Aller sur votre repo : `https://github.com/VOTRE-USERNAME/oktagon-sav`
2. Cliquer **Settings** > **Secrets and variables** > **Actions**
3. Cliquer **New repository secret**
4. Ajouter ces secrets :

| Nom | Valeur | Description |
|-----|--------|-------------|
| `CODECOV_TOKEN` | `votre_token` | Token Codecov pour upload coverage (optionnel) |

**Via GitHub CLI :**

```bash
# Codecov token (optionnel, mais recommandé)
gh secret set CODECOV_TOKEN --body "votre_token_codecov"
```

**Obtenir un token Codecov :**

1. Aller sur https://codecov.io/
2. Se connecter avec GitHub
3. Ajouter le repo `oktagon-sav`
4. Copier le token (format : `xxx-xxxxxx-xxxx-xxxx-xxxxxxxx`)

### 5. Activer GitHub Actions

**Les workflows se lancent automatiquement !**

1. Aller sur `https://github.com/VOTRE-USERNAME/oktagon-sav/actions`
2. Vous devriez voir le workflow **"Tests et Couverture"** en cours
3. Cliquer dessus pour voir les détails

Le workflow lance :
- ✅ **Tests unitaires** (44 tests avec PostgreSQL)
- ✅ **Linting** (flake8, black, isort)
- ✅ **Security scan** (Bandit, Safety)
- ✅ **Coverage upload** (Codecov)

### 6. Mettre à Jour le README

Une fois le repo créé, mettre à jour les badges dans [README.md](README.md) :

```bash
# Ouvrir README.md
nano README.md

# Remplacer VOTRE-USERNAME par votre vrai username GitHub (3 endroits)
# Ligne 3 : badge Tests
# Ligne 4 : badge Codecov
# Ligne 4 : lien Codecov

# Exemple :
# AVANT : https://github.com/VOTRE-USERNAME/oktagon-sav
# APRÈS : https://github.com/elbachiri/oktagon-sav

# Sauvegarder et committer
git add README.md
git commit -m "docs: update badges with real GitHub username"
git push
```

### 7. Vérifier les Badges

Après quelques minutes, les badges devraient être verts :

- ✅ **Tests** : passing (vert)
- ✅ **Codecov** : 87% (vert)
- ✅ **Python 3.10** : (bleu)
- ✅ **Code style: black** : (noir)

Si un badge est rouge :
1. Cliquer dessus pour voir l'erreur
2. Aller dans **Actions** pour les logs détaillés
3. Fixer le problème et re-push

## 🔧 Workflow CI/CD

### Déclencheurs

Le workflow se lance automatiquement sur :
- ✅ **Push** vers `main` ou `develop`
- ✅ **Pull Request** vers `main` ou `develop`
- ✅ **Manuel** via l'interface Actions

### Jobs Exécutés

**1. Tests (Python 3.10)**
```
- Checkout code
- Setup Python 3.10
- Install dependencies
- Create test .env
- Run pytest avec coverage
- Upload coverage à Codecov
- Upload HTML report (artifacts)
- Comment PR avec coverage
```

**2. Linting**
```
- black --check (formatage)
- isort --check (imports)
- flake8 (style + erreurs)
```

**3. Security**
```
- Bandit (vulnérabilités Python)
- Safety (dépendances vulnérables)
- Upload rapports (artifacts)
```

### Artefacts Conservés

Les rapports sont disponibles 30 jours :
- 📊 **Coverage HTML** : htmlcov/
- 🔒 **Security reports** : bandit-report.json

Accès : `Actions` > `Workflow run` > `Artifacts`

## 🌿 Workflow de Développement

### Feature Branch

```bash
# Créer une branche pour nouvelle fonctionnalité
git checkout -b feature/dashboard-react

# Faire des modifications...
git add .
git commit -m "feat(dashboard): add React frontend with graphs"

# Pousser la branche
git push -u origin feature/dashboard-react
```

### Pull Request

```bash
# Via GitHub CLI
gh pr create --title "feat: Dashboard React moderne" --body "Ajoute interface React..."

# Ou via l'interface web
# Aller sur https://github.com/VOTRE-USERNAME/oktagon-sav/pulls
# Cliquer "New pull request"
```

Le CI/CD se lance automatiquement sur le PR :
- ✅ Tests doivent passer
- ✅ Linting doit passer
- ✅ Security scan doit passer
- ✅ Coverage ne doit pas baisser

### Merge vers Main

```bash
# Après approbation du PR
gh pr merge 123 --squash --delete-branch

# Ou via l'interface web
# "Squash and merge" puis "Delete branch"
```

## 🚨 Troubleshooting

### Erreur : Tests échouent

```bash
# Lancer les tests localement
pytest tests/unit/ -v

# Vérifier la couverture
pytest tests/unit/ --cov=core --cov=storage --cov-report=html
open htmlcov/index.html
```

### Erreur : PostgreSQL connection failed

Le workflow GitHub Actions lance automatiquement PostgreSQL.

Si échec :
1. Vérifier [.github/workflows/tests.yml](/.github/workflows/tests.yml) ligne 13
2. Le service PostgreSQL doit être configuré correctement
3. Les credentials de test doivent matcher (test_user/test_password/test_db)

### Erreur : Codecov upload failed

C'est **non bloquant** (`fail_ci_if_error: false`).

Pour fixer :
1. Vérifier que le token `CODECOV_TOKEN` est bien dans les secrets
2. Vérifier le format du token (pas d'espaces)
3. Si pas de token, le badge restera gris (OK pour du privé)

### Erreur : Linting failed

```bash
# Formatter automatiquement
black core/ storage/ connectors/ handlers/ domain/ workers/

# Trier les imports
isort core/ storage/ connectors/ handlers/ domain/ workers/

# Vérifier
flake8 core/ storage/ connectors/ handlers/ domain/ workers/

# Committer les changements
git add .
git commit -m "style: format code with black + isort"
git push
```

## 📊 Monitoring Production

### Sentry Setup

Si vous déployez en production, configurer Sentry :

1. Créer un compte sur https://sentry.io
2. Créer un nouveau projet Python
3. Copier le DSN (format : `https://xxx@xxx.ingest.sentry.io/xxx`)
4. Mettre à jour `.env` :

```bash
SENTRY_DSN=https://votre_dsn_reel@sentry.ingest.io/123456
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
```

5. Redémarrer le service

Les erreurs seront automatiquement envoyées à Sentry.

### GitHub Actions Artifacts

Garder un œil sur les rapports de sécurité :

1. Aller dans **Actions**
2. Cliquer sur un workflow run
3. Télécharger **security-reports**
4. Lire `bandit-report.json`

## 🎯 Checklist de Déploiement

Avant de pousser en production :

- [ ] Tous les tests passent localement
- [ ] `.env` est dans `.gitignore` (vérifier `git status`)
- [ ] Secrets Shopify/Anthropic/Gmail sont dans `.env` (PAS dans le code)
- [ ] README.md badges mis à jour avec votre username
- [ ] Codecov token configuré dans GitHub Secrets
- [ ] Sentry DSN configuré (si monitoring souhaité)
- [ ] PostgreSQL accessible avec SSL/TLS
- [ ] Dashboard credentials changés (`DASHBOARD_PASSWORD`)
- [ ] Tests CI/CD passent sur GitHub Actions

## 📚 Ressources

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Codecov Docs](https://docs.codecov.com/)
- [Sentry Python Docs](https://docs.sentry.io/platforms/python/)
- [pytest Best Practices](https://docs.pytest.org/en/stable/goodpractices.html)

## 🤝 Support

Besoin d'aide ?
- 📧 Email : contact@oktagon-shop.com
- 💬 GitHub Issues : https://github.com/VOTRE-USERNAME/oktagon-sav/issues
- 📖 Documentation : [README.md](README.md)

---

**Fait avec ❤️ par OKTAGON | CI/CD par GitHub Actions**
