"""
OKTAGON — Calcul des COGS avec flocage en interne (nom + numéro).

Hypothèses par défaut (toutes modifiables en ligne de commande) :
- Employé au SMIC : 12,31 € brut/h (depuis le 01/06/2026), ~12 % de charges patronales après RGDU
- Frais fixes salarié : mutuelle part employeur + médecine du travail (~30 €/mois)
- 5 semaines de congés payés : payées mais non productives
- Local : 400 € HT/mois
- Consommables (flex nom + numéro + chutes) : 1,20 €/pièce
- Cadence : 12 pièces/h (découpe plotter, échenillage, 2 pressages, contrôle)

Usage :
    python tools/cogs_flocage.py                       # tableau des scénarios
    python tools/cogs_flocage.py --volume 250          # coût flocage pour 250 pièces/mois
    python tools/cogs_flocage.py --volume 250 --cout-vierge 9.50 --prix-ttc 29.99
    python tools/cogs_flocage.py --volume 250 --prix-sous-traitance 4.00
"""

import argparse
from dataclasses import dataclass

SMIC_HORAIRE_BRUT = 12.31
TAUX_CHARGES_PATRONALES = 0.12
SEMAINES_PAR_MOIS = 52 / 12
SEMAINES_TRAVAILLEES_PAR_AN = 47
TVA = 0.20

SCENARIOS_HORAIRES = {
    "bas (2h x 5j)": (2.0, 5),
    "moyen (2,5h x 5,5j)": (2.5, 5.5),
    "haut (3h x 6j)": (3.0, 6),
}
VOLUMES_TYPES = [100, 200, 300, 500, 800]


@dataclass
class Atelier:
    heures_par_jour: float = 2.5
    jours_par_semaine: float = 5.5
    salaire_brut_horaire: float = SMIC_HORAIRE_BRUT
    taux_charges: float = TAUX_CHARGES_PATRONALES
    frais_fixes_salarie: float = 30.0
    loyer_ht: float = 400.0
    equipement_mensuel: float = 0.0
    consommables_par_piece: float = 1.20
    pieces_par_heure: float = 12.0

    @property
    def heures_semaine(self) -> float:
        return self.heures_par_jour * self.jours_par_semaine

    @property
    def cout_salarie_mensuel(self) -> float:
        heures_payees = self.heures_semaine * SEMAINES_PAR_MOIS
        return heures_payees * self.salaire_brut_horaire * (1 + self.taux_charges) + self.frais_fixes_salarie

    @property
    def charges_fixes_mensuelles(self) -> float:
        return self.cout_salarie_mensuel + self.loyer_ht + self.equipement_mensuel

    @property
    def capacite_mensuelle(self) -> int:
        heures_productives = self.heures_semaine * SEMAINES_TRAVAILLEES_PAR_AN / 12
        return int(heures_productives * self.pieces_par_heure)

    def cout_flocage_par_piece(self, volume_mensuel: int) -> float:
        return self.charges_fixes_mensuelles / volume_mensuel + self.consommables_par_piece

    def volume_rentable(self, prix_sous_traitance: float) -> float:
        """Volume mensuel à partir duquel floquer en interne coûte moins cher que sous-traiter."""
        marge_par_piece = prix_sous_traitance - self.consommables_par_piece
        if marge_par_piece <= 0:
            return float("inf")
        return self.charges_fixes_mensuelles / marge_par_piece


def euros(montant: float) -> str:
    return f"{montant:,.2f} €".replace(",", " ").replace(".", ",")


def afficher_scenarios(base: Atelier) -> None:
    print("CHARGES FIXES MENSUELLES DE L'ATELIER")
    for nom, (heures, jours) in SCENARIOS_HORAIRES.items():
        atelier = Atelier(**{**base.__dict__, "heures_par_jour": heures, "jours_par_semaine": jours})
        print(
            f"  {nom:<22} {atelier.heures_semaine:>5.2f} h/sem | salarié {euros(atelier.cout_salarie_mensuel):>11}"
            f" + local {euros(atelier.loyer_ht)} = {euros(atelier.charges_fixes_mensuelles):>11}/mois"
            f" | capacité ~{atelier.capacite_mensuelle} pièces/mois"
        )

    print("\nCOÛT DU FLOCAGE PAR PIÈCE (fixes répartis + consommables)")
    print(f"  {'pièces/mois':<22}" + "".join(f"{v:>11}" for v in VOLUMES_TYPES))
    for nom, (heures, jours) in SCENARIOS_HORAIRES.items():
        atelier = Atelier(**{**base.__dict__, "heures_par_jour": heures, "jours_par_semaine": jours})
        cellules = []
        for volume in VOLUMES_TYPES:
            cellule = euros(atelier.cout_flocage_par_piece(volume))
            cellules.append(f"{cellule:>11}" if volume <= atelier.capacite_mensuelle else f"{'saturé':>11}")
        print(f"  {nom:<22}" + "".join(cellules))


def afficher_volume(atelier: Atelier, volume: int, cout_vierge, prix_ttc, prix_sous_traitance) -> None:
    flocage = atelier.cout_flocage_par_piece(volume)
    print(f"Atelier {atelier.heures_semaine:.2f} h/sem — charges fixes {euros(atelier.charges_fixes_mensuelles)}/mois")
    print(f"Volume {volume} pièces/mois (capacité ~{atelier.capacite_mensuelle})")
    if volume > atelier.capacite_mensuelle:
        print("  ATTENTION : volume supérieur à la capacité, il faut plus d'heures")
    print(f"  Coût flocage par pièce : {euros(flocage)}")
    print(f"  Heures réellement nécessaires : {volume / atelier.pieces_par_heure:.1f} h/mois")

    if cout_vierge is not None:
        cogs = cout_vierge + flocage
        print(f"  COGS pièce floquée : {euros(cout_vierge)} (vierge) + {euros(flocage)} (flocage) = {euros(cogs)}")
        if prix_ttc is not None:
            prix_ht = prix_ttc / (1 + TVA)
            marge = prix_ht - cogs
            print(f"  Prix {euros(prix_ttc)} TTC = {euros(prix_ht)} HT -> marge brute {euros(marge)} ({marge / prix_ht:.0%})")

    if prix_sous_traitance is not None:
        seuil = atelier.volume_rentable(prix_sous_traitance)
        print(f"  Rentable vs sous-traitance à {euros(prix_sous_traitance)}/pièce à partir de {seuil:.0f} pièces/mois")


def main() -> None:
    parser = argparse.ArgumentParser(description="COGS OKTAGON avec flocage interne")
    parser.add_argument("--volume", type=int, help="pièces floquées par mois")
    parser.add_argument("--heures-jour", type=float, default=2.5)
    parser.add_argument("--jours-semaine", type=float, default=5.5)
    parser.add_argument("--salaire-brut", type=float, default=SMIC_HORAIRE_BRUT, help="€ brut/h")
    parser.add_argument("--loyer", type=float, default=400.0, help="€ HT/mois")
    parser.add_argument("--equipement", type=float, default=0.0, help="presse/plotter amortis + énergie, €/mois")
    parser.add_argument("--consommables", type=float, default=1.20, help="€/pièce")
    parser.add_argument("--cadence", type=float, default=12.0, help="pièces/heure")
    parser.add_argument("--cout-vierge", type=float, help="coût d'achat HT de l'article non floqué, livré")
    parser.add_argument("--prix-ttc", type=float, help="prix de vente TTC")
    parser.add_argument("--prix-sous-traitance", type=float, help="prix actuel du flocage externe, €/pièce")
    args = parser.parse_args()

    atelier = Atelier(
        heures_par_jour=args.heures_jour,
        jours_par_semaine=args.jours_semaine,
        salaire_brut_horaire=args.salaire_brut,
        loyer_ht=args.loyer,
        equipement_mensuel=args.equipement,
        consommables_par_piece=args.consommables,
        pieces_par_heure=args.cadence,
    )
    if args.volume:
        afficher_volume(atelier, args.volume, args.cout_vierge, args.prix_ttc, args.prix_sous_traitance)
    else:
        afficher_scenarios(atelier)


if __name__ == "__main__":
    main()
