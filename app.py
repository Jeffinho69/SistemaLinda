from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import requests

app = Flask(__name__)

@app.route('/iniciar-robo', methods=['POST'])
def iniciar_robo():
    dados = request.json
    cnpj = dados.get('cnpj')
    senha = dados.get('senha')

    if not cnpj or not senha:
        return jsonify({"erro": "CNPJ e senha são obrigatórios"}), 400

    try:
        # Inicia o Playwright em modo Headless (invisível)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # --- INÍCIO DA AUTOMAÇÃO ---
            # Aqui você adapta a lógica de navegação do vídeo do Mitsueda.
            # Exemplo de acesso:
            # page.goto("URL_DO_PORTAL_NACIONAL")
            # page.fill("input[name='cnpj']", cnpj)
            # page.fill("input[name='senha']", senha)
            # page.click("button[type='submit']")
            # ... lógica de esperar e baixar o XML ...
            
            # Simulando que você pegou o XML e guardou numa variável:
            xml_baixado = "<xml>Conteudo da nota fiscal aqui</xml>" 
            
            # --- FIM DA AUTOMAÇÃO ---

            # Envia o XML baixado para o seu InfinityFree salvar no banco
            url_infinity = "http://SEU_DOMINIO.epizy.com/receber_notas.php"
            requests.post(url_infinity, data={
                "cnpj": cnpj,
                "tipo": "emitida",
                "xml_content": xml_baixado
            })

            browser.close()
            
        return jsonify({"status": "sucesso", "mensagem": "Notas processadas."}), 200

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    # Gunicorn cuidará da porta no Render
    app.run(host='0.0.0.0', port=10000)