# PLAN D'ATTAQUE — SAS SAV OKTAGON
## De code cassé → Production opérationnelle 100%

---

## ÉTAT ACTUEL
- **pipeline.py** : Code corrompu (lignes 97-112), ne compile pas
- **Base de données** : Tables et colonnes manquantes
- **Dashboard** : 3 fonctions cassées (chat, email, SQL injection)
- **Anti-spam** : Rate limiting inversé → mails en masse
- **Config** : .env.example incompatible avec config.py
- **Catégories** : 2 listes différentes dans 2 fichiers
- **Multi-tenant** : init_dashboard écrase les tenants précédents

---

## PHASE 1 — COEUR DU SYSTÈME (Pipeline)
> Objectif : Le pipeline compile, démarre, et traite un email sans crash

### 1.1 Réparer pipeline.py (code corrompu)
**Fichier** : `core/pipeline.py` lignes 97-112
**Bug** : Fragments SQL orphelins après un `return`, résultat de patches mal fusionnés
**Action** : Remplacer le bloc corrompu par une vraie protection anti-doublon propre :
```python
# Protection anti-doublon (v10.5 — propre)
if ticket.subject and ticket.subject.startswith("Re: Re:"):
    already_sent = await self.repos.count_recent_responses(
        self.tenant.id, ticket.email_from, hours=24
    )
    if already_sent > 0:
        logger.warning(
            f"DUPLICATE BLOQUÉ: {ticket.email_from} ({already_sent} réponses en 24h)",
            extra={"action": "duplicate_prevented"}
        )
        return
    logger.info(
        f"Re: Re: détecté mais aucune réponse envoyée — traitement normal",
        extra={"action": "first_response_needed"}
    )
```

### 1.2 Fixer le rate limiting inversé
**Fichier** : `storage/repos.py` lignes 191-209
**Bug** : La requête SQL cherche `email_from` mais reçoit `email_to` en paramètre
**Action** : Remplacer `email_from` par `email_to` dans les 2 requêtes SQL de `can_send()`
**Impact** : C'est CE BUG qui a causé l'envoi de mails en masse

### 1.3 Ajouter la méthode `count_recent_responses` dans repos.py
**Fichier** : `storage/repos.py`
**Action** : Ajouter une méthode propre utilisée par le fix 1.1 :
```python
async def count_recent_responses(self, tenant_id, email_to, hours=24):
    row = await self.db.fetch_one(
        """SELECT COUNT(*) as c FROM processed_emails
           WHERE tenant_id = $1 AND email_from = $2
           AND response_sent = true
           AND created_at > NOW() - INTERVAL '$3 hours'""",
        tenant_id, email_to, hours
    )
    return row['c'] if row else 0
```

### 1.4 Fixer main.py — init_dashboard hors de la boucle
**Fichier** : `main.py` lignes 160-175
**Bug** : `init_dashboard()` est appelée dans la boucle `for tenant in tenants`, écrase l'état à chaque itération
**Action** : Sortir l'appel APRÈS la boucle. Passer un dict de pipelines par tenant_id au lieu d'un seul set de connecteurs.

### 1.5 Fixer main.py — pipeline.db n'existe pas
**Fichier** : `main.py` ligne 202
**Bug** : `pipeline.db` n'est pas un attribut de Pipeline
**Action** : Remplacer `pipeline.db` par `db` (la variable locale déjà définie plus haut)

### 1.6 Fixer main.py — load_dotenv avant Sentry
**Fichier** : `main.py` lignes 6-15
**Bug** : `sentry_init` est importé AVANT `load_dotenv()`, donc Sentry n'a pas les env vars
**Action** : Déplacer `load_dotenv()` tout en haut, AVANT les imports locaux

---

## PHASE 2 — BASE DE DONNÉES (Tables & Colonnes manquantes)
> Objectif : Toutes les tables et colonnes existent, les migrations passent

### 2.1 Créer la table `tickets`
**Fichier** : `storage/schema.py`
**Bug** : `workers/ticket_tracker.py` fait des INSERT/SELECT sur `tickets` mais la table n'est jamais créée
**Action** : Ajouter la migration CREATE TABLE IF NOT EXISTS tickets

### 2.2 Créer la table `feedback_examples`
**Fichier** : `storage/schema.py`
**Bug** : `core/learning.py` et `workers/followup.py` utilisent cette table
**Action** : Ajouter la migration CREATE TABLE IF NOT EXISTS feedback_examples

### 2.3 Ajouter la colonne `response_text`
**Fichier** : `storage/schema.py`
**Bug** : Utilisée 20+ fois dans `repos.py` mais jamais créée
**Action** : ALTER TABLE processed_emails ADD COLUMN IF NOT EXISTS response_text TEXT

### 2.4 Fixer les SQL sans placeholders
**Fichier** : `core/auto_scoring.py` lignes 376, 389-390, 400
**Bug** : Les requêtes SQL n'ont pas de $1, $2, $3 :
```sql
WHERE e.id =  AND e.tenant_id = ""     -- VIDE
WHERE tenant_id =  AND category =       -- VIDE
VALUES (, , , , , NOW())                 -- VIDE
```
**Action** : Remettre les placeholders :
- Ligne 376 : `WHERE e.id = $1 AND e.tenant_id = $2`
- Ligne 389-390 : `WHERE tenant_id = $1 AND category = $2 AND client_message = $3`
- Ligne 400 : `VALUES ($1, $2, $3, $4, $5, NOW())`

### 2.5 Harmoniser les defaults tenants
**Fichier** : `tenants/models.py` vs `storage/schema.py`
**Bug** : `max_emails_per_hour` = 10 dans le code, 3 en DB
**Action** : Aligner sur la valeur du code (10/heure, 30/jour) dans les deux fichiers

---

## PHASE 3 — DASHBOARD & FRONTEND
> Objectif : Le dashboard se connecte, le chat fonctionne, pas d'injection SQL

### 3.1 Fixer le nom de fonction du chat
**Fichier** : `dashboard.py` ligne 340
**Bug** : Importe `handle_chat_message` mais la fonction s'appelle `chat_with_tools`
**Action** : Ajouter un alias dans `dashboard_chat.py` :
```python
# Alias pour compatibilité
handle_chat_message = chat_with_tools
```

### 3.2 Fixer l'injection SQL
**Fichier** : `dashboard.py` lignes 100-110
**Bug** : `interval` interpolé en f-string dans le SQL
**Action** : Valider `interval` dans une whitelist (`'24 hours'`, `'7 days'`, `'30 days'`) avant interpolation. Comme PostgreSQL ne supporte pas les paramètres dans INTERVAL, on valide strictement côté Python.

### 3.3 Fixer le login frontend
**Fichier** : `frontend/src/App.jsx` lignes 17-20
**Bug** : `setAuthed(true)` est appelé AVANT que le login soit vérifié
**Action** : Faire un appel API de test (`getStats()`) et ne mettre `authed=true` que si ça réussit (status 200)

### 3.4 Fixer l'ordre dans Escalations
**Fichier** : `frontend/src/pages/Escalations.jsx` lignes 31-32
**Bug** : Email envoyé AVANT de résoudre l'escalation → double envoi si erreur
**Action** : Inverser l'ordre : résoudre d'abord, envoyer ensuite. Si envoi échoue, annuler la résolution.

---

## PHASE 4 — CONFIGURATION & COHÉRENCE
> Objectif : Le .env fonctionne du premier coup, les catégories sont unifiées

### 4.1 Fixer .env.example
**Fichier** : `.env.example`
**Bug** : Les clés ne correspondent pas à config.py :
| .env.example (faux) | config.py (correct) |
|---|---|
| DB_HOST | POSTGRES_HOST |
| DB_PORT | POSTGRES_PORT |
| DB_NAME | POSTGRES_DB |
| DB_USER | POSTGRES_USER |
| DB_PASSWORD | POSTGRES_PASSWORD |
| GMAIL_USER | GMAIL_ADDRESS |
**Action** : Corriger .env.example avec les bons noms + ajouter les variables manquantes (CLAUDE_MODEL, AUTONOMY_LEVEL, etc.)

### 4.2 Unifier les catégories
**Fichiers** : `core/constants.py` et `core/validators.py`
**Bug** : 2 listes complètement différentes :
- constants.py : LIVRAISON, MODIFIER_ADRESSE, ANNULATION, RETOUR_ECHANGE, QUESTION_PRODUIT, SPONSORING, AFFILIATION, AUTRE, SPAM
- validators.py : LIVRAISON, COMMANDE, RETOUR, PERSONNALISATION, PRODUIT, PAIEMENT, AUTRE, PRE_ACHAT

**Action** : Fusionner en une seule liste de référence dans constants.py, et validators.py l'importe :
```python
CATEGORIES = [
    'LIVRAISON', 'MODIFIER_ADRESSE', 'ANNULATION',
    'RETOUR_ECHANGE', 'QUESTION_PRODUIT',
    'SPONSORING', 'AFFILIATION', 'AUTRE', 'SPAM'
]
```
Le validators.py utilise `from core.constants import CATEGORIES` comme source unique.

### 4.3 Fixer le hash salt hardcodé
**Fichier** : `config.py` ligne 62
**Bug** : Salt en dur dans le code source
**Action** : Charger depuis .env avec fallback :
```python
hash_salt: str = os.getenv('HASH_SALT', 'oktagon_sav_v24')
```

### 4.4 Fixer le chemin logger hardcodé
**Fichier** : `logger.py` ligne 105
**Bug** : Chemin `/root/oktagon-sav/logs` en dur
**Action** : Utiliser `Path(__file__).parent / 'logs'` pour être relatif au projet

---

## PHASE 5 — MULTI-TENANT PROPRE
> Objectif : Plusieurs boutiques peuvent tourner en parallèle

### 5.1 Refactorer init_dashboard pour multi-tenant
**Fichier** : `dashboard.py`
**Action** : Au lieu de stocker un seul set de connecteurs globaux, stocker un dict par tenant_id :
```python
_tenants = {}  # {tenant_id: {db, repos, shopify, email, claude}}

def init_dashboard(tenant_id, db, repos, shopify, email, claude, config):
    _tenants[tenant_id] = {
        'db': db, 'repos': repos, 'shopify': shopify,
        'email': email, 'claude': claude
    }
```
Les endpoints API recevront un header ou paramètre `tenant_id` pour sélectionner le bon tenant.

### 5.2 Ajouter tenant_id aux routes API
**Fichier** : `dashboard.py`
**Action** : Ajouter un paramètre `tenant_id` dans les routes (query param ou header). Fallback sur le premier tenant si un seul existe (backward compatible).

---

## PHASE 6 — ROBUSTESSE & SÉCURITÉ
> Objectif : Le système ne crash plus, gère les erreurs, et est sécurisé

### 6.1 Fixer les accès asyncpg.Record
**Fichiers** : `repos.py`, `emotional_intelligence.py`, `client_memory.py`, `conversation_reader.py`
**Bug** : Plusieurs endroits utilisent `.get()` ou `.keys()` sur des asyncpg.Record (qui sont des tuples nommés, pas des dicts)
**Action** : Convertir les Record en dict quand nécessaire : `dict(row)` avant accès

### 6.2 Fixer les timezone
**Fichiers** : `logger.py`, `info_extractor.py`
**Bug** : Mélange `datetime.now()` et `datetime.utcnow()` (deprecated Python 3.12+)
**Action** : Utiliser `datetime.now(timezone.utc)` partout

### 6.3 Ajouter protection None dans repos.py
**Fichier** : `storage/repos.py` ligne 36
**Bug** : `body_preview[:200]` crash si None
**Action** : `(body_preview or '')[:200]`

### 6.4 Fixer security.py — détection langue
**Fichier** : `security.py` lignes 157-162
**Bug** : Si espagnol est max_count, retourne 'fr' au lieu de 'es'
**Action** : Ajouter la condition `elif es_count == max_count: return 'es'`

### 6.5 Fixer claude.py — vérification response.content
**Fichier** : `connectors/ai/claude.py` lignes 254, 314, 339
**Bug** : `response.content[0].text` sans vérifier que content existe et n'est pas vide
**Action** : Ajouter `if response.content and len(response.content) > 0` avant chaque accès

---

## PHASE 7 — NETTOYAGE & QUALITÉ
> Objectif : Code propre, pas de fichiers morts, prêt pour production

### 7.1 Archiver les fichiers obsolètes (NE PAS SUPPRIMER)
**Action** : Créer un dossier `_archive/` et y déplacer :
- `final_fix.py`
- `fix_duplicates.py`
- `fix_duplicate_api.py`
- `add_duplicate_check.py`
- `improved_duplicate_check.py`
- `anti_duplicate.py`
- Tous les `.bak` et `.bak_*`

### 7.2 Supprimer les imports dupliqués
**Fichier** : `main.py` lignes 33-34
**Action** : Supprimer les imports en double de `security` et `dashboard`

### 7.3 Fixer la version dans les logs
**Fichier** : `main.py` ligne 39
**Bug** : Log dit "v5.0" mais le fichier est "v10.0"
**Action** : Mettre "v10.5" partout

### 7.4 Ajouter compilation dans Makefile
**Fichier** : `Makefile`
**Action** : Ajouter `python -m py_compile` dans la cible `deploy` pour détecter les erreurs de syntaxe avant redémarrage

---

## PHASE 8 — TESTS DE VALIDATION
> Objectif : Vérifier que tout fonctionne avant connexion Gmail

### 8.1 Test de compilation
```bash
python -m py_compile main.py
python -m py_compile core/pipeline.py
python -m py_compile dashboard.py
```

### 8.2 Test de démarrage
```bash
python main.py
# Doit afficher : "OKTAGON SAV v10.5 — DÉMARRAGE" sans erreur
```

### 8.3 Test unitaires existants
```bash
pytest tests/ -v
# Tous les tests doivent passer
```

### 8.4 Test de connexion Gmail (mode test)
- Envoyer un email de test à la boîte SAV
- Vérifier que le pipeline le reçoit, le traite, et génère une réponse
- Vérifier que la protection anti-doublon fonctionne (renvoyer le même email)
- Vérifier que le rate limiting empêche le spam

---

## ORDRE D'EXÉCUTION

```
Phase 1 (Pipeline)        ███████████░░░░░  ~40% du travail
Phase 2 (Base de données) ████░░░░░░░░░░░░  ~15%
Phase 3 (Dashboard)       ████░░░░░░░░░░░░  ~15%
Phase 4 (Configuration)   ███░░░░░░░░░░░░░  ~10%
Phase 5 (Multi-tenant)    ██░░░░░░░░░░░░░░  ~8%
Phase 6 (Robustesse)      ██░░░░░░░░░░░░░░  ~7%
Phase 7 (Nettoyage)       █░░░░░░░░░░░░░░░  ~3%
Phase 8 (Tests)           █░░░░░░░░░░░░░░░  ~2%
```

## RÉSULTAT ATTENDU
À la fin de ces 8 phases :
- Le serveur démarre sans erreur
- Les emails sont reçus via IMAP et traités par l'IA
- Les réponses sont envoyées via SMTP (pas de spam)
- Le dashboard est fonctionnel (stats, chat, escalations)
- Le multi-tenant est opérationnel
- La protection anti-doublon empêche les boucles de mail
- Le rate limiting protège contre l'envoi en masse
