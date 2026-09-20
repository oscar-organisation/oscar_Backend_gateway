"""Controle d'integration : l'adaptateur du worker, charge hors ligne depuis l'artefact,
retrouve-t-il les produits de la galerie ? Verifie la coherence des pretraitements
entre la construction de la galerie et le worker."""
import json, random, sys, time
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, '/src')
from perception_worker.adapters.identification import IdentificationAdapter
from perception_worker.schemas import ModelManifest

m = ModelManifest.model_validate({'id': 'ident', 'name': 'ident', 'version': '1', 'task': 'product_identification',
    'runtime': 'pytorch', 'sha256': '0' * 64, 'artifact_name': 'g.pt', 'artifact_path': '/a', 'input': {}, 'output': {},
    'labels': [], 'inference_fps': 1, 'confidence': 0.5, 'iou_threshold': 0.5, 'overlay_enabled': True,
    'incident_enabled': False, 'camera': 'primary', 'config': {}})
t = time.time(); a = IdentificationAdapter(m, Path('/work/oscar-identification-dinov2-fr.pt'))
print(f'adaptateur charge en {time.time()-t:.1f} s | {len(a.produits)} produits | seuil {a.seuil} marge {a.marge}')
random.seed(3); ech = random.sample(a.produits, 24)
recadrages = [np.asarray(Image.open(f"/work/images/{p['code']}.jpg").convert('RGB')) for p in ech]
t = time.time(); res = a.identifier(recadrages[:6]); lot6 = (time.time() - t) * 1000
res = res + a.identifier(recadrages[6:])
justes = sum(1 for p, r in zip(ech, res) if r and r.code == p['code'])
print(f'photos de reference retrouvees : {justes}/24 | lot de 6 recadrages : {lot6:.0f} ms CPU')
for p, r in list(zip(ech, res))[:5]:
    print('  ', p['nom'][:30], '->', (r.libelle, round(r.score, 3)) if r else None)

# Vues degradees a 200 px de haut, comme un produit proche vu par le robot
import io
from PIL import ImageEnhance, ImageFilter
def vue_robot(chemin, hauteur=200):
    im = Image.open(chemin).convert('RGB'); r = hauteur / im.size[1]
    im = im.resize((max(24, int(im.size[0] * r)), hauteur)).filter(ImageFilter.GaussianBlur(0.6))
    im = ImageEnhance.Brightness(im).enhance(0.85); b = io.BytesIO(); im.save(b, 'JPEG', quality=45)
    return np.asarray(Image.open(b).convert('RGB'))
vues = [vue_robot(f"/work/images/{p['code']}.jpg") for p in ech]
t = time.time(); res = a.identifier(vues[:6]); lot6 = (time.time() - t) * 1000; res += a.identifier(vues[6:])
nommes = [(p, r) for p, r in zip(ech, res) if r]
print(f'vues robot 200 px : {len(nommes)}/24 nommes, dont {sum(1 for p, r in nommes if r.code == p["code"])} justes | lot de 6 : {lot6:.0f} ms')
for p, r in nommes[:6]: print('   ', p['nom'][:28], '->', r.libelle, round(r.score, 2))
