import json, re, time, urllib.request, urllib.error, concurrent.futures as cf
from pathlib import Path
def log(*a): print(time.strftime('[%H:%M:%S]'), *a, flush=True)
racine = Path('/work'); produits = json.load(open(racine / 'selection.json'))
def chemins(code):
    return list(dict.fromkeys('/'.join(re.match(r'^(...)(...)(...)(.*)$', c).groups()) if len(c) > 8 else c for c in (code.zfill(13), code)))
def telecharger(f):
    for chemin in chemins(f['code']):
        try:
            with urllib.request.urlopen(f"https://openfoodfacts-images.s3.eu-west-3.amazonaws.com/data/{chemin}/{f['imgid']}.400.jpg", timeout=20) as r:
                (racine / 'images' / f"{f['code']}.jpg").write_bytes(r.read()); return True
        except urllib.error.HTTPError: continue
        except Exception: time.sleep(1)
    return False
log(f'telechargement de {len(produits)} photos de face depuis S3')
with cf.ThreadPoolExecutor(16) as ex: ok = list(ex.map(telecharger, produits))
produits = [f for f, b in zip(produits, ok) if b]
json.dump(produits, open(racine / 'produits.json', 'w'), ensure_ascii=False)
log(f'{len(produits)} photos disponibles sur {len(ok)}')
