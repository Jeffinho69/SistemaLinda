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
                
                # Acessa a página de login com senha no portal nacional
                page.goto("https://www.nfse.gov.br/EmissorNacional/Login")
                
                # Preenche os campos de acesso (Aguardando os elementos carregarem na tela)
                page.wait_for_selector("input[id='Inscricao']", timeout=15000)
                page.fill("input[id='Inscricao']", cnpj)
                page.fill("input[id='Senha']", senha_portal)
                
                # Clica no botão de entrar
                page.click("button[id='btnEntrar']")
                page.wait_for_load_state("networkidle")

            # ==========================================
            # CAMINHO 2: LOGIN COM CERTIFICADO A1
            # ==========================================
            elif tipo_autenticacao == 'certificado_a1':
                if not cert_base64:
                    return jsonify({"erro": "Certificado digital não fornecido"}), 400
                
                # Recria o arquivo temporário no servidor Linux do Render
                caminho_pfx = f"/tmp/cert_{empresa_id}.pfx"
                with open(caminho_pfx, "wb") as f:
                    f.write(base64.b64decode(cert_base64))
                
                # Inicia o navegador injetando o certificado digital no contexto
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
                page.goto("https://www.nfse.gov.br/EmissorNacional/LoginCertificado")
                page.wait_for_load_state("networkidle")
                
                # Remove o arquivo do certificado temporário por segurança
                if os.path.exists(caminho_pfx):
                    os.remove(caminho_pfx)
                    
            else:
                return jsonify({"erro": "Tipo de autenticação inválido"}), 400

            # ==========================================
            # ÁREA COMUM: NAVEGAÇÃO, DOWNLOAD E ENVIO
            # ==========================================
            
            # 1. Navega para a página onde ficam as Notas Emitidas
            # (Ajuste esta URL caso o caminho direto seja diferente após o login)
            page.goto("https://www.nfse.gov.br/EmissorNacional/Notas/Emitidas")
            page.wait_for_load_state("networkidle")
            
            # 2. Intercepta o download do arquivo XML
            # Nota: Substitua "button.icone-baixar-xml" pelo seletor CSS exato do botão de baixar XML do portal.
            with page.expect_download() as download_info:
                # O robô clica no botão para exportar/baixar a nota
                page.click("button.icone-baixar-xml")
            
            download = download_info.value
            caminho_arquivo_temporario = download.path()
            
            # 3. Lê o conteúdo do arquivo XML que acabou de ser baixado
            with open(caminho_arquivo_temporario, 'r', encoding='utf-8') as arquivo_xml:
                xml_baixado = arquivo_xml.read()
            
            # 4. Devolve o XML via POST para o banco de dados do Aliado Fiscal no InfinityFree
            url_php = "http://ajudati.gt.tc/receber_notas.php"
            resposta = requests.post(url_php, data={
                "empresa_id": empresa_id,
                "cnpj": cnpj,
                "tipo": "emitida",
                "xml_content": xml_baixado
            })

            browser.close()
            
            if resposta.status_code == 200:
                return jsonify({"status": "sucesso", "mensagem": "Robô finalizou as operações e enviou as notas."}), 200
            else:
                return jsonify({"erro": f"Nota baixada, mas o PHP recusou o recebimento. Status: {resposta.status_code}"}), 500

    except Exception as e:
        # Garante que o arquivo de certificado seja deletado do servidor mesmo se ocorrer uma falha crítica
        if tipo_autenticacao == 'certificado_a1' and 'caminho_pfx' in locals():
            if os.path.exists(caminho_pfx):
                os.remove(caminho_pfx)
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
