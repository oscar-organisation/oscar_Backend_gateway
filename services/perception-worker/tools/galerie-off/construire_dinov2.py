"""Artefact d'identification OSCAR v2 : DINOv2 ViT-S/14 + galerie Open Food Facts France.

Choix de l'encodeur mesure sur banc (galerie de 1 000 produits, vues degradees) :
DINOv2 ViT-S/14 retrouve le produit exact a 38 % / 82 % / 96 % pour 80 / 150 / 250 px
de haut, contre 16 % / 74 % / 92 % pour CLIP ViT-B/32.

L'encodeur est embarque en TorchScript : le worker tourne hors ligne, sans le code
de torch.hub. La calibration ne porte que sur les produits assez grands pour etre
reconnus (HAUTEUR_MIN) : en dessous, le worker n'essaie pas de nommer.
"""
import io, json, random, time
from pathlib import Path
import torch, torchvision.transforms as T
from PIL import Image, ImageEnhance, ImageFilter

torch.set_num_threads(5); random.seed(21)
racine = Path('/work'); produits = json.loads((racine / 'produits.json').read_text())
def log(*a): print(time.strftime('[%H:%M:%S]'), *a, flush=True)
TAILLE, MOYENNE, ECART = 224, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
HAUTEUR_MIN = 140
pre = T.Compose([T.Resize(TAILLE, interpolation=T.InterpolationMode.BICUBIC), T.CenterCrop(TAILLE),
                 T.ToTensor(), T.Normalize(MOYENNE, ECART)])

eager = torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14').eval()
with torch.no_grad():
    script = torch.jit.trace(eager, torch.randn(1, 3, TAILLE, TAILLE))
    x = torch.randn(4, 3, TAILLE, TAILLE)
    ecart_lot = (script(x) - eager(x)).abs().max().item()
log(f'TorchScript trace ; ecart max avec le modele d origine sur un lot de 4 : {ecart_lot:.2e}')
assert ecart_lot < 1e-3, 'la trace ne gere pas la taille de lot : ne pas livrer'
tampon = io.BytesIO(); torch.jit.save(script, tampon); octets_encodeur = tampon.getvalue()

charger = lambda c: Image.open(racine / 'images' / f'{c}.jpg').convert('RGB')
@torch.no_grad()
def encoder(fabriques, lot=32):
    out = []
    for i in range(0, len(fabriques), lot):
        f = script(torch.stack([pre(fab()) for fab in fabriques[i:i+lot]])); out.append(f / f.norm(dim=-1, keepdim=True))
    return torch.cat(out)

def degrader(im, hauteur, rng):
    w, h = im.size; s = rng.uniform(0.85, 1.0); cw, ch = int(w*s), int(h*s)
    x0, y0 = rng.randint(0, w-cw), rng.randint(0, h-ch)
    im = im.crop((x0, y0, x0+cw, y0+ch)).rotate(rng.uniform(-6, 6), expand=True, fillcolor=(40, 40, 40))
    k = rng.uniform(-0.2, 0.2); im = im.transform(im.size, Image.AFFINE, (1, k, -k*im.size[1]/2, 0, 1, 0), fillcolor=(40, 40, 40))
    r = hauteur / im.size[1]; im = im.resize((max(16, int(im.size[0]*r)), hauteur), Image.BILINEAR)
    im = ImageEnhance.Brightness(im).enhance(rng.uniform(0.75, 1.25)).filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.9)))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=rng.randint(35, 60)); return Image.open(b).convert('RGB')

log(f'empreintes de {len(produits)} photos de reference')
galerie = encoder([(lambda c=p['code']: charger(c)) for p in produits])
log('galerie encodee', tuple(galerie.shape))

ids = list(range(len(produits))); random.shuffle(ids)
negatifs, positifs = ids[:400], ids[400:1000]
masque = torch.ones(len(produits), dtype=torch.bool); masque[negatifs] = False
index = torch.nonzero(masque).squeeze(1); g_cal = galerie[index]
rng = random.Random(5)
def interroger(liste):
    hauteurs = [rng.choice((140, 170, 200, 250, 320)) for _ in liste]
    q = encoder([(lambda c=produits[i]['code'], h=h: degrader(charger(c), h, rng)) for i, h in zip(liste, hauteurs)])
    top = (q @ g_cal.T).topk(2, dim=1)
    return top.values[:, 0], top.values[:, 0] - top.values[:, 1], index[top.indices[:, 0]], hauteurs
log('calibration : 600 produits presents, 400 absents, hauteurs de 140 a 320 px')
sp, mp, ip, hp = interroger(positifs); sn, mn, _, _ = interroger(negatifs)
juste = ip == torch.tensor(positifs)
log(f'sans seuil : bon produit en tete {juste.float().mean():.1%}')
meilleur = None
for seuil in [round(0.30 + 0.01*i, 2) for i in range(66)]:
    for marge in (0.0, 0.01, 0.02, 0.03, 0.05, 0.08):
        ap = (sp >= seuil) & (mp >= marge); an = (sn >= seuil) & (mn >= marge)
        affiches = int(ap.sum() + an.sum()); justes = int((ap & juste).sum())
        if not affiches: continue
        precision, rappel = justes / affiches, justes / len(positifs)
        if precision >= 0.90 and (meilleur is None or rappel > meilleur['rappel']):
            meilleur = dict(seuil=seuil, marge=marge, precision=round(precision, 3), rappel=round(rappel, 3),
                            faux_sur_absents=round(float(an.float().mean()), 3), hauteur_min=HAUTEUR_MIN)
log('seuil retenu', meilleur)
if meilleur:
    for h in (140, 170, 200, 250, 320):
        sel = torch.tensor([x == h for x in hp])
        ok = ((sp >= meilleur['seuil']) & (mp >= meilleur['marge']) & juste & sel).sum().item()
        log(f'  a {h} px : {ok}/{int(sel.sum())} produits nommes justement')
paquet = {'format': 'oscar.identification.v2',
          'encoder': {'type': 'torchscript', 'name': 'dinov2_vits14', 'bytes': octets_encodeur,
                      'input': TAILLE, 'mean': MOYENNE, 'std': ECART},
          'embeddings': galerie.half(),
          'products': [{k: p[k] for k in ('code', 'nom', 'marque', 'categorie', 'scans')} for p in produits],
          'calibration': meilleur,
          'source': 'Open Food Facts (https://world.openfoodfacts.org) — base ODbL, images CC BY-SA ; DINOv2 (Apache 2.0)',
          'created': time.strftime('%Y-%m-%d')}
torch.save(paquet, racine / 'oscar-identification-dinov2-fr.pt')
log('artefact ecrit', round((racine / 'oscar-identification-dinov2-fr.pt').stat().st_size / 1e6), 'Mo')
log('FIN')
