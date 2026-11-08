# Plan d'implémentation — Planification des ressources hospitalières

## Résumé et décisions approuvées

`specifications.md` est la source principale des exigences. Ce document est la feuille de route approuvée. Le projet est un prototype local, reproductible et fondé exclusivement sur des données synthétiques. Il utilise Python pour le pipeline métier et Next.js + shadcn/ui pour l'interface, conformément au choix explicite de l'article 2.3 du cahier des charges.

L'architecture est : Next.js/TypeScript/Plotly.js → FastAPI → services Python partagés par l'API et la CLI → génération, prévision, conversion opérationnelle, planification, validation indépendante et stockage CSV/JSON. Les lectures et filtres du dashboard ne déclenchent jamais de calcul. Un seul worker local borné exécutera les tâches lourdes.

Les trois méthodes — heuristique gloutonne, MILP PuLP/CBC et CP-SAT OR-Tools — résoudront une même instance jointe lits/personnel. Elles partageront les données, prévisions, scénarios, capacités, qualifications, contraintes dures, coefficients, budget de calcul et validateur indépendant.

Les admissions demandées, admissions acceptées, admissions refusées, occupation, lits ouverts et lits disponibles sont distincts. Les indicateurs de demande non satisfaite sont exprimés en journées-patients; les admissions refusées sont exprimées en patients. Les ratios, coûts, durées de séjour et règles de travail sont des hypothèses synthétiques configurables.

## Contrats et modèle cible

- Les couches `domain`, `data`, `forecasting`, `optimization`, `experiments`, `storage`, `api` et `frontend` restent découplées. Les contrats typés sont la seule interface entre elles.
- Les résultats normalisent les statuts `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNKNOWN` et `ERROR`; ils conservent statut natif, temps, objectif, écart, empreintes, graine, affectations, allocations et rapport de validation.
- Une politique permissive autorise les déficits de demande et de cible de personnel, mais jamais une violation de disponibilité, qualification, repos, capacité ou dotation minimale des lits ouverts. Une politique stricte exige la couverture complète et peut être infaisable.
- L'occupation future provient de cohortes agrégées: sorties puis admissions chaque jour. Les patients initiaux restent jusqu'à leur sortie simulée. Les lits ouverts doivent être soutenus à chaque poste et pour chaque rôle requis.
- Le modèle emploie des coefficients entiers identiques dans les solveurs pour coût des lits ouverts, journées-patients non couvertes, déficit de personnel cible et déséquilibre de charge.

## Phases, livrables et critères de sortie

| Phase | Livrables | Critère de sortie |
|---|---|---|
| 1. Contrats et fondations | Structure, dépendances verrouillées, schémas, configuration, API minimale, documentation mathématique, fixtures, fumées solveur | Configurations valides; 300 lits; API et solveurs vérifiés |
| 2. Données synthétiques | Générateur 1 095 jours, occupations, personnel, disponibilités, fermetures, rapport qualité | Reproductibilité, conservation et invariants validés |
| 3. Prévision | Naïf, saisonnier, moyenne mobile, lissage exponentiel, régression retardée et évaluation chronologique | Prévisions J+1 à J+7 finies; pas de fuite temporelle |
| 4. Besoins opérationnels | Conversion admissions→occupation, cibles de lits et personnel, instance canonique gelée | Cas calculés à la main et unités validés |
| 5. Heuristique et validateur | Planification déterministe, planning individuel, validation indépendante | Toute solution publiée respecte les contraintes dures |
| 6. MILP et CP-SAT | Deux adaptateurs solveur équivalents, statuts et journaux | Optima identiques sur petites instances et incumbents traités correctement |
| 7. Expériences | Scénarios S0–S5, KPI, stockage, exports et sensibilité | Instances identiques entre méthodes; résultats partiels conservés |
| 8. API applicative | Jobs, récupération de résultats et téléchargements | Contrats HTTP testés; lecture sans calcul |
| 9. Dashboard | Huit pages, visualisations et filtres requis | Totaux affichés cohérents; tests navigateur passent |
| 10. Livraison | README, rapport, démonstration, preuves d'acceptation | Exécution propre sans donnée hospitalière réelle |

La sensibilité exécute 5 taux d'absence × 4 multiplicateurs de demande × 4 réductions de capacité, soit 80 instances et 160 appels exacts. Le profil de démonstration utilisera des budgets plus courts et les résultats conserveront leurs budgets réels.

## Vérification et risques

Les tests couvrent les configurations invalides, la conservation de l'occupation, les fuites temporelles, la capacité, la disponibilité, les qualifications, le repos, les doubles affectations, les scénarios non mutables, les dénominateurs nuls, les erreurs de solveur et les instances infaisables.

Les risques majeurs sont le modèle joint, la dérive entre formulations MILP/CP-SAT, le temps de la grille de sensibilité et la compatibilité Windows des solveurs. Les mitigations sont des fixtures énumérables, un validateur indépendant, des empreintes d'instance, un seul thread de solveur et des tests de fumée dès la phase 1.

## Valeurs par défaut et limites

L'horizon est de 7 jours, l'historique de 1 095 jours et la graine 42. Après recalibrage validé du scénario nominal S0, les capacités sont URG 75, MED 106, REA 55 et CHI 64, pour un total constant de 300 lits. La phase 1 n'implémente ni génération, ni prévision, ni optimisation métier.

PostgreSQL, intervalles prédictifs, Excel, dossiers patients individuels, simulation à événements discrets, gradient boosting, métaheuristiques, optimisation multiobjectif et infrastructure distribuée sont différés. La livraison ne suppose pas qu'un modèle surpasse une baseline ni que chaque instance de crise soit prouvée optimale.
