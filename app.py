import base64
import os
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

@app.route('/iniciar-robo', methods=['POST'])
def iniciar_robo():
    dados = request.json
    empresa_id = dados.get('empresa_id')
    cnpj = dados.get('cnpj')
    cert_base64 = dados.get('certificado_data')
    cert_senha = dados.get('senha_certificado')

    if not cert_base64:
        return jsonify({"erro": "Certificado digital nao fornecido"}), 400

    # Define um caminho temporário no servidor para criar o arquivo do certificado
    caminho_pfx = f"/tmp/cert_{empresa_id}.pfx"

    try:
        # Decodifica a string Base64 de volta para o arquivo binário .pfx
        with open(caminho_pfx, "wb") as f:
            f.write(base64.b64decode(cert_base64))

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            # AQUI ESTÁ O SEGREDO: Criamos o contexto injetando o certificado digital no navegador
            context = browser.new_context(
                client_certificates=[{
                    "origin": "https://www.nfse.gov.br", # URL base do portal de login
                    "pfxPath": caminho_pfx,
                    "password": cert_senha
                }]
            )
            
            page = context.new_page()
            
            # Quando a página abrir a tela de login por certificado, o Playwright
            # vai responder automaticamente com as credenciais do arquivo .pfx
            page.goto("https://www.nfse.gov.br/Perfil/Contribuinte/Login")
            
            # ... Lógica de clique no botão "Entrar com Certificado Digital" ...
            # ... Restante do script de raspagem e download das notas ...
            
            browser.close()

        # Remove o arquivo do certificado por questões de segurança após o uso
        if os.path.exists(caminho_pfx):
            os.remove(caminho_pfx)

        return jsonify({"status": "sucesso"}), 200

    except Exception as e:
        if os.path.exists(caminho_pfx):
            os.remove(caminho_pfx)
        return jsonify({"erro": str(e)}), 500
