"""
Proxy FFN — relaie les requêtes vers ffn.extranat.fr
et ajoute les headers CORS pour autoriser l'app mobile.
"""
from flask import Flask, request, Response, send_file
import requests as req
import os

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
    response.headers['Access-Control-Allow-Origin']  = '*'
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
    idbas    = request.args.get('bas', '25')
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


@app.route('/proxy/rankings')
def proxy_rankings():
    """Récupère le 16ème temps national pour une épreuve/age/bassin/sexe."""
    idepr = request.args.get('idepr', '')
    idage = request.args.get('idage', '12')
    idbas = request.args.get('idbas', '25')
    idgen = request.args.get('idgen', 'M')
    try:
        r = req.get(
            FFN + 'nat_rankings.php',
            params={
                'idact': 'nat',
                'idbas': idbas,
                'idepr': idepr,
                'idage': idage,
                'idgen': idgen,
            },
            headers={**HEADERS, 'Accept': 'text/html'},
            timeout=15
        )
        return Response(r.content, status=r.status_code,
                        content_type='text/html; charset=utf-8')
    except Exception as e:
        return Response(f'<html><body>Erreur: {e}</body></html>',
                        status=500, content_type='text/html')


@app.route('/')
def index():
    # Cherche index.html à la racine OU dans static/
    for path in ['static/index.html', 'index.html']:
        if os.path.exists(path):
            return send_file(path)
    return 'index.html introuvable', 404


if __name__ == '__main__':
    app.run(debug=True, port=5000)
