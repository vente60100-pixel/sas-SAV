-- Migration v10.5 : Enrichir custom_rules pour modularité
-- DATE: 2026-03-01
-- SAFE: Additive only, no data deletion

BEGIN;

-- Créer un SAVEPOINT pour rollback partiel si besoin
SAVEPOINT before_custom_rules_update;

-- Enrichir custom_rules du tenant OKTAGON
UPDATE tenants
SET custom_rules = custom_rules || jsonb_build_object(
    -- Logique produits
    'product_logic', 'oktagon_sport_combat',
    'has_ensemble_products', true,
    'has_flocage', true,
    'ensemble_split_enabled', true,

    -- Propriétés Shopify pour flocage (déjà existant, on documente)
    'flocage_property_names', jsonb_build_array('Nom Flocage', 'Numéro'),

    -- Règles métier produits (déjà existant, on garde)
    'short_price', COALESCE((custom_rules->>'short_price')::numeric, 29.99),

    -- Délais (nouvelle structure)
    'delai_jours', COALESCE(custom_rules->>'delai_jours', '12-15'),
    'delai_context', 'personnalisation sur commande',

    -- Politique retour/remboursement
    'politique_retour', 'Short : remboursable. Haut : remboursable sauf si floqué.',
    'delai_retour_jours', 30,
    'frais_retour', 'gratuit',

    -- Contexte business
    'business_model', 'fabrication_sur_commande',
    'pays_couverts', jsonb_build_array('FR', 'EU', 'Maghreb', 'Afrique', 'International'),

    -- Template prompts (placeholders dynamiques)
    'prompt_placeholders', jsonb_build_object(
        'delai', '12-15 jours',
        'type_produits', 'équipement sport de combat personnalisé',
        'process_fabrication', 'Chaque pièce est conçue sur commande avec personnalisation gratuite'
    )
)
WHERE id = 'oktagon';

-- Vérifier que la mise à jour a bien eu lieu
DO $$
DECLARE
    v_product_logic TEXT;
BEGIN
    SELECT custom_rules->>'product_logic' INTO v_product_logic
    FROM tenants WHERE id = 'oktagon';

    IF v_product_logic != 'oktagon_sport_combat' THEN
        RAISE EXCEPTION 'Migration custom_rules FAILED: product_logic not set correctly';
    END IF;

    RAISE NOTICE 'Migration custom_rules SUCCESS: product_logic = %', v_product_logic;
END $$;

-- Si tout est OK, valider
COMMIT;

-- Afficher le résultat final
SELECT
    id,
    name,
    custom_rules->>'product_logic' as product_logic,
    custom_rules->>'delai_jours' as delai,
    custom_rules->>'short_price' as short_price
FROM tenants
WHERE id = 'oktagon';
