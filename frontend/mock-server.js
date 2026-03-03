/**
 * Mock API server for standalone frontend development.
 * Simulates the FastAPI backend with realistic demo data.
 * Run: node mock-server.js (port 8888)
 */
import http from 'http'

const PORT = 8888

// ── Demo data ──────────────────────────────────────────────

const ESCALATIONS = [
  {
    id: 1, email: 'ines.bk@gmail.com', category: 'ANNULATION',
    reason: "Cliente demande l'annulation de sa commande #8519 — personnalisation déjà lancée, politique retour non applicable.",
    subject: 'Annulation commande #8519', date: new Date(Date.now() - 3600000 * 2).toISOString(),
    preview: "Bonjour, je souhaite annuler ma commande car j'ai changé d'avis sur la taille. Merci de me confirmer le remboursement.",
    resolved: false,
    client_message: "Bonjour, je souhaite annuler ma commande #8519 car j'ai changé d'avis sur la taille. J'ai commandé un M mais je voulais un L. Est-ce possible d'annuler et de me rembourser ? Merci.",
    order: { number: '8519', total: '89.90', status: 'unfulfilled', items: ['Short MMA Custom - Taille M'], tracking: null },
    history: [
      { date: new Date(Date.now() - 86400000 * 3).toISOString(), from: 'client', text: "Bonjour, j'ai passé commande hier, tout est ok ?" },
      { date: new Date(Date.now() - 86400000 * 3).toISOString(), from: 'sav', text: "Bonjour Inès ! Votre commande #8519 est bien enregistrée. La fabrication sur mesure prend 12-15 jours. On vous tient informée !" },
      { date: new Date(Date.now() - 3600000 * 2).toISOString(), from: 'client', text: "Finalement je souhaite annuler, j'ai pris la mauvaise taille..." },
    ]
  },
  {
    id: 2, email: 'karim.fight@outlook.fr', category: 'RETOUR_ECHANGE',
    reason: "Client mécontent — article reçu avec défaut de couture, demande échange ou remboursement. Photo jointe.",
    subject: 'Problème qualité commande #8472', date: new Date(Date.now() - 3600000 * 8).toISOString(),
    preview: "Mon short a une couture qui lâche après seulement 2 entraînements. C'est pas sérieux pour le prix...",
    resolved: false,
    client_message: "Bonjour, j'ai reçu mon short personnalisé la semaine dernière et après seulement 2 entraînements la couture au niveau de la cuisse droite a complètement lâché. Pour un produit à 90€ c'est vraiment pas acceptable. Je veux un échange ou un remboursement. J'ai des photos si besoin.",
    order: { number: '8472', total: '94.90', status: 'fulfilled', items: ['Short MMA Pro Custom - Taille L', 'Flocage prénom'], tracking: 'LP123456789FR' },
    history: [
      { date: new Date(Date.now() - 86400000 * 12).toISOString(), from: 'client', text: "Quand est-ce que je recevrai ma commande ?" },
      { date: new Date(Date.now() - 86400000 * 12).toISOString(), from: 'sav', text: "Bonjour Karim ! Votre commande #8472 vient d'être expédiée. Voici votre tracking : LP123456789FR" },
      { date: new Date(Date.now() - 3600000 * 8).toISOString(), from: 'client', text: "Mon short a une couture qui lâche après 2 entraînements. Pas sérieux..." },
    ]
  },
  {
    id: 3, email: 'sophie.martinez@free.fr', category: 'LIVRAISON',
    reason: "Commande expédiée il y a 20 jours — tracking bloqué depuis 10 jours. Cliente très inquiète (3ème relance).",
    subject: 'Toujours pas reçu ma commande #8445 !!!', date: new Date(Date.now() - 3600000 * 1).toISOString(),
    preview: "Ça fait 3 semaines que j'attends et le tracking ne bouge plus depuis 10 jours. C'est mon 3ème message !",
    resolved: false,
    client_message: "Bonjour (encore), ça fait maintenant 3 SEMAINES que j'attends ma commande #8445 !! Le numéro de suivi ne bouge plus depuis le 15 février. C'est mon TROISIÈME message et personne ne me répond sérieusement. Si je n'ai pas de réponse concrète aujourd'hui je fais opposition sur ma carte bancaire.",
    order: { number: '8445', total: '129.90', status: 'fulfilled', items: ['Rashguard Custom - Taille S', 'Short MMA Custom - Taille S'], tracking: 'CB987654321FR' },
    history: [
      { date: new Date(Date.now() - 86400000 * 10).toISOString(), from: 'client', text: "Bonjour, je n'ai toujours pas reçu ma commande, le tracking ne bouge plus." },
      { date: new Date(Date.now() - 86400000 * 10).toISOString(), from: 'sav', text: "Bonjour Sophie, nous vérifions avec le transporteur. Un délai supplémentaire peut survenir." },
      { date: new Date(Date.now() - 86400000 * 5).toISOString(), from: 'client', text: "Toujours rien reçu, le tracking est bloqué depuis 10 jours maintenant..." },
      { date: new Date(Date.now() - 86400000 * 5).toISOString(), from: 'sav', text: "Nous comprenons votre frustration. Nous avons relancé le transporteur." },
      { date: new Date(Date.now() - 3600000 * 1).toISOString(), from: 'client', text: "3ème message ! Si pas de réponse concrète, opposition bancaire." },
    ]
  },
]

const STATS = {
  total_emails: 247, emails_sent: 218, escalations: 3, avg_processing_ms: 4200,
  categories: [
    { category: 'LIVRAISON', count: 89 },
    { category: 'QUESTION_PRODUIT', count: 62 },
    { category: 'RETOUR_ECHANGE', count: 41 },
    { category: 'ANNULATION', count: 28 },
    { category: 'MODIFIER_ADRESSE', count: 15 },
    { category: 'AUTRE', count: 12 },
  ],
  daily: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 86400000).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }),
    count: Math.floor(Math.random() * 12) + 3,
  }))
}

const PIPELINE = {
  emails: [
    { email: 'ines.bk@gmail.com', subject: 'Annulation commande #8519', category: 'ANNULATION', confidence: 0.94, time_ms: 3800, sent: false, date: new Date(Date.now() - 3600000 * 2).toISOString() },
    { email: 'marc.dupont@gmail.com', subject: 'Où en est ma commande ?', category: 'LIVRAISON', confidence: 0.97, time_ms: 2900, sent: true, date: new Date(Date.now() - 3600000 * 3).toISOString() },
    { email: 'karim.fight@outlook.fr', subject: 'Problème qualité', category: 'RETOUR_ECHANGE', confidence: 0.91, time_ms: 5200, sent: false, date: new Date(Date.now() - 3600000 * 8).toISOString() },
    { email: 'julie.r@hotmail.com', subject: 'Taille short MMA', category: 'QUESTION_PRODUIT', confidence: 0.98, time_ms: 2100, sent: true, date: new Date(Date.now() - 3600000 * 5).toISOString() },
    { email: 'sophie.martinez@free.fr', subject: 'Commande pas reçue !!!', category: 'LIVRAISON', confidence: 0.88, time_ms: 4600, sent: false, date: new Date(Date.now() - 3600000 * 1).toISOString() },
    { email: 'alex.training@gmail.com', subject: 'Guide des tailles ?', category: 'QUESTION_PRODUIT', confidence: 0.99, time_ms: 1800, sent: true, date: new Date(Date.now() - 3600000 * 6).toISOString() },
    { email: 'nadia.k@yahoo.fr', subject: 'Modifier mon adresse', category: 'MODIFIER_ADRESSE', confidence: 0.95, time_ms: 3200, sent: true, date: new Date(Date.now() - 3600000 * 7).toISOString() },
    { email: 'thomas.b@gmail.com', subject: 'Re: Suivi commande #8501', category: 'LIVRAISON', confidence: 0.96, time_ms: 2600, sent: true, date: new Date(Date.now() - 3600000 * 9).toISOString() },
  ]
}

const SETTINGS = {
  brand_name: 'OKTAGON', website: 'https://oktagon-shop.com', instagram: '@oktagon_mma',
  brand_color: '#F0FF27', tagline: 'Le combat, sur mesure.',
  return_address: '12 Rue du Sport, 75011 Paris',
  autonomy_level: 2, confidence_threshold: 0.9,
  auto_categories: ['QUESTION_PRODUIT', 'LIVRAISON'],
  claude_model: 'claude-sonnet-4-5-20250929', max_tokens: 8000, temperature: 0.7,
  tone: 'pro-chaleureux',
  delivery_delay: '12-15 jours', flocage_gratuit: true,
  return_policy: { delay_days: 30, return_shipping: 'client', refund_delay: '5-10 jours' },
  products: [
    { name: 'Short MMA Custom', price: 89.90, sizes: ['S', 'M', 'L', 'XL'] },
    { name: 'Rashguard Custom', price: 69.90, sizes: ['S', 'M', 'L', 'XL'] },
    { name: 'Kimono JJB Custom', price: 149.90, sizes: ['A1', 'A2', 'A3', 'A4'] },
  ],
}

const CLIENTS = [
  { email: 'ines.bk@gmail.com', prenom: 'Inès', total_emails: 4, total_escalations: 1, derniere_commande: '8519', vip: false },
  { email: 'karim.fight@outlook.fr', prenom: 'Karim', total_emails: 3, total_escalations: 1, derniere_commande: '8472', vip: true },
  { email: 'sophie.martinez@free.fr', prenom: 'Sophie', total_emails: 6, total_escalations: 1, derniere_commande: '8445', vip: false },
  { email: 'marc.dupont@gmail.com', prenom: 'Marc', total_emails: 2, total_escalations: 0, derniere_commande: '8501', vip: false },
  { email: 'julie.r@hotmail.com', prenom: 'Julie', total_emails: 1, total_escalations: 0, derniere_commande: '8510', vip: false },
  { email: 'alex.training@gmail.com', prenom: 'Alex', total_emails: 1, total_escalations: 0, derniere_commande: '8520', vip: true },
  { email: 'nadia.k@yahoo.fr', prenom: 'Nadia', total_emails: 2, total_escalations: 0, derniere_commande: '8499', vip: false },
  { email: 'thomas.b@gmail.com', prenom: 'Thomas', total_emails: 3, total_escalations: 0, derniere_commande: '8501', vip: false },
]

const METRICS = {
  emails: { received: 312, processed: 247, filtered: 52, duplicates: 8, rate_limited: 5 },
  responses: { sent: 218, escalated: 14, failed: 3 },
  ai: { calls_success: 244, calls_failed: 3, success_rate: 98.78, tool_uses: 189, avg_duration_ms: 2840 },
  shopify: { calls_success: 198, calls_failed: 2, success_rate: 99.0, avg_duration_ms: 420 },
  performance: { email_processing_avg_ms: 4200, processing_rate_per_min: 1.2 },
  system: { uptime_seconds: 86400 * 3.5, escalation_rate: 5.67, filter_rate: 16.7 },
}

const INTELLIGENCE = {
  period: '7d',
  categorization: { total: 247, categorized: 235, other: 12, rate: 95.1 },
  confidence_by_category: [
    { category: 'LIVRAISON', count: 89, avg_confidence: 0.96, min_confidence: 0.82, max_confidence: 0.99 },
    { category: 'QUESTION_PRODUIT', count: 62, avg_confidence: 0.97, min_confidence: 0.88, max_confidence: 1.0 },
    { category: 'RETOUR_ECHANGE', count: 41, avg_confidence: 0.91, min_confidence: 0.78, max_confidence: 0.98 },
    { category: 'ANNULATION', count: 28, avg_confidence: 0.93, min_confidence: 0.85, max_confidence: 0.97 },
    { category: 'MODIFIER_ADRESSE', count: 15, avg_confidence: 0.95, min_confidence: 0.90, max_confidence: 0.99 },
  ],
  escalation: { total_emails: 247, escalated: 14, rate: 5.67 },
  escalation_reasons: [
    { reason: 'Confiance insuffisante', count: 5 },
    { reason: 'Demande humain explicite', count: 4 },
    { reason: 'Remboursement > seuil', count: 3 },
    { reason: 'Client VIP mécontent', count: 2 },
  ],
  daily_trend: Array.from({ length: 7 }, (_, i) => ({
    date: new Date(Date.now() - (6 - i) * 86400000).toISOString().split('T')[0],
    total: Math.floor(Math.random() * 15) + 8,
    categorized: Math.floor(Math.random() * 13) + 7,
    avg_confidence: +(0.90 + Math.random() * 0.08).toFixed(2),
    escalated: Math.floor(Math.random() * 3),
  })),
  realtime_24h: { emails: 18, ai_responses: 16, ai_response_rate: 88.9, avg_response_time: 4 },
}

// ── Chat AI simulation ──────────────────────────────────────

function simulateChat(message) {
  const lower = message.toLowerCase()
  if (lower.includes('escalation') || lower.includes('attente')) {
    return `Il y a actuellement **${ESCALATIONS.length} escalations** en attente :\n\n` +
      ESCALATIONS.map(e => `- **#${e.id}** — ${e.email} — ${e.category}\n  ${e.reason.slice(0, 80)}...`).join('\n\n') +
      `\n\nTu veux que je traite l'une d'entre elles ?`
  }
  if (lower.includes('stat') || lower.includes('combien') || lower.includes('résumé')) {
    return `Voici le résumé :\n\n- **${STATS.total_emails}** emails traités\n- **${STATS.emails_sent}** réponses envoyées (taux: ${(STATS.emails_sent / STATS.total_emails * 100).toFixed(1)}%)\n- **${STATS.escalations}** escalations en attente\n- Temps moyen de traitement : **${(STATS.avg_processing_ms / 1000).toFixed(1)}s**\n\nTop catégories : Livraison (${STATS.categories[0].count}), Produits (${STATS.categories[1].count}), Retours (${STATS.categories[2].count})`
  }
  if (lower.includes('inès') || lower.includes('ines')) {
    return `**Inès** (ines.bk@gmail.com) :\n- 4 emails, 1 escalation en cours\n- Commande #8519 — Short MMA Custom M — 89.90€\n- Demande d'annulation (mauvaise taille)\n- Commande non expédiée\n\nLa personnalisation est déjà lancée. Tu veux que je lui propose un échange de taille plutôt qu'une annulation ?`
  }
  if (lower.includes('karim')) {
    return `**Karim** (karim.fight@outlook.fr) — Client VIP :\n- 3 emails, 1 escalation en cours\n- Commande #8472 — Short MMA Pro + Flocage — 94.90€\n- Défaut de couture signalé après 2 entraînements\n- Tracking : LP123456789FR (livré)\n\nClient VIP mécontent, je recommande un renvoi gratuit + échange. Tu veux que je rédige le mail ?`
  }
  if (lower.includes('sophie')) {
    return `**Sophie** (sophie.martinez@free.fr) :\n- 6 emails, 1 escalation — 3ème relance !\n- Commande #8445 — Rashguard + Short — 129.90€\n- Tracking CB987654321FR bloqué depuis 10 jours\n- Menace d'opposition bancaire\n\n⚠️ **Urgence haute** — Je recommande de contacter Colissimo et proposer un renvoi ou remboursement immédiat.`
  }
  if (lower.includes('paramètre') || lower.includes('config') || lower.includes('setting')) {
    return `Tu peux tout configurer dans l'onglet **Paramètres** :\n\n- **Marque** : nom, couleur, slogan\n- **IA** : niveau d'autonomie, seuil de confiance, modèle\n- **Prompts** : personnaliser le ton par catégorie\n- **Règles** : politique retour, délais, promesses interdites\n- **Sécurité** : rate limiting, emails bloqués\n- **Connecteurs** : Shopify, Gmail, Telegram\n\nDis-moi ce que tu veux modifier, je peux le faire directement !`
  }
  return `J'ai bien compris ta demande. Voici ce que je peux faire :\n\n- 🔍 **Chercher** un client, une commande, des stats\n- 📧 **Envoyer** un email à un client\n- ✅ **Résoudre** une escalation\n- 💰 **Marquer** un remboursement\n- 📝 **Ajouter** une note client\n\nEssaie : "Montre-moi les escalations en attente" ou "Dis-moi tout sur Inès"`
}

// ── AI Draft generation for escalations ─────────────────────

function generateAiDraft(esc) {
  const prenom = CLIENTS.find(c => c.email === esc.email)?.prenom || 'Client'
  const drafts = {
    'ANNULATION': `Bonjour ${prenom},\n\nNous avons bien reçu votre demande concernant la commande #${esc.order.number}.\n\nComme votre article est en cours de personnalisation sur mesure, l'annulation n'est malheureusement plus possible à ce stade de la fabrication.\n\nCependant, nous pouvons vous proposer un échange de taille une fois l'article reçu. Les frais de retour seront à notre charge compte tenu de la situation.\n\nRestant à votre disposition,\nL'équipe OKTAGON`,
    'RETOUR_ECHANGE': `Bonjour ${prenom},\n\nNous sommes sincèrement désolés pour ce désagrément avec votre commande #${esc.order.number}.\n\nUn défaut de fabrication n'est absolument pas à la hauteur de nos standards de qualité. Nous vous proposons :\n\n1. Un renvoi gratuit de l'article défectueux (étiquette prépayée par email)\n2. Un nouvel article fabriqué et expédié en priorité\n\nPouvez-vous nous envoyer une photo du défaut à cette adresse ? Cela nous aidera à améliorer notre production.\n\nSportivement,\nL'équipe OKTAGON`,
    'LIVRAISON': `Bonjour ${prenom},\n\nNous comprenons parfaitement votre inquiétude concernant la commande #${esc.order.number} et nous vous prions d'accepter nos excuses pour ce retard.\n\nNous avons immédiatement contacté le transporteur concernant votre colis (tracking: ${esc.order.tracking}). Si celui-ci reste introuvable sous 48h, nous procéderons à un renvoi complet à nos frais.\n\nVous recevrez un email de suivi dès que nous aurons une réponse du transporteur.\n\nSportivement,\nL'équipe OKTAGON`,
  }
  return drafts[esc.category] || `Bonjour ${prenom},\n\nNous avons bien pris note de votre message et nous y apportons toute notre attention.\n\nNous revenons vers vous dans les plus brefs délais.\n\nSportivement,\nL'équipe OKTAGON`
}

function generateAiAnalysis(esc) {
  const analyses = {
    1: {
      summary: "Inès a commandé un Short MMA Custom en taille M mais souhaite annuler car elle voulait un L. La commande n'est pas encore expédiée mais la personnalisation est en cours.",
      emotion: 'neutre',
      urgency: 'moyenne',
      recommendation: "Proposer un échange de taille (M → L) plutôt qu'une annulation. La commande n'est pas expédiée, un changement de taille est peut-être encore possible en production. Si impossible, proposer un retour gratuit à la réception.",
      risk: "Faible — cliente calme, première demande.",
      similar_cases: "85% des demandes d'annulation pour mauvaise taille se résolvent par un échange."
    },
    2: {
      summary: "Karim (client VIP) a reçu un Short MMA Pro avec un défaut de couture (cuisse droite) après 2 entraînements. Commande #8472 à 94.90€. Il demande un échange ou remboursement.",
      emotion: 'frustré',
      urgency: 'haute',
      recommendation: "Client VIP mécontent avec un défaut produit légitime. Proposer immédiatement : 1) Étiquette retour prépayée, 2) Renvoi prioritaire d'un nouvel article, 3) Geste commercial (réduction prochaine commande). Demander photo du défaut pour le contrôle qualité.",
      risk: "Élevé — client VIP, défaut produit avéré, ton frustré. Risque de perte client fidèle.",
      similar_cases: "100% des défauts de couture signalés sont résolus par échange + geste commercial."
    },
    3: {
      summary: "Sophie attend sa commande #8445 (129.90€) depuis 3 semaines. Le tracking CB987654321FR est bloqué depuis 10 jours. C'est son 3ème message et elle menace une opposition bancaire.",
      emotion: 'en colère',
      urgency: 'critique',
      recommendation: "URGENCE : 3ème relance + menace d'opposition bancaire. Agir immédiatement : 1) Contacter Colissimo/transporteur, 2) Si colis perdu : renvoi immédiat ou remboursement intégral, 3) Geste commercial obligatoire. Réponse dans l'heure.",
      risk: "Critique — menace de chargeback, 3 messages sans résolution satisfaisante. Image de marque en jeu.",
      similar_cases: "Les colis bloqués >10 jours sont considérés perdus dans 70% des cas."
    }
  }
  return analyses[esc.id] || { summary: esc.reason, emotion: 'neutre', urgency: 'moyenne', recommendation: 'Analyser et répondre.', risk: 'À évaluer', similar_cases: '' }
}

function simulateSettingsAi(message, settings) {
  const lower = message.toLowerCase()
  if (lower.includes('retour') || lower.includes('politique')) {
    return {
      response: `Actuellement ta politique retour est configurée ainsi :\n- Délai : **${(settings.return_policy||{}).delay_days || 30} jours**\n- Frais de retour : **${(settings.return_policy||{}).return_shipping === 'client' ? 'à charge du client' : 'à ta charge'}**\n- Délai remboursement : **${(settings.return_policy||{}).refund_delay || '5-10 jours'}**\n\nTu veux modifier quelque chose ? Dis-moi en français ce que tu veux et je mets à jour.`,
      suggestions: null
    }
  }
  if (lower.includes('autonomie') || lower.includes('autonome') || lower.includes('confiance')) {
    return {
      response: `Niveau d'autonomie actuel : **${settings.autonomy_level ?? 2}/3**\nSeuil de confiance : **${((settings.confidence_threshold ?? 0.9) * 100).toFixed(0)}%**\n\n- Niveau 0 : tout est escaladé (mode surveillance)\n- Niveau 1 : seule la catégorisation est auto\n- Niveau 2 : auto sauf questions d'argent (actuel)\n- Niveau 3 : full auto (confiance totale en l'IA)\n\nPour commencer, je recommande de rester au **niveau 2** et de monter progressivement quand tu vois que l'IA gère bien.`,
      suggestions: null
    }
  }
  if (lower.includes('prompt') || lower.includes('ton') || lower.includes('style')) {
    return {
      response: `Ton actuel : **${settings.tone || 'pro-chaleureux'}**\n\nLes prompts personnalisés permettent d'affiner la façon dont l'IA répond par catégorie. Par exemple :\n- LIVRAISON : tu peux ajouter "Toujours mentionner le délai de fabrication de 12-15 jours"\n- RETOUR : "Proposer systématiquement un échange avant le remboursement"\n\nDis-moi ce que tu veux comme ton ou style, je génère le prompt.`,
      suggestions: null
    }
  }
  if (lower.includes('analyse') || lower.includes('diagnostic') || lower.includes('état') || lower.includes('résumé')) {
    return {
      response: `**Diagnostic du système :**\n\n✅ **Marque** : ${settings.brand_name || 'Non configuré'}\n✅ **IA** : Autonomie ${settings.autonomy_level ?? 2}/3, Confiance ${((settings.confidence_threshold ?? 0.9) * 100).toFixed(0)}%\n✅ **Produits** : ${(settings.products || []).length} produits configurés\n${(settings.return_policy || {}).delay_days ? '✅' : '⚠️'} **Politique retour** : ${(settings.return_policy || {}).delay_days || 'Non configurée'} jours\n${settings.tone ? '✅' : '⚠️'} **Ton** : ${settings.tone || 'Non défini'}\n\n**Score de complétude : 78%**\n\nPour atteindre 100%, il faudrait :\n- Configurer les prompts par catégorie\n- Ajouter les mots-clés de demande humaine\n- Configurer les notifications Telegram`,
      suggestions: null
    }
  }
  return {
    response: `Je peux t'aider avec la configuration. Voici ce que je peux faire :\n\n- **"Analyse le système"** — diagnostic complet\n- **"Change la politique retour"** — modifier les règles\n- **"Explique l'autonomie"** — comprendre les niveaux\n- **"Génère un prompt pour [catégorie]"** — créer des prompts IA\n- **"Quel est le ton actuel ?"** — voir la config de style\n\nDis-moi ce que tu veux configurer !`,
    suggestions: null
  }
}

// ── Router ──────────────────────────────────────────────────

function route(method, url, body) {
  const path = url.split('?')[0]
  const params = Object.fromEntries(new URL(`http://localhost${url}`).searchParams)

  // Stats
  if (path === '/api/stats') return STATS

  // Intelligence
  if (path === '/api/intelligence') return INTELLIGENCE

  // Metrics
  if (path === '/api/metrics') return METRICS

  // Health
  if (path === '/api/health') return { status: 'healthy', timestamp: Date.now() / 1000, checks: {} }

  // Circuit breakers
  if (path === '/api/circuit-breakers') return {
    shopify: { name: 'shopify', state: 'closed', failure_count: 0, success_count: 198 },
    claude: { name: 'claude', state: 'closed', failure_count: 1, success_count: 244 },
    gmail: { name: 'gmail', state: 'closed', failure_count: 0, success_count: 218 },
  }

  // Clients
  if (path === '/api/clients') {
    const search = (params.search || '').toLowerCase()
    const filtered = search ? CLIENTS.filter(c =>
      c.email.toLowerCase().includes(search) || (c.prenom || '').toLowerCase().includes(search)
    ) : CLIENTS
    return { clients: filtered }
  }

  // Client detail
  const clientMatch = path.match(/^\/api\/clients\/(.+)$/)
  if (clientMatch) {
    const email = decodeURIComponent(clientMatch[1])
    const client = CLIENTS.find(c => c.email === email)
    const esc = ESCALATIONS.filter(e => e.email === email)
    return {
      profile: client || { email, total_emails: 0, total_escalations: 0 },
      history: (esc[0]?.history || []).map(h => ({
        date: h.date, client_message: h.from === 'client' ? h.text : null,
        sav_response: h.from === 'sav' ? h.text : null, category: 'SAV'
      })),
      escalations: esc.map(e => ({ id: e.id, date: e.date, category: e.category, reason: e.reason, resolved: e.resolved }))
    }
  }

  // Pipeline
  if (path === '/api/pipeline') return PIPELINE

  // Escalations
  if (path === '/api/escalations') return { escalations: ESCALATIONS.filter(e => !e.resolved), count: ESCALATIONS.filter(e => !e.resolved).length }

  // Escalation detail
  const escDetailMatch = path.match(/^\/api\/escalations\/(\d+)$/)
  if (escDetailMatch && method === 'GET') {
    const id = parseInt(escDetailMatch[1])
    const esc = ESCALATIONS.find(e => e.id === id)
    if (!esc) return { error: 'Not found' }
    const client = CLIENTS.find(c => c.email === esc.email)
    return { ...esc, client, ai_analysis: generateAiAnalysis(esc) }
  }

  // AI draft for escalation
  const escDraftMatch = path.match(/^\/api\/escalations\/(\d+)\/ai-draft$/)
  if (escDraftMatch && method === 'POST') {
    const id = parseInt(escDraftMatch[1])
    const esc = ESCALATIONS.find(e => e.id === id)
    if (!esc) return { error: 'Not found' }
    return { draft: generateAiDraft(esc), analysis: generateAiAnalysis(esc) }
  }

  // Resolve escalation
  const resolveMatch = path.match(/^\/api\/escalations\/(\d+)\/resolve$/)
  if (resolveMatch && method === 'POST') {
    const id = parseInt(resolveMatch[1])
    const esc = ESCALATIONS.find(e => e.id === id)
    if (esc) esc.resolved = true
    return { ok: true }
  }

  // Chat
  if (path === '/api/chat' && method === 'POST') {
    const message = body?.message || ''
    return { response: simulateChat(message) }
  }

  // Send email
  if (path === '/api/send-email' && method === 'POST') return { ok: true }

  // Settings
  if (path === '/api/settings' && method === 'GET') return SETTINGS
  if (path === '/api/settings' && method === 'POST') { Object.assign(SETTINGS, body); return { ok: true } }

  // Settings AI assist
  if (path === '/api/settings/ai-assist' && method === 'POST') {
    return simulateSettingsAi(body?.message || '', body?.current_settings || SETTINGS)
  }

  return { error: 'Not found' }
}

// ── HTTP Server ─────────────────────────────────────────────

const server = http.createServer((req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization')
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return }

  // Auth check (accept anything)
  res.setHeader('Content-Type', 'application/json')

  let body = ''
  req.on('data', chunk => body += chunk)
  req.on('end', () => {
    let parsed = null
    try { parsed = body ? JSON.parse(body) : null } catch {}
    const result = route(req.method, req.url, parsed)
    res.writeHead(result?.error ? 404 : 200)
    res.end(JSON.stringify(result))
  })
})

server.listen(PORT, () => {
  console.log(`\n  Mock API server running on http://localhost:${PORT}`)
  console.log(`  Simulating OKTAGON SAV backend with demo data\n`)
})
