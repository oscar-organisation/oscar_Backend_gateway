# Galerie d'identification Open Food Facts (France)

Construit l'artefact `oscar.identification.v2` importé dans la plateforme comme
modèle « Identification de produits ». À exécuter dans l'image du worker, avec
`/work` monté sur un répertoire de travail disposant d'environ 10 Go.

```bash
curl -sL -o food.parquet https://huggingface.co/datasets/openfoodfacts/product-database/resolve/main/food.parquet
python selectionner.py         # 5 000 produits : classements top-100/1000/10000 FR 2025 d'OFF
python photos.py               # photos de face depuis le bucket S3 public d'OFF
python construire_dinov2.py    # empreintes DINOv2, calibration, artefact
python verifier_adaptateur.py  # contrôle hors ligne avec l'adaptateur du worker
```

Choix mesurés, pas supposés :

- **Sélection par les classements par pays d'OFF** (`top-*-fr-scans-2025`). Les
  compteurs de scans bruts des exports CSV et JSONL ont donné, l'un des produits
  marocains, l'autre des fruits en vrac : ils ne reflètent pas la popularité en France.
- **Photos depuis S3** (`openfoodfacts-images`) : le serveur d'images répondait en
  ~12 s par requête depuis le VPS, le bucket en ~0,1 s.
- **DINOv2 ViT-S/14 plutôt que CLIP ViT-B/32** : produit exact retrouvé à 38 / 82 / 96 %
  pour des produits de 80 / 150 / 250 px de haut, contre 16 / 74 / 92 % (galerie de 1 000).
- **Hauteur minimale de 140 px** : en dessous, le bon produit n'arrive en tête qu'une
  fois sur trois ; le worker laisse alors « produit ».

Calibration de la version 1.0.0 (4 981 produits, 600 présents et 400 absents, vues
dégradées de 140 à 320 px) : bon produit en tête 85,3 % sans seuil ; seuil 0,57 et
marge 0,08 pour 90 % de noms justes, 51 % des produits présents nommés, 8,3 % de
produits absents nommés à tort.

Données : Open Food Facts — base ODbL, images CC BY-SA. DINOv2 : Apache 2.0.
