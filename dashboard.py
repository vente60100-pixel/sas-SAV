"""
OKTAGON SAV v11.0 — DASHBOARD API + REACT FRONTEND
Backend API pur. Le frontend React est servi via StaticFiles.
"""
import html
import json
import os
import time
import secrets
from typing import Optional
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from logger import logger

app = FastAPI(title="OKTAGON SAV Cockpit", docs_url=None, redoc_url=None)
security = HTTPBasic()

# Références injectées par main.py
_db = None
_repos = None
_shopify = None
_email_connector = None
_claude = None
_config = None
_tenant_id = 'oktagon'

def init_dashboard(db, repos, shopify_connector=None, email_connector=None,
                   claude_connector=None, config=None):
    global _db, _repos, _shopify, _email_connector, _claude, _config
    _db = db
    _repos = repos
    _shopify = shopify_connector
    _email_connector = email_connector
    _claude = claude_connector
    _config = config


def _verify(creds: HTTPBasicCredentials = Depends(security)):
    user_ok = secrets.compare_digest(creds.username, os.environ.get('DASHBOARD_USERNAME', 'admin'))
    pass_ok = secrets.compare_digest(creds.password, os.environ.get('DASHBOARD_PASSWORD', 'admin'))
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="Non autorise",
                            headers={"WWW-Authenticate": "Basic"})
    return creds.username


# ================================================================
# API ENDPOINTS
# ================================================================

@app.get("/api/stats")
async def api_stats(user: str = Depends(_verify), period: str = 'today'):
    stats = await _repos.get_dashboard_stats(_tenant_id, period)
    categories = await _repos.get_stats_by_category(_tenant_id, period)
    # Daily stats pour graphique
    daily = []
    try:
        rows = await _db.fetch_all(
            """SELECT DATE(created_at) as d, COUNT(*) as c
               FROM processed_emails WHERE tenant_id = $1
               AND created_at > NOW() - INTERVAL '30 days'
               GROUP BY DATE(created_at) ORDER BY d""",
            _tenant_id
        )
        daily = [{'date': r['d'].strftime('%d/%m'), 'count': r['c']} for r in rows]
    except Exception:
        pass
    stats['categories'] = categories
    stats['daily'] = daily
    return JSONResponse(stats)



@app.get("/api/intelligence")
async def api_intelligence(user: str = Depends(_verify), period: str = '7d'):
    """
    Métriques d'intelligence de l'IA.

    Retourne:
    - Taux de catégorisation correcte (% de non-AUTRE)
    - Taux de confiance moyen
    - Taux d'escalation
    - Performance par catégorie
    - Évolution sur période
    """
    try:
        # Calculer l'intervalle
        if period == 'today':
            interval = "24 HOURS"
        elif period == '7d':
            interval = "7 DAYS"
        elif period == '30d':
            interval = "30 DAYS"
        else:
            interval = "7 DAYS"

        # 1. TAUX DE CATÉGORISATION (% non-AUTRE)
        categorization = await _db.fetch_one(f"""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN category != 'AUTRE' THEN 1 END) as categorized,
                COUNT(CASE WHEN category = 'AUTRE' THEN 1 END) as other,
                ROUND(100.0 * COUNT(CASE WHEN category != 'AUTRE' THEN 1 END) / NULLIF(COUNT(*), 0), 1) as categorization_rate
            FROM processed_emails
            WHERE tenant_id = $1
            AND created_at > NOW() - INTERVAL '{interval}'
            AND category IS NOT NULL
        """, _tenant_id)

        # 2. CONFIANCE MOYENNE PAR CATÉGORIE
        confidence_by_cat = await _db.fetch_all(f"""
            SELECT
                category,
                COUNT(*) as count,
                ROUND(AVG(confidence_score)::numeric, 2) as avg_confidence,
                ROUND(MIN(confidence_score)::numeric, 2) as min_confidence,
                ROUND(MAX(confidence_score)::numeric, 2) as max_confidence
            FROM processed_emails
            WHERE tenant_id = $1
            AND created_at > NOW() - INTERVAL '{interval}'
            AND category IS NOT NULL
            AND confidence_score IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
        """, _tenant_id)

        # 3. TAUX D'ESCALATION
        escalation_rate = await _db.fetch_one(f"""
            SELECT
                COUNT(*) as total_emails,
                COUNT(CASE WHEN escalated = true THEN 1 END) as escalated,
                ROUND(100.0 * COUNT(CASE WHEN escalated = true THEN 1 END) / NULLIF(COUNT(*), 0), 1) as escalation_rate
            FROM processed_emails
            WHERE tenant_id = $1
            AND created_at > NOW() - INTERVAL '{interval}'
        """, _tenant_id)

        # 4. RAISONS D'ESCALATION (top 5)
        escalation_reasons = await _db.fetch_all(f"""
            SELECT
                reason,
                COUNT(*) as count
            FROM escalations
            WHERE tenant_id = $1
            AND created_at > NOW() - INTERVAL '{interval}'
            AND status = 'pending'
            GROUP BY reason
            ORDER BY count DESC
            LIMIT 5
        """, _tenant_id)

        # 5. ÉVOLUTION JOURNALIÈRE (7 derniers jours)
        daily_intelligence = await _db.fetch_all("""
            SELECT
                DATE(created_at) as date,
                COUNT(*) as total,
                COUNT(CASE WHEN category != 'AUTRE' THEN 1 END) as categorized,
                ROUND(AVG(confidence_score)::numeric, 2) as avg_confidence,
                COUNT(CASE WHEN escalated = true THEN 1 END) as escalated
            FROM processed_emails
            WHERE tenant_id = $1
            AND created_at > NOW() - INTERVAL '7 DAYS'
            AND category IS NOT NULL
            GROUP BY DATE(created_at)
            ORDER BY date
        """, _tenant_id)

        # 6. PERFORMANCE TEMPS RÉEL (dernières 24h)
        realtime = await _db.fetch_one("""
            SELECT
                COUNT(*) as emails_24h,
                COUNT(CASE WHEN ai_response_sent = true THEN 1 END) as ai_responses,
                ROUND(100.0 * COUNT(CASE WHEN ai_response_sent = true THEN 1 END) / NULLIF(COUNT(*), 0), 1) as ai_response_rate,
                ROUND(AVG(EXTRACT(EPOCH FROM (responded_at - created_at)))::numeric, 0) as avg_response_time_seconds
            FROM processed_emails
            WHERE tenant_id = $1
            AND created_at > NOW() - INTERVAL '24 HOURS'
        """, _tenant_id)

        # Formatter la réponse
        result = {
            'period': period,
            'categorization': {
                'total': categorization['total'] or 0,
                'categorized': categorization['categorized'] or 0,
                'other': categorization['other'] or 0,
                'rate': float(categorization['categorization_rate'] or 0)
            },
            'confidence_by_category': [
                {
                    'category': row['category'],
                    'count': row['count'],
                    'avg_confidence': float(row['avg_confidence'] or 0),
                    'min_confidence': float(row['min_confidence'] or 0),
                    'max_confidence': float(row['max_confidence'] or 0)
                }
                for row in confidence_by_cat
            ],
            'escalation': {
                'total_emails': escalation_rate['total_emails'] or 0,
                'escalated': escalation_rate['escalated'] or 0,
                'rate': float(escalation_rate['escalation_rate'] or 0)
            },
            'escalation_reasons': [
                {'reason': row['reason'], 'count': row['count']}
                for row in escalation_reasons
            ],
            'daily_trend': [
                {
                    'date': row['date'].strftime('%Y-%m-%d'),
                    'total': row['total'],
                    'categorized': row['categorized'],
                    'avg_confidence': float(row['avg_confidence'] or 0),
                    'escalated': row['escalated']
                }
                for row in daily_intelligence
            ],
            'realtime_24h': {
                'emails': realtime['emails_24h'] or 0,
                'ai_responses': realtime['ai_responses'] or 0,
                'ai_response_rate': float(realtime['ai_response_rate'] or 0),
                'avg_response_time': int(realtime['avg_response_time_seconds'] or 0)
            }
        }

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Erreur /api/intelligence: {e}")
        return JSONResponse({
            'error': str(e),
            'period': period,
            'categorization': {'total': 0, 'categorized': 0, 'other': 0, 'rate': 0},
            'confidence_by_category': [],
            'escalation': {'total_emails': 0, 'escalated': 0, 'rate': 0},
            'escalation_reasons': [],
            'daily_trend': [],
            'realtime_24h': {'emails': 0, 'ai_responses': 0, 'ai_response_rate': 0, 'avg_response_time': 0}
        })


@app.get("/api/clients")
async def api_clients(user: str = Depends(_verify), search: str = '', limit: int = 50, offset: int = 0):
    clients = await _repos.get_all_clients(_tenant_id, search or None, limit, offset)
    return JSONResponse({'clients': clients})


@app.get("/api/clients/{email:path}")
async def api_client_detail(email: str, user: str = Depends(_verify)):
    detail = await _repos.get_client_detail(_tenant_id, email)
    return JSONResponse(detail)


@app.get("/api/pipeline")
async def api_pipeline(user: str = Depends(_verify), limit: int = 50, offset: int = 0, category: str = ''):
    emails = await _repos.get_recent_emails(_tenant_id, limit, offset, category or None)
    return JSONResponse({'emails': emails})


@app.get("/api/escalations")
async def api_escalations(user: str = Depends(_verify)):
    pending = await _repos.get_pending_escalations(_tenant_id)
    return JSONResponse({'escalations': pending, 'count': len(pending)})


@app.post("/api/escalations/{esc_id}/resolve")
async def api_resolve_escalation(esc_id: int, request: Request, user: str = Depends(_verify)):
    body = await request.json()
    action = body.get('action', 'resolved')
    response_text = body.get('response_text')
    await _repos.resolve_escalation(esc_id, action=action, response=response_text)
    # v10.0 — Apprentissage : si une reponse humaine est fournie, sauver comme exemple
    if response_text and response_text.strip():
        try:
            from core.auto_scoring import learn_from_escalation
            await learn_from_escalation(_db, _tenant_id, esc_id, response_text)
        except Exception as e:
            logger.debug(f"Erreur learn_from_escalation: {e}")
    return JSONResponse({'ok': True})


@app.get("/api/settings")
async def api_get_settings(user: str = Depends(_verify)):
    """Charge tous les settings depuis la DB (tenant + custom_rules)."""
    try:
        tenant = await _db.fetch_one("SELECT * FROM tenants WHERE id = $1", _tenant_id)
        if not tenant:
            return JSONResponse({})
        result = {
            'brand_name': tenant.get('brand_name', ''),
            'return_address': tenant.get('return_address', ''),
        }
        cr = tenant.get('custom_rules')
        if cr:
            rules = json.loads(cr) if isinstance(cr, str) else cr
            result.update(rules)
        return JSONResponse(result)
    except Exception as e:
        logger.debug(f"Erreur get_settings: {e}")
        return JSONResponse({})


@app.post("/api/settings")
async def api_save_settings(request: Request, user: str = Depends(_verify)):
    body = await request.json()
    brand = body.pop('brand_name', None)
    ret_addr = body.pop('return_address', None)
    # Sauver brand_name et return_address dans les colonnes dediees
    if brand or ret_addr:
        await _db.execute(
            "UPDATE tenants SET brand_name = COALESCE($1, brand_name), return_address = COALESCE($2, return_address) WHERE id = $3",
            brand, ret_addr, _tenant_id
        )
    # Sauver tout le reste dans custom_rules (JSONB)
    if body:
        # Merger avec les rules existantes
        tenant = await _db.fetch_one("SELECT custom_rules FROM tenants WHERE id = $1", _tenant_id)
        existing = {}
        if tenant and tenant.get('custom_rules'):
            cr = tenant['custom_rules']
            existing = json.loads(cr) if isinstance(cr, str) else cr
        existing.update(body)
        await _db.execute(
            "UPDATE tenants SET custom_rules = $1 WHERE id = $2",
            json.dumps(existing), _tenant_id
        )
    return JSONResponse({'ok': True})


@app.post("/api/chat")
async def api_chat(request: Request, user: str = Depends(_verify)):
    body = await request.json()
    message = body.get('message', '')
    if not message.strip():
        return JSONResponse({'response': 'Message vide'})
    try:
        # Importer le chat handler
        from dashboard_chat import handle_chat_message
        response = await handle_chat_message(message, _db, _repos, _shopify, _claude, _tenant_id)
        return JSONResponse({'response': response})
    except Exception as e:
        logger.error(f"Chat erreur: {e}")
        return JSONResponse({'response': f'Erreur: {str(e)}'})


@app.post("/api/send-email")
async def api_send_email(request: Request, user: str = Depends(_verify)):
    body = await request.json()
    to_email = body.get('to', '')
    subject = body.get('subject', 'OKTAGON SAV')
    email_body = body.get('body', '')
    if not to_email or not email_body:
        return JSONResponse({'ok': False, 'error': 'Champs manquants'})
    try:
        if _email_connector:
            from knowledge.templates import email_template
            html_body = email_template(email_body)
            await _email_connector.send_email(to_email, subject, html_body)
            return JSONResponse({'ok': True})
        return JSONResponse({'ok': False, 'error': 'Email connector non disponible'})
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)})


# ================================================================
# REACT FRONTEND (fichiers statiques)

# ================================================================
# v6.0 — Metrics and Health Endpoints
# ================================================================

@app.get("/api/metrics")
async def get_metrics():
    """Get real-time system metrics"""
    from core.metrics import metrics
    
    return {
        "emails": {
            "received": metrics.emails_received,
            "processed": metrics.emails_processed,
            "filtered": metrics.emails_filtered,
            "duplicates": metrics.emails_duplicates,
            "rate_limited": metrics.emails_rate_limited
        },
        "responses": {
            "sent": metrics.responses_sent,
            "escalated": metrics.responses_escalated,
            "failed": metrics.responses_failed
        },
        "ai": {
            "calls_success": metrics.ai_calls_success,
            "calls_failed": metrics.ai_calls_failed,
            "success_rate": round(metrics.ai_success_rate, 2),
            "tool_uses": metrics.ai_tool_uses,
            "avg_duration_ms": round(metrics.timing_ai_calls.avg, 2) if metrics.timing_ai_calls.count > 0 else 0
        },
        "shopify": {
            "calls_success": metrics.shopify_calls_success,
            "calls_failed": metrics.shopify_calls_failed,
            "success_rate": round(metrics.shopify_success_rate, 2),
            "avg_duration_ms": round(metrics.timing_shopify_calls.avg, 2) if metrics.timing_shopify_calls.count > 0 else 0
        },
        "performance": {
            "email_processing_avg_ms": round(metrics.timing_email_processing.avg, 2) if metrics.timing_email_processing.count > 0 else 0,
            "processing_rate_per_min": round(metrics.processing_rate, 2)
        },
        "system": {
            "uptime_seconds": round(metrics.uptime_seconds, 1),
            "escalation_rate": round(metrics.escalation_rate, 2),
            "filter_rate": round(metrics.filter_rate, 2)
        }
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring"""
    from core.metrics import metrics
    
    health = metrics.get_health()
    
    return {
        "status": health["status"],
        "timestamp": time.time(),
        "checks": {
            "ai_success_rate": {
                "value": metrics.ai_success_rate,
                "threshold": 95.0,
                "healthy": metrics.ai_success_rate >= 95.0
            },
            "shopify_success_rate": {
                "value": metrics.shopify_success_rate,
                "threshold": 90.0,
                "healthy": metrics.shopify_success_rate >= 90.0
            },
            "escalation_rate": {
                "value": metrics.escalation_rate,
                "threshold": 30.0,
                "healthy": metrics.escalation_rate <= 30.0
            }
        },
        "message": health.get("message", "System operational")
    }


@app.get("/api/circuit-breakers")
async def get_circuit_breakers():
    """Get circuit breaker states"""
    from core.circuit_breaker import shopify_circuit, claude_circuit, gmail_circuit
    
    def circuit_info(cb):
        return {
            "name": cb.name,
            "state": cb.state.value,
            "failure_count": cb.failure_count,
            "success_count": cb.success_count,
            "last_failure_time": cb.last_failure_time
        }
    
    return {
        "shopify": circuit_info(shopify_circuit),
        "claude": circuit_info(claude_circuit),
        "gmail": circuit_info(gmail_circuit)
    }


# ================================================================

# Monter les fichiers React APRES les API routes
_frontend_dir = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')
if os.path.isdir(_frontend_dir):
    # Servir index.html pour toutes les routes non-API (React Router)
    @app.get("/{path:path}")
    async def serve_react(path: str):
        import pathlib
        file_path = pathlib.Path(_frontend_dir) / path
        if file_path.is_file():
            # Servir le fichier statique
            return FileResponse(str(file_path))
        # Sinon servir index.html (React Router)
        return FileResponse(os.path.join(_frontend_dir, 'index.html'))
else:
    @app.get("/")
    async def no_frontend():
        return HTMLResponse("<h1>Frontend non build. Run: cd frontend && npm run build</h1>")
