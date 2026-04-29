import os
import requests

class MondayService:
    @staticmethod
    def criar_item_falha_critica(nome_app, total_s1, falhas=None, pdf_path=None, motivos=None):
        """
        Integração com Monday.com para criação automática de Itens de Bugs Críticos (S1) ou Reprovação Geral.
        """
        # Utilizando o token e board ID fornecidos (com fallback para .env no futuro)
        monday_token = os.getenv("MONDAY_TOKEN", "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjY1MTM2MzQ0NCwiYWFpIjoxMSwidWlkIjo2OTUzMzUzMiwiaWFkIjoiMjAyNi0wNC0yOFQxODowMDoyOS42NzBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MTQ1NDY2NDYsInJnbiI6InVzZTEifQ.DMopOfCffIQal4RXlMK6QzmzcPyAbm5bbO_IytcUAlk")
        monday_board_id = os.getenv("MONDAY_BOARD_ID", "18410657296")
        
        print(f"\n--- Integração Monday.com Acionada ---")
        if not monday_token or not monday_board_id:
            print(f"⚠️  Aviso: Variáveis de ambiente do MONDAY não configuradas (MONDAY_TOKEN, MONDAY_BOARD_ID).")
            print(f"✅  SIMULAÇÃO: Item criado com sucesso no Board para '{nome_app}'!")
            print(f"    Resumo do Item: [QA-BLOCKER] Encontradas {total_s1} falhas críticas (S1) no Quality Gate.")
            print("--------------------------------\n")
            return True
            
        # Código REAL ativado usando a API GraphQL do Monday.com:
        url = "https://api.monday.com/v2"
        headers = {"Authorization": monday_token, "API-Version": "2023-10"}
        
        titulo = f"[QA-REPROVADO] {nome_app}"
        if total_s1 > 0:
            titulo += f" - {total_s1} Falhas S1"
            
        query = 'mutation { create_item (board_id: ' + str(monday_board_id) + ', item_name: "' + titulo + '") { id } }'
        
        # Formata o texto para o comentário com as falhas detalhadas (limpando caracteres especiais)
        texto_erros = "<h2>O App foi Reprovado no Quality Gate</h2><br>"
        if motivos:
            texto_erros += "<b>Motivos da Reprovação:</b><br>"
            for m in motivos:
                texto_formatado = m.replace('"', "'").replace('\n', ' ').replace('\\', '/')
                texto_erros += f"• {texto_formatado}<br>"
            texto_erros += "<br>"
            
        if falhas:
            texto_erros += "<b>Detalhamento de Erros Encontrados:</b><br>"
            for f in falhas:
                if f.get('severidade') in ['S1', 'S2']:
                    msg = f.get('mensagem', '').replace('"', "'").replace('\n', ' ').replace('\\', '/')
                    teste = f.get('teste', '').replace('"', "'").replace('\\', '/')
                    texto_erros += f"• [{f.get('severidade')}] <b>{teste}</b>: {msg}<br>"
        else:
            texto_erros += "Verifique o relatório em anexo para mais detalhes.<br>"

        try:
            # 1. Cria o Item (Card)
            response = requests.post(url, headers=headers, json={'query': query})
            res_json = response.json()
            
            if response.status_code == 200 and "errors" not in res_json:
                item_id = res_json['data']['create_item']['id']
                print(f"✅  REAL: Card criado com sucesso no quadro do Monday.com para '{nome_app}'! (ID: {item_id})")
                
                # 2. Cria o Update (Comentário com as falhas)
                query_update = f'mutation {{ create_update (item_id: {item_id}, body: "{texto_erros}") {{ id }} }}'
                res_update = requests.post(url, headers=headers, json={'query': query_update}).json()
                
                if "errors" not in res_update and 'data' in res_update:
                    update_id = res_update['data']['create_update']['id']
                    print("✅  Comentário com as falhas adicionado.")
                    
                    # 3. Anexa o PDF ao Comentário recém-criado
                    if pdf_path:
                        caminho_real = pdf_path.lstrip("/") if pdf_path.startswith("/") else pdf_path
                        if os.path.exists(caminho_real):
                            file_url = "https://api.monday.com/v2/file"
                            query_file = 'mutation ($file: File!) { add_file_to_update (update_id: ' + str(update_id) + ', file: $file) { id } }'
                            
                            with open(caminho_real, 'rb') as f:
                                files = {'variables[file]': (os.path.basename(caminho_real), f, 'application/pdf')}
                                data = {'query': query_file}
                                res_file = requests.post(file_url, headers=headers, data=data, files=files)
                                
                                if res_file.status_code == 200:
                                    print("✅  Relatório PDF anexado ao card do Monday com sucesso!")
                                else:
                                    print(f"⚠️  Erro ao anexar PDF: {res_file.text}")
                        else:
                            print(f"⚠️  Arquivo PDF não encontrado no disco: {caminho_real}")
            else:
                print(f"⚠️  Erro retornado pela API do Monday ao criar item: {response.text}")
        except Exception as e:
            print(f"⚠️  Erro de conexão com o Monday: {e}")
            
        print("--------------------------------\n")
        return True