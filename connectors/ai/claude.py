"""
OKTAGON SAV v11.0 — Connecteur Claude (Anthropic)
CERVEAU INTELLIGENT avec Tool Use natif.
L'IA peut chercher elle-même sur Shopify (par nom, confirmation, montant, tracking).
"""
import asyncio
import re
import json
import anthropic
from typing import Optional

from connectors.ai.base import AIConnector
from logger import logger


# ═══════════════════════════════════════════════════════════
# TOOLS SHOPIFY — Le cerveau peut appeler ces outils
# ═══════════════════════════════════════════════════════════

BRAIN_TOOLS = [
    {
        "name": "search_shopify_by_email",
        "description": "Cherche les commandes d'un client par son adresse email. Utilise cet outil quand tu connais l'email du client.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "L'adresse email du client"
                }
            },
            "required": ["email"]
        }
    },
    {
        "name": "search_shopify_by_name",
        "description": "Cherche une commande Shopify par nom et prénom du client. Utilise cet outil quand le client donne son nom mais pas son numéro de commande.",
        "input_schema": {
            "type": "object",
            "properties": {
                "first_name": {
                    "type": "string",
                    "description": "Le prénom du client"
                },
                "last_name": {
                    "type": "string",
                    "description": "Le nom de famille du client"
                }
            },
            "required": ["first_name", "last_name"]
        }
    },
    {
        "name": "search_shopify_by_confirmation",
        "description": "Cherche une commande par numéro de confirmation (code alphanumérique comme 5RLVXHTWI). Utilise cet outil quand le client donne un code de confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "confirmation_number": {
                    "type": "string",
                    "description": "Le numéro/code de confirmation"
                }
            },
            "required": ["confirmation_number"]
        }
    },
    {
        "name": "search_shopify_by_order_number",
        "description": "Cherche une commande par son numéro (ex: #8519, 8519). Utilise cet outil pour récupérer les détails d'une commande.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_number": {
                    "type": "string",
                    "description": "Le numéro de commande (avec ou sans #)"
                }
            },
            "required": ["order_number"]
        }
    },
    {
        "name": "search_shopify_by_amount",
        "description": "Cherche une commande par montant payé. Utilise cet outil quand le client mentionne un montant mais pas de numéro de commande.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "string",
                    "description": "Le montant en euros (ex: '59.99', '120')"
                },
                "email": {
                    "type": "string",
                    "description": "L'email du client (optionnel, pour filtrer)"
                }
            },
            "required": ["amount"]
        }
    }
]


async def execute_brain_tool(tool_name: str, tool_input: dict, shopify) -> str:
    """Exécute un outil Shopify et retourne le résultat en JSON."""
    try:
        if tool_name == "search_shopify_by_email":
            orders = await shopify.get_orders_by_email(tool_input["email"], limit=5)
            if orders:
                return json.dumps({"found": True, "orders": orders}, ensure_ascii=False, default=str)
            return json.dumps({"found": False, "message": "Aucune commande trouvée pour cet email"})

        elif tool_name == "search_shopify_by_name":
            orders = await shopify.search_orders_by_name(
                tool_input["first_name"], tool_input["last_name"]
            )
            if orders:
                return json.dumps({"found": True, "orders": orders}, ensure_ascii=False, default=str)
            return json.dumps({"found": False, "message": "Aucun client trouvé avec ce nom"})

        elif tool_name == "search_shopify_by_confirmation":
            order = await shopify.search_by_confirmation(tool_input["confirmation_number"])
            if order:
                return json.dumps({"found": True, "order": order}, ensure_ascii=False, default=str)
            return json.dumps({"found": False, "message": "Aucune commande trouvée avec ce code de confirmation"})

        elif tool_name == "search_shopify_by_order_number":
            order_num = tool_input["order_number"].replace("#", "").strip()
            order = await shopify.get_order(order_num)
            if order:
                return json.dumps({"found": True, "order": order}, ensure_ascii=False, default=str)
            return json.dumps({"found": False, "message": f"Commande #{order_num} non trouvée"})

        elif tool_name == "search_shopify_by_amount":
            orders = await shopify.search_by_amount(
                tool_input["amount"],
                tool_input.get("email")
            )
            if orders:
                return json.dumps({"found": True, "orders": orders}, ensure_ascii=False, default=str)
            return json.dumps({"found": False, "message": "Aucune commande trouvée pour ce montant"})

        else:
            return json.dumps({"error": f"Outil inconnu: {tool_name}"})

    except (OSError, ValueError, KeyError, TypeError) as e:
        logger.error(f"Erreur exécution tool {tool_name}: {e}")
        return json.dumps({"error": str(e)})


class ClaudeConnector(AIConnector):
    """Connecteur Anthropic Claude — v11.0 avec tool use + timeout."""

    # Timeout max par appel API Claude (secondes)
    API_TIMEOUT = 45

    def __init__(self, api_key: str, model: str = 'claude-sonnet-4-5-20250929',
                 max_tokens: int = 8000, temperature: float = 0.7):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def unified_process_with_tools(self, prompt: str, shopify) -> dict:
        """CERVEAU INTELLIGENT v8.0 — L'IA peut chercher sur Shopify elle-même.

        Boucle agentic : l'IA appelle des tools Shopify jusqu'à avoir assez d'infos,
        puis génère sa réponse finale en JSON.
        """
        try:
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            messages = [{"role": "user", "content": prompt}]
            tool_calls_count = 0
            max_tool_calls = 5  # Sécurité anti-boucle

            while True:
                response = await asyncio.wait_for(
                    client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        temperature=0.4,
                        tools=BRAIN_TOOLS,
                        messages=messages
                    ),
                    timeout=self.API_TIMEOUT
                )

                # Vérifier s'il y a des tool_use dans la réponse
                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

                if not tool_use_blocks:
                    # Pas de tool_use → réponse finale
                    text_blocks = [b for b in response.content if b.type == "text"]
                    if text_blocks:
                        return self._parse_json_response(text_blocks[0].text)
                    return self._empty_response()

                # Il y a des tool_use → les exécuter
                # D'abord, ajouter la réponse assistant complète
                messages.append({"role": "assistant", "content": response.content})

                # Exécuter chaque tool et collecter les résultats
                tool_results = []
                for block in tool_use_blocks:
                    tool_calls_count += 1
                    logger.info(
                        f"🔧 TOOL | {block.name}({json.dumps(block.input, ensure_ascii=False)[:100]})",
                        extra={"action": "brain_tool_call", "tool": block.name}
                    )

                    result = await execute_brain_tool(block.name, block.input, shopify)

                    logger.info(
                        f"🔧 RESULT | {block.name} → {result[:150]}",
                        extra={"action": "brain_tool_result", "tool": block.name}
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

                # Ajouter tous les résultats de tools dans le message user
                messages.append({"role": "user", "content": tool_results})

                # Sécurité anti-boucle
                if tool_calls_count >= max_tool_calls:
                    logger.warning(
                        f"⚠️ Max tool calls atteint ({max_tool_calls}), forçage réponse finale",
                        extra={"action": "brain_max_tools"}
                    )
                    # Forcer une réponse finale sans tools
                    final_response = await asyncio.wait_for(
                        client.messages.create(
                            model=self.model,
                            max_tokens=self.max_tokens,
                            temperature=0.4,
                            messages=messages
                        ),
                        timeout=self.API_TIMEOUT
                    )
                    text_blocks = [b for b in final_response.content if b.type == "text"]
                    if text_blocks:
                        return self._parse_json_response(text_blocks[0].text)
                    return self._empty_response()

        except asyncio.TimeoutError:
            logger.error("Timeout cerveau intelligent (API Claude ne répond pas)",
                         extra={"action": "brain_timeout"})
            return self._empty_response()
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            logger.error(f"Erreur auth Claude: {e}",
                         extra={"action": "brain_auth_error", "error": str(e)})
            return self._empty_response()
        except anthropic.APIError as e:
            logger.error(f"Erreur API Claude: {e}",
                         extra={"action": "brain_api_error", "error": str(e)})
            return self._empty_response()

    async def unified_process(self, prompt: str) -> dict:
        """CERVEAU UNIFIÉ v5.0 — Un seul appel pour tout (LEGACY, sans tools).

        Gardé pour compatibilité — utilisé quand pas de connecteur Shopify disponible.
        """
        try:
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            response = await asyncio.wait_for(
                client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=0.4,
                    messages=[{"role": "user", "content": prompt}]
                ),
                timeout=self.API_TIMEOUT
            )
            if not response.content:
                logger.warning("Claude a retourné une réponse vide")
                return self._empty_response()
            text = response.content[0].text.strip() if hasattr(response.content[0], 'text') else ''
            return self._parse_json_response(text)
        except asyncio.TimeoutError:
            logger.error("Timeout unified_process", extra={"action": "brain_timeout"})
            return self._empty_response()
        except anthropic.APIError as e:
            logger.error(f"Erreur API unified_process: {e}")
            return self._empty_response()

    def _parse_json_response(self, text: str) -> dict:
        """Parse la réponse JSON du cerveau."""
        text = text.strip()

        # Nettoyer le JSON si enveloppé dans ```
        if text.startswith('```'):
            text = re.sub(r'^```json\s*\n?', '', text)
            text = re.sub(r'\n?```\s*$', '', text)

        try:
            result = json.loads(text)
            return {
                "category": result.get("category", "AUTRE"),
                "response": result.get("response", ""),
                "action": result.get("action", "send"),
                "confidence": result.get("confidence", 0.5),
                "needs_order_number": result.get("needs_order_number", False),
                "summary": result.get("summary", "")
            }
        except json.JSONDecodeError:
            # L'IA a répondu en texte libre au lieu de JSON
            return {
                "category": "AUTRE",
                "response": text if text else "",
                "action": "send" if text else "send_and_escalate",
                "confidence": 0.6,
                "needs_order_number": False
            }

    def _empty_response(self) -> dict:
        """Réponse vide en cas d'erreur."""
        return {
            "category": "AUTRE",
            "response": "",
            "action": "send_and_escalate",
            "confidence": 0.0,
            "needs_order_number": False
        }

    # ═══════════════════════════════════════════════════════════
    # ANCIENNES MÉTHODES — gardées pour compatibilité
    # ═══════════════════════════════════════════════════════════

    async def generate(self, prompt: str, context: str) -> dict:
        """Appelle Claude pour générer une réponse SAV."""
        try:
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            full_prompt = f"{prompt}\n\nContexte client:\n{context}"
            response = await client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": full_prompt}]
            )
            text = response.content[0].text.strip()
            if text.startswith('```'):
                text = re.sub(r'^```json\s*\n', '', text)
                text = re.sub(r'\n```\s*$', '', text)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"response": text, "escalade": False, "confidence": 0.85}
        except (anthropic.APIError, asyncio.TimeoutError) as e:
            logger.error(f"Erreur generate: {e}")
            return {"response": "", "escalade": True, "confidence": 0.0}

    async def classify(self, subject: str, body: str, tenant=None) -> dict:
        """Classifie un email avec le Brain IA."""
        try:
            brand_name = tenant.brand_name if tenant else 'SAV'
            prompt = f"Classifie cet email SAV pour {brand_name}."
            prompt += f"\n\nEmail à classifier :\nSujet: {subject[:200]}\nCorps: {body[:800]}"

            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            response = await client.messages.create(
                model=self.model,
                max_tokens=300,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip()
            if text.startswith('```'):
                text = re.sub(r'^```json\s*\n', '', text)
                text = re.sub(r'\n```\s*$', '', text)
            result = json.loads(text)
            return {
                "category": result.get("category", "AUTRE"),
                "confidence": result.get("confidence", 0.5),
                "order_number": result.get("order_number"),
                "language": result.get("language", "fr"),
                "summary": result.get("summary", "")
            }
        except (anthropic.APIError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            logger.error(f"Erreur classify: {e}")
            return {"category": "AUTRE", "confidence": 0.0, "order_number": None, "language": "fr", "summary": ""}
