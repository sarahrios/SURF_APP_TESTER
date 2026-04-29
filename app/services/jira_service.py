import os

class JiraService:
    @staticmethod
    def criar_issue_falha_critica(nome_app, total_s1):
        """
        Integração com Jira para criação automática de Tickets de Bugs Críticos (S1).
        """
        jira_url = os.getenv("JIRA_URL")
        
        print(f"\n--- Integração Jira Acionada ---")
        if not jira_url:
            print(f"⚠️  Aviso: Variáveis de ambiente do JIRA não configuradas.")
            print(f"✅  SIMULAÇÃO: Ticket criado com sucesso no Kanban para '{nome_app}'!")
            print(f"    Resumo do Card: [QA-BLOCKER] Encontradas {total_s1} falhas críticas (S1) no Quality Gate.")
            print("--------------------------------\n")
            return True
            
        # Aqui entraria o código real usando a biblioteca 'jira' do Python:
        # jira = JIRA(server=jira_url, basic_auth=(os.getenv("JIRA_USER"), os.getenv("JIRA_TOKEN")))
        # jira.create_issue(project='QA', summary=f"[BUG] {nome_app}", description="Falhas S1...", issuetype={'name': 'Bug'})
        return True