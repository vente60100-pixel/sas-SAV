# LOG DE SCRAPING — VOC Bastion (cargo moto CE AA)
Date: 2026-06-19

## Accès réseau testé depuis le sandbox (IP datacenter)
| Source            | requests (raw) | WebFetch        | Note |
|-------------------|----------------|-----------------|------|
| reddit.com (json) | 403 BLOQUÉ     | refusé          | Anti-bot Reddit sur IP datacenter + WebFetch interdit reddit |
| old.reddit.com    | 403            | refusé          | idem |
| trustpilot.com    | 403 BLOQUÉ     | -               | Anti-bot |
| google.com        | 200            | -               | inutilisable directement |
| advrider.com      | 202 (CF)       | à tester        | Cloudflare challenge |
| ukbikeforum.co.uk | DNS/conn error | -               | injoignable |
| revzilla.com      | 200 OK         | OK              | reviews clients accessibles |
| bull-it.com       | 200 OK         | OK              | |

## Stratégie adoptée (Reddit bloqué)
1. WebSearch `site:reddit.com ...` -> récupère snippets verbatim + permalinks (citables).
2. WebFetch articles reviews qui citent des propriétaires (webbikeworld, MCN, RotCR, ultimatemotorcycling).
3. WebFetch pages reviews clients RevZilla / Sportsbikeshop (avis étoilés réels).
4. WebFetch threads forums (nc700-forum, motorcyclenews, advrider).

## Bilan récolte (verbatims réels sourcés)
| Batch | Source(s) | Type voix | ~verbatims |
|-------|-----------|-----------|-----------|
| 01 | webbikeworld, MCN (Pando Mark), anandtech forum | reviewer + forum | 26 |
| 02 | Sportsbikeshop (Oxford AAA straight + slim), MCN Bull-it Tactical | CLIENT UK + reviewer | 41 |
| 03 | Sportsbikeshop (Bull-it Tactical slim, Bull-it cargo ladies, Richa Carter, Bull-it Onyx) | CLIENT UK | 40 |
| 04 | roadskin x2, pandomoto blog | récits de chute 1re personne | 27 |
| 05 | itsbetterontheroad, rideadv, mcgearhub(HWK) | éducation CE + objection cheap | 22 |
| 06 | bohnarmor, jessiejobst, bestbeginnermotorcycles | discret/anti-gear + lexique | 17 |
| **TOTAL** | | | **~170 lignes / 110+ verbatims exploitables** |

## Sources BLOQUÉES (documenté, non contournable depuis IP datacenter)
- Reddit (json + WebFetch) = 403 / refusé -> compensé par reviews clients UK Sportsbikeshop (même voix d'acheteur, marché UK exact).
- Trustpilot = 403 ; PistonHeads = 403 ; tollbit(Ducati forum) = 402 ; Bennetts BikeSocial = 403 ; teamblind = 403.
- content_rev/<id> Sportsbikeshop = 410 Gone (utiliser content_prod/<id> à la place).
- Amazon.co.uk = anti-bot (non tenté en profondeur, fallback retailer UK utilisé comme prévu par le brief).

## Vecteur gagnant
WebFetch sur URLs concrètes de pages-produit Sportsbikeshop.co.uk (avis clients UK server-rendered, nom + étoiles)
+ pages récits-de-chute (roadskin/pando) + articles reviews (MCN/webbikeworld/ultimatemotorcycling) + guides CE.
