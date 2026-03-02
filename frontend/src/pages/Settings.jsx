import { useState, useEffect } from 'react'
import { getSettings, saveSettings } from '../api/client'
import { Save, Check, RotateCcw } from 'lucide-react'

const TABS = [
  { id: 'brand', label: 'Marque' },
  { id: 'ai', label: 'IA & Autonomie' },
  { id: 'tone', label: 'Ton & Prompts' },
  { id: 'rules', label: 'Règles métier' },
  { id: 'products', label: 'Catalogue' },
  { id: 'security', label: 'Sécurité' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'connectors', label: 'Connecteurs' },
  { id: 'template', label: 'Template email' },
]

function Field({ label, children, hint }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>{label}</label>
      {children}
      {hint && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{hint}</div>}
    </div>
  )
}

export default function Settings() {
  const [tab, setTab] = useState('brand')
  const [settings, setSettings] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getSettings()
      .then(data => { setSettings(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const update = (key, value) => setSettings(prev => ({ ...prev, [key]: value }))
  const updateNested = (parent, key, value) => setSettings(prev => ({
    ...prev, [parent]: { ...(prev[parent] || {}), [key]: value }
  }))

  const handleSave = async () => {
    setSaving(true)
    try {
      await saveSettings(settings)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      alert('Erreur de sauvegarde')
    }
    setSaving(false)
  }

  if (loading) return <div style={{ color: 'var(--text-muted)', padding: 40 }}>Chargement...</div>

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>Settings</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '4px 0 0' }}>Paramétrage complet du système</p>
        </div>
        <button className="btn-primary" onClick={handleSave} disabled={saving} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {saved ? <Check size={16} /> : <Save size={16} />}
          {saving ? 'Sauvegarde...' : saved ? 'Sauvegardé !' : 'Sauvegarder'}
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 24, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={tab === t.id ? 'btn-primary' : 'btn-secondary'}
            style={{ fontSize: 13, padding: '8px 16px' }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="glass-card animate-in">
        {tab === 'brand' && (
          <div>
            <h3 style={{ margin: '0 0 24px', fontSize: 18, fontWeight: 600 }}>Marque & Identité</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
              <Field label="Nom de la marque">
                <input className="input" value={settings.brand_name || ''} onChange={e => update('brand_name', e.target.value)} />
              </Field>
              <Field label="Site web">
                <input className="input" value={settings.website || ''} onChange={e => update('website', e.target.value)} />
              </Field>
              <Field label="Instagram">
                <input className="input" value={settings.instagram || ''} onChange={e => update('instagram', e.target.value)} />
              </Field>
              <Field label="Couleur accent">
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input type="color" value={settings.brand_color || '#F0FF27'} onChange={e => update('brand_color', e.target.value)}
                    style={{ width: 48, height: 40, border: 'none', borderRadius: 8, cursor: 'pointer' }} />
                  <input className="input" value={settings.brand_color || '#F0FF27'} onChange={e => update('brand_color', e.target.value)} style={{ width: 120 }} />
                </div>
              </Field>
              <Field label="Tagline / Slogan">
                <input className="input" value={settings.tagline || ''} onChange={e => update('tagline', e.target.value)} />
              </Field>
              <Field label="Adresse retour">
                <input className="input" value={settings.return_address || ''} onChange={e => update('return_address', e.target.value)} />
              </Field>
            </div>
          </div>
        )}

        {tab === 'ai' && (
          <div>
            <h3 style={{ margin: '0 0 24px', fontSize: 18, fontWeight: 600 }}>IA & Autonomie</h3>
            <Field label={`Niveau d'autonomie : ${settings.autonomy_level ?? 2}`}
              hint="0=Tout escalade | 1=Auto catégories seulement | 2=Toutes sauf argent | 3=Full auto">
              <input type="range" min={0} max={3} step={1} value={settings.autonomy_level ?? 2}
                onChange={e => update('autonomy_level', parseInt(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent)' }} />
            </Field>
            <Field label={`Seuil de confiance : ${(settings.confidence_threshold ?? 0.9).toFixed(2)}`}
              hint="Plus haut = plus prudent (plus d'escalations)">
              <input type="range" min={0.5} max={0.99} step={0.01} value={settings.confidence_threshold ?? 0.9}
                onChange={e => update('confidence_threshold', parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent)' }} />
            </Field>
            <Field label="Catégories auto-réponse">
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                {['LIVRAISON', 'QUESTION_PRODUIT', 'RETOUR_ECHANGE', 'ANNULATION', 'MODIFIER_ADRESSE', 'AUTRE'].map(cat => {
                  const cats = settings.auto_categories || ['QUESTION_PRODUIT', 'LIVRAISON']
                  const checked = cats.includes(cat)
                  return (
                    <label key={cat} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                      <input type="checkbox" checked={checked}
                        onChange={() => update('auto_categories', checked ? cats.filter(c => c !== cat) : [...cats, cat])}
                        style={{ accentColor: 'var(--accent)' }} />
                      {cat}
                    </label>
                  )
                })}
              </div>
            </Field>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24 }}>
              <Field label="Modèle Claude">
                <select className="input" value={settings.claude_model || 'claude-sonnet-4-5-20250929'}
                  onChange={e => update('claude_model', e.target.value)}>
                  <option value="claude-sonnet-4-5-20250929">Sonnet 4.5</option>
                  <option value="claude-opus-4-6">Opus 4.6</option>
                  <option value="claude-haiku-4-5-20251001">Haiku 4.5</option>
                </select>
              </Field>
              <Field label={`Max tokens : ${settings.max_tokens ?? 8000}`}>
                <input type="range" min={1000} max={16000} step={500} value={settings.max_tokens ?? 8000}
                  onChange={e => update('max_tokens', parseInt(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--accent)' }} />
              </Field>
              <Field label={`Temperature : ${(settings.temperature ?? 0.7).toFixed(1)}`}>
                <input type="range" min={0} max={1} step={0.1} value={settings.temperature ?? 0.7}
                  onChange={e => update('temperature', parseFloat(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--accent)' }} />
              </Field>
            </div>
          </div>
        )}

        {tab === 'tone' && (
          <div>
            <h3 style={{ margin: '0 0 24px', fontSize: 18, fontWeight: 600 }}>Ton & Prompts IA</h3>
            <Field label="Ton général">
              <select className="input" style={{ width: 300 }} value={settings.tone || 'pro-chaleureux'}
                onChange={e => update('tone', e.target.value)}>
                <option value="formel">Formel</option>
                <option value="pro-chaleureux">Pro-chaleureux</option>
                <option value="decontracte">Décontracté</option>
              </select>
            </Field>
            <Field label="Message réassurance livraison" hint="Affiché dans toutes les réponses livraison">
              <textarea className="input" rows={3} value={settings.reassurance_message || ''}
                onChange={e => update('reassurance_message', e.target.value)} style={{ resize: 'vertical' }} />
            </Field>
            {['LIVRAISON', 'RETOUR_ECHANGE', 'QUESTION_PRODUIT', 'MODIFIER_ADRESSE', 'ANNULATION'].map(cat => (
              <Field key={cat} label={`Prompt ${cat}`}>
                <textarea className="input" rows={4}
                  value={(settings.custom_prompts || {})[cat] || ''}
                  onChange={e => updateNested('custom_prompts', cat, e.target.value)}
                  placeholder={`Instructions personnalisées pour la catégorie ${cat}...`}
                  style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: 12 }} />
              </Field>
            ))}
          </div>
        )}

        {tab === 'rules' && (
          <div>
            <h3 style={{ margin: '0 0 24px', fontSize: 18, fontWeight: 600 }}>Règles métier</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
              <Field label="Délai de livraison" hint="Ex: 12-15 jours">
                <input className="input" value={settings.delivery_delay || ''} onChange={e => update('delivery_delay', e.target.value)} />
              </Field>
              <Field label="Personnalisation/Flocage">
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
                  <input type="checkbox" checked={settings.flocage_gratuit ?? true}
                    onChange={e => update('flocage_gratuit', e.target.checked)}
                    style={{ accentColor: 'var(--accent)' }} />
                  Flocage gratuit
                </label>
              </Field>
            </div>
            <h4 style={{ fontSize: 15, fontWeight: 600, marginTop: 24, marginBottom: 16, color: 'var(--text-secondary)' }}>Politique retours</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24 }}>
              <Field label="Délai retour (jours)">
                <input className="input" type="number" value={(settings.return_policy || {}).delay_days ?? 30}
                  onChange={e => updateNested('return_policy', 'delay_days', parseInt(e.target.value))} />
              </Field>
              <Field label="Frais retour">
                <select className="input" value={(settings.return_policy || {}).return_shipping ?? 'client'}
                  onChange={e => updateNested('return_policy', 'return_shipping', e.target.value)}>
                  <option value="client">À la charge du client</option>
                  <option value="brand">À notre charge</option>
                </select>
              </Field>
              <Field label="Délai remboursement">
                <input className="input" value={(settings.return_policy || {}).refund_delay ?? '5-10 jours'}
                  onChange={e => updateNested('return_policy', 'refund_delay', e.target.value)} />
              </Field>
            </div>
            <Field label="Promesses interdites" hint="Une par ligne">
              <textarea className="input" rows={4}
                value={(settings.forbidden_promises || []).join('\n')}
                onChange={e => update('forbidden_promises', e.target.value.split('\n').filter(Boolean))}
                style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: 12 }} />
            </Field>
          </div>
        )}

        {tab === 'products' && (
          <div>
            <h3 style={{ margin: '0 0 24px', fontSize: 18, fontWeight: 600 }}>Catalogue produits</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 20 }}>Ces produits sont utilisés par l'IA pour répondre aux questions produits.</p>
            {(settings.products || []).map((p, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 2fr auto', gap: 12, marginBottom: 12, alignItems: 'end' }}>
                <Field label={i === 0 ? 'Nom' : ''}>
                  <input className="input" value={p.name || ''} onChange={e => {
                    const prods = [...(settings.products || [])]
                    prods[i] = { ...prods[i], name: e.target.value }
                    update('products', prods)
                  }} />
                </Field>
                <Field label={i === 0 ? 'Prix' : ''}>
                  <input className="input" type="number" step="0.01" value={p.price ?? ''} onChange={e => {
                    const prods = [...(settings.products || [])]
                    prods[i] = { ...prods[i], price: parseFloat(e.target.value) }
                    update('products', prods)
                  }} />
                </Field>
                <Field label={i === 0 ? 'Tailles' : ''}>
                  <input className="input" value={(p.sizes || []).join(', ')} onChange={e => {
                    const prods = [...(settings.products || [])]
                    prods[i] = { ...prods[i], sizes: e.target.value.split(',').map(s => s.trim()) }
                    update('products', prods)
                  }} placeholder="S, M, L, XL" />
                </Field>
                <button className="btn-secondary" style={{ padding: '8px 12px', color: 'var(--red)' }}
                  onClick={() => update('products', (settings.products || []).filter((_, j) => j !== i))}>
                  X
                </button>
              </div>
            ))}
            <button className="btn-secondary" style={{ marginTop: 8 }}
              onClick={() => update('products', [...(settings.products || []), { name: '', price: 0, sizes: [] }])}>
              + Ajouter un produit
            </button>
          </div>
        )}

        {tab === 'security' && (
          <div>
            <h3 style={{ margin: '0 0 24px', fontSize: 18, fontWeight: 600 }}>Rate limiting & Sécurité</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 24 }}>
              <Field label="Max emails / heure">
                <input className="input" type="number" value={settings.rate_limit_hour ?? 3} onChange={e => update('rate_limit_hour', parseInt(e.target.value))} />
              </Field>
              <Field label="Max emails / jour">
                <input className="input" type="number" value={settings.rate_limit_day ?? 8} onChange={e => update('rate_limit_day', parseInt(e.target.value))} />
              </Field>
              <Field label="Polling (secondes)">
                <input className="input" type="number" value={settings.polling_interval ?? 30} onChange={e => update('polling_interval', parseInt(e.target.value))} />
              </Field>
              <Field label="Anti-boucle (heures)">
                <input className="input" type="number" value={settings.anti_loop_hours ?? 48} onChange={e => update('anti_loop_hours', parseInt(e.target.value))} />
              </Field>
            </div>
            <Field label="Emails bloqués" hint="Un email par ligne">
              <textarea className="input" rows={4} value={(settings.blocked_emails || []).join('\n')}
                onChange={e => update('blocked_emails', e.target.value.split('\n').filter(Boolean))}
                style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: 12 }} />
            </Field>
            <Field label="Patterns bloqués" hint="Un pattern par ligne (ex: noreply@)">
              <textarea className="input" rows={4} value={(settings.blocked_patterns || []).join('\n')}
                onChange={e => update('blocked_patterns', e.target.value.split('\n').filter(Boolean))}
                style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: 12 }} />
            </Field>
            <Field label="Mots-clés demande humain" hint="Un mot-clé par ligne">
              <textarea className="input" rows={4} value={(settings.human_keywords || []).join('\n')}
                onChange={e => update('human_keywords', e.target.value.split('\n').filter(Boolean))}
                style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: 12 }} />
            </Field>
          </div>
        )}

        {tab === 'notifications' && (
          <div>
            <h3 style={{ margin: '0 0 24px', fontSize: 18, fontWeight: 600 }}>Notifications Telegram</h3>
            <Field label="Activer Telegram">
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
                <input type="checkbox" checked={(settings.telegram || {}).enabled ?? true}
                  onChange={e => updateNested('telegram', 'enabled', e.target.checked)}
                  style={{ accentColor: 'var(--accent)' }} />
                Notifications activées
              </label>
            </Field>
            <Field label="Chat ID Admin">
              <input className="input" value={(settings.telegram || {}).chat_id || ''} style={{ width: 300 }}
                onChange={e => updateNested('telegram', 'chat_id', e.target.value)} />
            </Field>
            <div style={{ display: 'flex', gap: 24 }}>
              <Field label="">
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
                  <input type="checkbox" checked={(settings.telegram || {}).notify_escalations ?? true}
                    onChange={e => updateNested('telegram', 'notify_escalations', e.target.checked)}
                    style={{ accentColor: 'var(--accent)' }} />
                  Escalations
                </label>
              </Field>
              <Field label="">
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
                  <input type="checkbox" checked={(settings.telegram || {}).notify_errors ?? true}
                    onChange={e => updateNested('telegram', 'notify_errors', e.target.checked)}
                    style={{ accentColor: 'var(--accent)' }} />
                  Erreurs
                </label>
              </Field>
              <Field label="">
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
                  <input type="checkbox" checked={(settings.telegram || {}).daily_summary ?? false}
                    onChange={e => updateNested('telegram', 'daily_summary', e.target.checked)}
                    style={{ accentColor: 'var(--accent)' }} />
                  Résumé quotidien
                </label>
              </Field>
            </div>
          </div>
        )}

        {tab === 'connectors' && (
          <div>
            <h3 style={{ margin: '0 0 24px', fontSize: 18, fontWeight: 600 }}>Connecteurs</h3>
            <h4 style={{ fontSize: 15, fontWeight: 600, color: 'var(--accent)', marginBottom: 16 }}>Shopify</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
              <Field label="URL boutique">
                <input className="input" value={settings.shopify_url || ''} onChange={e => update('shopify_url', e.target.value)} placeholder="ma-boutique.myshopify.com" />
              </Field>
              <Field label="Access Token">
                <input className="input" type="password" value={settings.shopify_token || ''} onChange={e => update('shopify_token', e.target.value)} />
              </Field>
            </div>
            <h4 style={{ fontSize: 15, fontWeight: 600, color: 'var(--accent)', marginTop: 24, marginBottom: 16 }}>Gmail</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
              <Field label="Email">
                <input className="input" value={settings.gmail_email || ''} onChange={e => update('gmail_email', e.target.value)} />
              </Field>
              <Field label="App Password">
                <input className="input" type="password" value={settings.gmail_password || ''} onChange={e => update('gmail_password', e.target.value)} />
              </Field>
            </div>
          </div>
        )}

        {tab === 'template' && (
          <div>
            <h3 style={{ margin: '0 0 24px', fontSize: 18, fontWeight: 600 }}>Template email</h3>
            <Field label="Signature">
              <input className="input" value={(settings.email_template || {}).signature || ''} onChange={e => updateNested('email_template', 'signature', e.target.value)} />
            </Field>
            <Field label="Footer HTML">
              <textarea className="input" rows={4} value={(settings.email_template || {}).footer_html || ''}
                onChange={e => updateNested('email_template', 'footer_html', e.target.value)}
                style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: 12 }} />
            </Field>
          </div>
        )}
      </div>
    </div>
  )
}
