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

    # Argumentos de otimização pesada para o Render não estourar a memória (RAM)
    browser_args = [
        '--no-sandbox', 
        '--disable-setuid-sandbox', 
        '--disable-dev-shm-usage',
        '--disable-gpu'
    ]

    try:
        with sync_playwright() as p:
            # ==========================================
            # CAMINHO 1: LOGIN COM SENHA WEB
            # ==========================================
            if tipo_autenticacao == 'senha':
                if not senha_portal:
                    return jsonify({"erro": "Senha do portal não fornecida pelo PHP"}), 400
                
                # Inicia o navegador otimizado
                browser = p.chromium.launch(headless=True, args=browser_args)
                context = browser.new_context()
                page = context.new_page()
                
                # Acessa a página de login
                page.goto("https://www.nfse.gov.br/EmissorNacional/Login")
                
                # Preenche os campos baseados na sua inspeção (F12)
                page.wait_for_selector("input[id='Inscricao']", timeout=15000)
                page.fill("input[id='Inscricao']", cnpj)
                page.fill("input[id='Senha']", senha_portal)
                
                # Clica no botão de entrar (Agora usando a classe exata que vimos no print)
                page.click("button[type='submit'].btn-primary")
                page.wait_for_load_state("networkidle")

            # ==========================================
            # CAMINHO 2: LOGIN COM CERTIFICADO A1
            # ==========================================
            elif tipo_autenticacao == 'certificado_a1':
                if not cert_base64:
                    return jsonify({"erro": "Certificado digital não fornecido"}), 400
                
                caminho_pfx = f"/tmp/cert_{empresa_id}.pfx"
                with open(caminho_pfx, "wb") as f:
                    f.write(base64.b64decode(cert_base64))
                
                browser = p.chromium.launch(headless=True, args=browser_args)
                context = browser.new_context(
                    client_certificates=[{
                        "origin": "https://www.nfse.gov.br",
                        "pfxPath": caminho_pfx,
                        "password": cert_senha
                    }]
                )
                page = context.new_page()
                
                page.goto("https://www.nfse.gov.br/EmissorNacional/LoginCertificado")
                page.wait_for_load_state("networkidle")
                
                if os.path.exists(caminho_pfx):
                    os.remove(caminho_pfx)
                    
            else:
                return jsonify({"erro": "Tipo de autenticação inválido"}), 400

            # ==========================================
            # ÁREA DE NAVEGAÇÃO E DOWNLOAD (Com trava de segurança)
            # ==========================================
            
            # Navega para a página de Notas Emitidas
            page.goto("https://www.nfse.gov.br/EmissorNacional/Notas/Emitidas")
            page.wait_for_load_state("networkidle")
            
            try:
                # TENTA clicar no botão de download XML (Ainda usando o nome provisório)
                # Reduzi o timeout para 10 segundos para não derrubar o servidor se não achar
                with page.expect_download(timeout=10000) as download_info:
                    page.click("button.icone-baixar-xml") # <-- AINDA PRECISAMOS DESCOBRIR ESSE NOME REAL
                
                download = download_info.value
                caminho_arquivo_temporario = download.path()
                
                with open(caminho_arquivo_temporario, 'r', encoding='utf-8') as arquivo_xml:
                    xml_baixado = arquivo_xml.read()
                
                # Envia para o InfinityFree
                url_php = "http://ajudati.gt.tc/receber_notas.php"
                resposta = requests.post(url_php, data={
                    "empresa_id": empresa_id,
                    "cnpj": cnpj,
                    "tipo": "emitida",
                    "xml_content": xml_baixado
                })

                browser.close()
                
                if resposta.status_code == 200:
                    return jsonify({"status": "sucesso", "mensagem": "XML capturado e enviado ao banco de dados."}), 200
                else:
                    return jsonify({"erro": f"PHP recusou. Status: {resposta.status_code}"}), 500

            except Exception as e_download:
                # Se não achar o botão de baixar, devolve um aviso pacífico em vez de quebrar tudo
                browser.close()
                return jsonify({
                    "status": "sucesso", 
                    "mensagem": "LOGIN REALIZADO COM SUCESSO! O robô entrou no painel, mas não encontrou o botão de download do XML. Precisamos usar o F12 nessa tela agora."
                }), 200

    except Exception as e:
        if tipo_autenticacao == 'certificado_a1' and 'caminho_pfx' in locals():
            if os.path.exists(caminho_pfx):
                os.remove(caminho_pfx)
        return jsonify({"erro": f"Erro crítico no processo: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
