"""
Proxy FFN — relaie les requêtes vers ffn.extranat.fr
et ajoute les headers CORS pour autoriser l'app mobile.

Version mise à jour : la route /proxy/rankings utilise désormais la vue
"Les Statistiques des rankings" (go=sta), qui donne le 16e temps national
de la saison en cours, pour toutes les épreuves d'un âge / sexe / bassin.
"""
import os
import re
import json
from datetime import datetime
from flask import Flask, request, Response, send_file
import requests as req

app = Flask(__name__)

FFN = 'https://ffn.extranat.fr/webffn/'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'fr-FR,fr;q=0.9',
    'Referer': FFN + 'nat_recherche.php?idact=nat',
}


def cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = '*'
    return response


@app.after_request
def add_cors(response):
    return cors(response)


@app.route('/', methods=['OPTIONS'])
@app.route('/<path:p>', methods=['OPTIONS'])
def handle_options(p=''):
    return cors(Response('', 204))


@app.route('/proxy/search')
def proxy_search():
    q = request.args.get('q', '')
    try:
        r = req.get(
            FFN + '_recherche.php',
            params={'go': 'ind', 'idrch': q},
            headers={**HEADERS, 'X-Requested-With': 'XMLHttpRequest',
                     'Accept': 'application/json, */*'},
            timeout=10
        )
        return Response(r.content, status=r.status_code,
                        content_type='application/json; charset=utf-8')
    except Exception as e:
        return Response(f'{{"error":"{e}"}}', status=500,
                        content_type='application/json')


@app.route('/proxy/perfs')
def proxy_perfs():
    idrch_id = request.args.get('id', '')
    idbas = request.args.get('bas', '25')
    try:
        r = req.get(
            FFN + 'nat_recherche.php',
            params={'idrch_id': idrch_id, 'idbas': idbas, 'idopt': 'prf'},
            headers={**HEADERS, 'Accept': 'text/html'},
            timeout=15
        )
        return Response(r.content, status=r.status_code,
                        content_type='text/html; charset=utf-8')
    except Exception as e:
        return Response(f'<html><body>Erreur: {e}</body></html>',
                        status=500, content_type='text/html')


# --------------------------------------------------------------------------
# RANKINGS — vue "Les Statistiques des rankings" (16e temps national)
# --------------------------------------------------------------------------

def _saison_courante():
    """Année de FIN de la saison FFN en cours (sept -> août). 2026 = 2025-2026."""
    now = datetime.now()
    return now.year + 1 if now.month >= 9 else now.year


def _norm_time(t):
    """'00:27.82' -> '27.82' ; '01:07.32' -> '1:07.32'. None reste None."""
    if not t:
        return None
    m = re.match(r'(\d{1,2}):(\d{2}\.\d{2})$', t)
    if not m:
        return t
    minutes, reste = int(m.group(1)), m.group(2)
    return reste if minutes == 0 else f'{minutes}:{reste}'


def parse_stats(html):
    """Parse le tableau 'Statistiques des rankings' -> (meta, liste d'épreuves)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'lxml')
    tbl = soup.find('table')
    if not tbl:
        return None, []
    rows = tbl.find_all('tr')
    if len(rows) < 3:
        return None, []

    meta = re.sub(r'\s+', ' ', rows[0].get_text()).strip()
    header = [re.sub(r'\s+', ' ', c.get_text()).strip()
              for c in rows[1].find_all(['th', 'td'])]

    col = {}
    for i, h in enumerate(header):
        m = re.search(r'Temps du (\d+)(?:er|e)', h)
        if m:
            col[int(m.group(1))] = i
        if h.startswith('Nbr'):
            col['nbr'] = i

    rangs = (1, 3, 8, 12, 16, 20, 24)
    out = []
    for tr in rows[2:]:
        cells = [re.sub(r'\s+', ' ', c.get_text()).strip()
                 for c in tr.find_all(['th', 'td'])]
        if len(cells) < len(header) or not cells[0]:
            continue
        rec = {'epreuve': cells[0]}
        for rg in rangs:
            v = cells[col[rg]] if rg in col else None
            v = None if v in (None, '---', '') else v
            rec[f't{rg}'] = v
            rec[f't{rg}_norm'] = _norm_time(v)
        rec['nbr'] = (int(re.sub(r'\D', '', cells[col['nbr']]) or 0)
                      if 'nbr' in col else None)
        out.append(rec)
    return meta, out


@app.route('/proxy/rankings')
def proxy_rankings():
    """
    GET /proxy/rankings?age=12&bas=25&sexe=2[&saison=2026]
      sexe : 1=Messieurs, 2=Dames  (accepte aussi 'M'/'F'/'H'/'D')
    Tolère aussi les anciens noms de paramètres (idage/idbas/idgen).
    Renvoie un JSON : { meta, saison, age, bassin, sexe, epreuves: [...] }
    """
    age = request.args.get('age') or request.args.get('idage') \
        or request.args.get('idcat') or '12'
    bas = request.args.get('bas') or request.args.get('idbas') or '25'
    sexe = request.args.get('sexe') or request.args.get('idsex') \
        or request.args.get('idgen') or '2'
    saison = request.args.get('saison') or request.args.get('idsai') \
        or str(_saison_courante())

    smap = {'M': '1', 'H': '1', 'MESSIEURS': '1', 'HOMMES': '1', '1': '1',
            'F': '2', 'D': '2', 'DAMES': '2', 'FEMMES': '2', '2': '2'}
    idsex = smap.get(str(sexe).strip().upper(), '2')

    form = {
        'idact': 'nat', 'go': 'sta', 'idopt': 'sai',
        'idsai': str(saison), 'idbas': str(bas),
        'idcat': str(age), 'idsex': idsex,
        'idmin': '', 'idmax': '', 'idepr': '', 'idreg': '', 'iddep': '',
        'idzon': '', 'idold': '', 'idcot': '', 'idclb': '', 'idsty': '',
        'labelClub': '',
    }
    try:
        s = req.Session()
        s.headers.update(HEADERS)
        s.get(FFN + 'nat_rankings.php', params={'idact': 'nat'}, timeout=15)
        r = s.post(FFN + 'nat_rankings.php', data=form, timeout=20)
        meta, epreuves = parse_stats(r.text)
        payload = {
            'meta': meta, 'saison': str(saison), 'age': str(age),
            'bassin': str(bas), 'sexe': idsex, 'nb_epreuves': len(epreuves),
            'epreuves': epreuves,
            'source': 'ffn.extranat.fr (FFN) - SwimCompare non affilié',
        }
        return Response(json.dumps(payload, ensure_ascii=False),
                        status=200,
                        content_type='application/json; charset=utf-8')
    except Exception as e:
        return Response(json.dumps({'error': str(e)}, ensure_ascii=False),
                        status=500,
                        content_type='application/json; charset=utf-8')


@app.route('/')
def index():
    for path in ['static/index.html', 'index.html']:
        if os.path.exists(path):
            return send_file(path)
    return 'index.html introuvable', 404


if __name__ == '__main__':
    app.run(debug=True, port=5000)
