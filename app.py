import base64
import os
import requests
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

@app.route('/iniciar-robo', methods=['POST'])
def iniciar_robo():
    dados = request.json
    empresa_id = dados.get('empresa_id')
    cnpj = dados.get('cnpj')
    tipo_autenticacao = dados.get('tipo_autenticacao')
    senha_portal = dados.get('senha_portal')
    cert_base64 = dados.get('certificado_data')
    cert_senha = dados.get('senha_certificado')

    try:
        with sync_playwright() as p:
            # ==========================================
            # CAMINHO 1: LOGIN COM SENHA WEB
            # ==========================================
            if tipo_autenticacao == 'senha':
                if not senha_portal:
                    return jsonify({"erro": "Senha do portal não fornecida pelo PHP"}), 400
                
                # Inicia o navegador normalmente
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # Acessa a página de login com senha
                page.goto("https://www.nfse.gov.br/Perfil/Contribuinte/Login")
                
                # NOTA: Aqui você coloca os comandos do Playwright do vídeo 
                # para preencher o formulário. Exemplo:
                # page.fill("input[name='cnpj_ou_cpf']", cnpj)
                # page.fill("input[name='senha']", senha_portal)
                # page.click("button[id='btn-login']")

            # ==========================================
            # CAMINHO 2: LOGIN COM CERTIFICADO A1
            # ==========================================
            elif tipo_autenticacao == 'certificado_a1':
                if not cert_base64:
                    return jsonify({"erro": "Certificado digital não fornecido"}), 400
                
                # Recria o arquivo temporário no servidor Linux
                caminho_pfx = f"/tmp/cert_{empresa_id}.pfx"
                with open(caminho_pfx, "wb") as f:
                    f.write(base64.b64decode(cert_base64))
                
                # Inicia o navegador injetando o certificado
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    client_certificates=[{
                        "origin": "https://www.nfse.gov.br",
                        "pfxPath": caminho_pfx,
                        "password": cert_senha
                    }]
                )
                page = context.new_page()
                
                # Acessa direto a rota de login por certificado
                page.goto("https://www.nfse.gov.br/Perfil/Contribuinte/LoginCertificado")
                
                # Remove o arquivo temporário por segurança
                if os.path.exists(caminho_pfx):
                    os.remove(caminho_pfx)
                    
            else:
                return jsonify({"erro": "Tipo de autenticação inválido"}), 400

            # ==========================================
            # ÁREA COMUM: DOWNLOAD E ENVIO PARA O PHP
            # ==========================================
            
            # Aqui entra a lógica do Fabio Mitsueda para navegar até as notas 
            # e capturar os arquivos XML.
            
            # Exemplo de devolução do XML baixado para o seu sistema:
            # url_php = "http://ajudati.gt.tc/receber_notas.php"
            # requests.post(url_php, data={
            #     "empresa_id": empresa_id,
            #     "cnpj": cnpj,
            #     "tipo": "emitida",
            #     "xml_content": xml_baixado
            # })

            browser.close()

        return jsonify({"status": "sucesso", "mensagem": "Robô finalizou as operações."}), 200

    except Exception as e:
        # Garante que o arquivo seja deletado mesmo se o código der erro no meio
        if tipo_autenticacao == 'certificado_a1' and 'caminho_pfx' in locals():
            if os.path.exists(caminho_pfx):
                os.remove(caminho_pfx)
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
