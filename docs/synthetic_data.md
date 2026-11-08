# Données synthétiques — phase 2

Les données de cette phase sont exclusivement synthétiques. Elles servent à vérifier le pipeline et ne décrivent aucun hôpital réel, aucune règle clinique et aucun ratio réglementaire.

## Génération

Depuis la racine du projet :

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m hospital_planning.data.generator
```

La commande lit `configs/hospital.json`, écrit les CSV dans `data/synthetic/` et produit `quality_report.json` dans le même dossier.

Les fichiers sont `historical_demand.csv`, `bed_capacity.csv`, `occupancy.csv`, `staff.csv`, `staff_availability.csv` et `staff_requirements.csv`.

## Hypothèses explicites

- Les admissions sont tirées selon une loi de Poisson dont le taux combine niveau de base, effet hebdomadaire, tendance et événement simulé.
- Les événements et absences utilisent un générateur NumPy local initialisé avec `random_seed`.
- Les fermetures diminuent `beds_operational`, sans jamais rendre la capacité négative.
- Les patients sont représentés par cohortes agrégées; les sorties ont lieu après une durée entière propre au service.
- Un dépassement de capacité est enregistré dans `overflow`; aucun patient n'est supprimé pour respecter artificiellement la capacité.
- Les qualifications, disponibilités et besoins de personnel sont des hypothèses synthétiques et configurables.

## Calibrage du scénario nominal S0

Le scénario nominal conserve 300 lits théoriques, mais les répartit entre les services afin d'éviter une saturation structurelle qui masquerait les effets calendaires : URG 75, MED 106, REA 55 et CHI 64 lits. L'effectif synthétique de médecins est porté de 45 à 50 afin de conserver une couverture qualifiée cohérente avec l'augmentation de capacité de MED.

Ce calibrage ne modifie ni les admissions, ni leurs effets hebdomadaires, tendances ou événements, ni les durées de séjour. Il répond au déséquilibre précédent entre l'occupation moyenne attendue par les cohortes (environ 66 lits en URG et 45 en REA) et les capacités respectives de 40 et 30 lits. Les saturations résiduelles sont conservées comme épisodes de variabilité synthétique; les crises plus fortes seront définies explicitement par les scénarios des phases ultérieures.
