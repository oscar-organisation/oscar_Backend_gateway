"""Selection de la galerie : les produits les plus scannes en France (classement Open Food Facts)."""
import json, polars as pl
RANGS = [('top-100-fr-scans-2025', 1), ('top-1000-fr-scans-2025', 2), ('top-10000-fr-scans-2025', 3),
         ('top-1000-fr-scans-2024', 4), ('top-10000-fr-scans-2024', 5)]
f = pl.scan_parquet('/work/food.parquet')
rang = pl.lit(None, dtype=pl.Int32)
for tag, r in reversed(RANGS):
    rang = pl.when(pl.col('popularity_tags').list.contains(tag)).then(pl.lit(r)).otherwise(rang)
d = (f.filter(pl.col('countries_tags').list.contains('en:france'))
      .with_columns(rang.alias('rang'))
      .filter(pl.col('rang').is_not_null())
      .select('code', 'brands', 'rang', 'unique_scans_n',
              pl.col('product_name').list.eval(pl.element().filter(pl.element().struct.field('lang') == 'main')
                                               .struct.field('text')).list.first().alias('nom'),
              pl.col('categories_tags').list.last().alias('categorie'),
              pl.col('images').list.eval(pl.element().filter(pl.element().struct.field('key') == 'front_fr')
                                         .struct.field('imgid')).list.first().alias('imgid'))
      .filter(pl.col('imgid').is_not_null() & pl.col('nom').is_not_null() & (pl.col('nom').str.len_chars() > 1))
      .sort(['rang', 'unique_scans_n'], descending=[False, True], nulls_last=True)
      .head(5000)
      .collect(engine='streaming'))
print('retenus :', d.height, '| par rang :', d.group_by('rang').len().sort('rang').to_dicts())
for r in d.head(25).iter_rows(named=True):
    print(f"  rang {r['rang']} {r['unique_scans_n']!s:>6}  {(r['brands'] or '')[:20]:20s} {r['nom'][:42]:42s} {r['categorie'] or ''}")
print('  ...'); [print(f"  rang {r['rang']} {(r['brands'] or '')[:20]:20s} {r['nom'][:42]}") for r in d.tail(4).iter_rows(named=True)]
prefixes = d.select(pl.col('code').str.slice(0, 3)).to_series().value_counts().sort('count', descending=True).head(6)
print('prefixes GS1 les plus frequents :', prefixes.to_dicts())
json.dump([{'code': r['code'], 'nom': r['nom'][:120], 'marque': (r['brands'] or '').split(',')[0].strip()[:60],
            'categorie': r['categorie'] or '', 'scans': r['unique_scans_n'] or 0, 'imgid': str(r['imgid'])}
           for r in d.iter_rows(named=True)], open('/work/selection.json', 'w'), ensure_ascii=False)
