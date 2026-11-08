# Contrats de configuration

`hospital.json` est la configuration de référence du pipeline. Ses valeurs sont des hypothèses synthétiques et non des ratios cliniques, réglementaires ou observés.

La section `synthetic_data` contrôle la date de début, les événements, fermetures de lits, absences, effectifs, qualifications et besoins par rôle. Chaque service définit aussi ses effets hebdomadaires, sa tendance, son effet d'événement, sa durée de séjour synthétique et sa part des 300 lits du scénario nominal S0.

`scenarios.json` définit les scénarios d’expérience S0 à S5. Leur transformation et leur exécution sont décrites dans [la documentation des scénarios](../docs/experiments.md).
