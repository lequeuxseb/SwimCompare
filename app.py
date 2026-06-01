"""
Proxy FFN — relaie les requêtes vers ffn.extranat.fr
et ajoute les headers CORS pour autoriser l'app mobile.
"""
from flask import Flask, request, Response, send_from_directory
import requests as req

app = Flask(__name__, static_folder='static')

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


@app.route('/options', methods=['OPTIONS'])
@app.route('/<path:p>', methods=['OPTIONS'])
def handle_options(p=''):
    return cors(Response('', 204))


@app.route('/proxy/search')
def proxy_search():
    """Recherche nageur via l'API AJAX FFN."""
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
    """Récupère la page HTML des performances d'un nageur."""
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


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


if __name__ == '__main__':
    app.run(debug=True, port=5000)
