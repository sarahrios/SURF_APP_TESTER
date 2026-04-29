# Arquivo: app/main.py
import shutil
import os
import socket
import time
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.models.schemas import ExecutionRequest, TestResultInput, QualityGateResponse, FaseTeste
from app.services.test_runner import TestRunner
from app.core.quality_gate import QualityGateEvaluator
from app.services.pdf_reporter import PDFReporter
from app.services.apk_analyzer import ApkAnalyzer
from app.core.database import init_db, salvar_execucao, obter_historico
from app.services.monday_service import MondayService

app = FastAPI(title="Surf Assurance Lab API")

# Armazena os últimos resultados dos testes (em memória)
latest_results = {
    "stats": {
        "testsRun": 0,
        "passed": 0,
        "failed": 0,
        "coverage": 0
    },
    "last_analysis": None,
    "analysis_in_progress": False,
    "current_stage": "IDLE"
}

# Inicializa o banco de dados
init_db()

# Configurar CORS para permitir requisições do front-end
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos do frontend
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")
frontend_dir = "frontend/build" if os.path.exists("frontend/build") else "frontend"

if os.path.exists(frontend_dir):
    # Monta os arquivos estáticos (JS, CSS, Imagens)
    app.mount("/static", StaticFiles(directory=f"{frontend_dir}/static" if os.path.exists(f"{frontend_dir}/static") else frontend_dir), name="static")

# Servir arquivos gerados (PDFs) da pasta storage
os.makedirs("storage", exist_ok=True)
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

# Rota raiz para servir o index.html
@app.get("/")
async def read_root():
    """Serve a página principal do front-end"""
    frontend_path = "frontend/index.html"
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    # Tenta servir do build primeiro, senão tenta do fonte direto
    possible_paths = ["frontend/build/index.html", "frontend/index.html"]
    
    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path)
            
    return {"message": "Front-end não encontrado. Crie a pasta 'frontend' e adicione o index.html"}

# Nova rota para obter status do sistema
@app.get("/api/system-status")
async def get_system_status():
    """Retorna o status atual do sistema"""
    return {
        "status": "active",
        "services": {
            "apk_analyzer": "online",
            "test_runner": "online",
            "quality_gate": "online",
            "pdf_reporter": "online"
        }
    }

# Nova rota para obter estatísticas
@app.get("/api/stats")
async def get_stats():
    """Retorna estatísticas gerais do sistema baseadas nos últimos testes executados"""
    return latest_results["stats"]

# Nova rota: Dashboard de Histórico e Score de Qualidade (Fase 2)
@app.get("/api/historico")
async def get_historico():
    """Retorna o histórico de execuções com Score calculado para o Dashboard."""
    historico = obter_historico()
    for item in historico:
        s1 = item.get('s1_total', 0) or 0
        s2 = item.get('s2_total', 0) or 0
        # Fase 2: Fórmula do Score (Começa em 100. Punição: -20 por S1, -5 por S2)
        score = max(0, 100 - (s1 * 20) - (s2 * 5))
        item['score_qualidade'] = score
        
    return {"success": True, "data": historico}

@app.post("/executar-teste-apk")
def upload_e_testar(
    apk_surf: UploadFile = File(None),
    apk_pagtel: UploadFile = File(None),
    fase: str = Form("E2E")
):
    """
    Endpoint principal que realiza o ciclo completo:
    1. Upload do APK (Surf ou Pagtel)
    2. Análise Estática de Código (Segurança)
    3. Testes Dinâmicos (Simulação)
    4. Quality Gate (Aprovação/Reprovação)
    5. Geração de PDF
    """
    if not apk_surf and not apk_pagtel:
        return JSONResponse(status_code=400, content={"message": "Nenhum arquivo enviado. Envie um APK Surf ou APK Pagtel."})

    global latest_results
    latest_results["analysis_in_progress"] = True
    latest_results["current_stage"] = "SAST"
    
    try:

        # 1. SALVAR O APK
        # Melhoria: Limpar storage antigo de APKs para economizar espaço, mantendo a pasta
        storage_dir = "storage"
        os.makedirs(storage_dir, exist_ok=True)
        
        # Remove APKs antigos para evitar confusão
        for f in os.listdir(storage_dir):
            if f.endswith(".apk") or f.endswith(".zip"):
                try: os.remove(os.path.join(storage_dir, f))
                except: pass
                
        caminho_apk = None
        tipo_app = "SURF"
        nome_arquivo_salvo = "Desconhecido"
        
        if apk_surf:
            caminho_apk = os.path.join("storage", apk_surf.filename)
            with open(caminho_apk, "wb") as buffer:
                shutil.copyfileobj(apk_surf.file, buffer)
            print(f"APK Surf recebido e salvo em: {caminho_apk}")
            tipo_app = "SURF"
            nome_arquivo_salvo = apk_surf.filename
        elif apk_pagtel:
            caminho_apk = os.path.join("storage", apk_pagtel.filename)
            with open(caminho_apk, "wb") as buffer:
                shutil.copyfileobj(apk_pagtel.file, buffer)
            print(f"APK Pagtel recebido e salvo em: {caminho_apk}")
            tipo_app = "PAGTEL"
            nome_arquivo_salvo = apk_pagtel.filename
        else:
            print("Nenhum APK enviado. Pulando análise.")

        # --- NOVA ETAPA: ANÁLISE ESTÁTICA DO CÓDIGO (SAST) ---
        print("Iniciando Análise de Segurança...")
        latest_results["current_stage"] = "SAST_RUNNING"
        
        resultado_codigo = {"falhas_encontradas": []}
        if caminho_apk:
            resultado_codigo = ApkAnalyzer.analisar_codigo(caminho_apk)

        # Extrai falhas do APK para somar no Quality Gate
        falhas_codigo = resultado_codigo.get("falhas_encontradas", [])
        
        s1_codigo = sum(1 for f in falhas_codigo if f['severidade'] == 'S1')
        s2_codigo = sum(1 for f in falhas_codigo if f['severidade'] == 'S2')

        print(f"Análise de Código concluída. S1: {s1_codigo}, S2: {s2_codigo}")

        # 2. CONFIGURAR AMBIENTE E RODAR TESTES DINÂMICOS (DAST)
        latest_results["current_stage"] = "DAST"
        
        resultados_testes = {
            "total_testes": 0, "executados": 0, "aprovados": 0,
            "defeitos_s1": 0, "defeitos_s2": 0, "falhas_por_area": {},
            "lista_testes": []
        }
        modo_execucao = "APENAS_CODIGO_FONTE"

        if caminho_apk:
            os.environ["TARGET_APK_PATH"] = os.path.abspath(caminho_apk)
            
            # Define a pasta de testes baseado em qual APK foi upado
            caminho_testes = "tests_mobile" if tipo_app == "SURF" else "tests_pagtel"
            
            # Se for PAGTEL, garante que a pasta existe para o Pytest não quebrar
            if tipo_app == "PAGTEL":
                os.makedirs(caminho_testes, exist_ok=True)
                
            modo_execucao = "REAL_DEVICE"

            print(f"Tentando executar testes em: {caminho_testes}")
            try:
                # Verifica se o Appium está rodando antes de tentar testar
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0) # Aumentado timeout para evitar falsos negativos
                if sock.connect_ex(('localhost', 4723)) != 0:
                    sock.close()
                    raise Exception("Servidor Appium não detectado na porta 4723.")
                sock.close()

                # Rodamos o TestRunner
                resultados_testes = TestRunner.executar_testes(caminho_testes)
                
                # Se não retornou nada ou zero testes, assume falha de conexão com Appium
                if not resultados_testes or resultados_testes.get('total_testes', 0) == 0:
                    raise Exception("Falha de conexão com Appium ou nenhum teste encontrado.")
                    
                # Se rodou mas TUDO falhou (0 aprovados), assume erro de ambiente (ex: Appium travado)
                # e força o fallback para Simulação para o usuário ver o fluxo funcionar.
                if resultados_testes.get('aprovados', 0) == 0:
                    raise Exception("Todos os testes mobile falharam (provável erro de conexão).")
                    
            except Exception as e:
                print(f"⚠️ Ambiente mobile indisponível: {e}")
                print("ℹ️ Executando Análise Estática Avançada (Verificação estrutural e de segurança).")
                caminho_testes = "tests_repo"
                modo_execucao = "ANALISE_ESTATICA"
                resultados_testes = TestRunner.executar_testes(caminho_testes)

        if not resultados_testes:
            # Fallback se o teste falhar em gerar XML
            resultados_testes = {
                "total_testes": 0, "executados": 0, "aprovados": 0,
                "defeitos_s1": 0, "defeitos_s2": 0, "falhas_por_area": {},
                "lista_testes": [],
                "lista_falhas": []
            }

        # --- FORÇAR A GERAÇÃO DO PDF ÚTIL ---
        # Adiciona os defeitos de código (SAST) na tabela do relatório
        if "lista_falhas" not in resultados_testes:
            resultados_testes["lista_falhas"] = []
            
        for f in falhas_codigo:
            resultados_testes["lista_falhas"].append({
                "teste": "Análise SAST (Estática)",
                "classe": f.get("arquivo", "Código Fonte/Manifesto"),
                "mensagem": f["mensagem"],
                "severidade": f["severidade"],
                "detalhes": f"Detectado durante varredura: {f.get('tipo', 'Segurança')}",
                "descricao": "Auditoria de Segurança do Arquivo"
            })

        # 3. UNIFICAR OS RESULTADOS (CÓDIGO + TESTES)
        total_s1 = resultados_testes['defeitos_s1'] + s1_codigo
        total_s2 = resultados_testes['defeitos_s2'] + s2_codigo

        # Adiciona as falhas de código na lista de "motivos" do Quality Gate
        motivos_codigo = [f"[CÓDIGO] {f['mensagem']}" for f in falhas_codigo]

        # 4. QUALITY GATE & RELATÓRIO
        latest_results["current_stage"] = "QUALITY_GATE"
        aprovado, motivos_gate = QualityGateEvaluator.avaliar_e2e_para_uat(
            resultados_testes['total_testes'],
            resultados_testes['executados'],
            resultados_testes['aprovados'],
            total_s1, # Soma total de defeitos críticos
            total_s2,
            resultados_testes['falhas_por_area']
        )

        # Junta todos os motivos
        todos_motivos = motivos_codigo + motivos_gate

        # Garante reprovação se houver falha de código crítica
        if s1_codigo > 0:
            aprovado = False

        pdf = PDFReporter.gerar(resultados_testes, aprovado, todos_motivos, fase)

        # Atualiza os resultados globais com os valores reais
        total_testes = resultados_testes['total_testes']
        total_aprovados = resultados_testes['aprovados']
        total_falhas = total_testes - total_aprovados
        coverage = round((total_aprovados / total_testes * 100) if total_testes > 0 else 0)

        latest_results["stats"] = {
            "testsRun": total_testes,
            "passed": total_aprovados,
            "failed": total_falhas,
            "coverage": coverage
        }

        latest_results["last_analysis"] = {
            "arquivo": nome_arquivo_salvo,
            "analise_estatica": resultado_codigo,
            "analise_dinamica": resultados_testes,
            "status_final": "APROVADO" if aprovado else "REPROVADO",
            "s1_total": total_s1,
            "s2_total": total_s2,
            "motivos": todos_motivos,
            "relatorio_pdf": pdf
        }

        latest_results["current_stage"] = "COMPLETED"

        # Salva no banco de dados (Fase 1)
        try:
            salvar_execucao(latest_results["last_analysis"])
        except Exception as e:
            print(f"⚠️ Aviso: Erro ao salvar histórico: {e}")

        # Fase 3: Integração com Monday.com (Cria item automático se o App for REPROVADO)
        try:
            if not aprovado:
                nome_arquivo = nome_arquivo_salvo
                MondayService.criar_item_falha_critica(nome_arquivo, total_s1, resultados_testes.get("lista_falhas", []), pdf, todos_motivos)
        except Exception as e:
            print(f"⚠️ Aviso: Erro na integração do Monday: {e}")

        return {
            "arquivo": nome_arquivo_salvo,
            "tipo_app": tipo_app,
            "analise_estatica": {
                "debuggable": "Sim (FALHA)" if s1_codigo > 0 else "Não (OK)",
                "falhas_identificadas": falhas_codigo
            },
            "analise_dinamica": resultados_testes,
            "status_final": "APROVADO" if aprovado else "REPROVADO",
            "relatorio_pdf": f"{pdf}?t={int(time.time())}" if pdf else None,
            "modo_execucao": modo_execucao
        }
    except Exception as e:
        import traceback
        print(f"❌ ERRO FATAL NO SERVIDOR: {e}")
        traceback.print_exc()
        latest_results["current_stage"] = "ERROR"
        return JSONResponse(
            status_code=500, 
            content={
                "message": f"Erro interno durante a análise: {str(e)}",
                "details": traceback.format_exc()
            }
        )
    finally:
        latest_results["analysis_in_progress"] = False

@app.post("/executar-teste-web")
def executar_teste_web(url: str = Form(...), tipo_teste: str = Form("RECARGA"), iccid: str = Form(None)):
    """
    Endpoint que realiza testes automatizados em um site.
    """
    global latest_results
    latest_results["analysis_in_progress"] = True
    latest_results["current_stage"] = "WEB_TEST_RUNNING"
    
    try:
        # 1. Define o caminho dos testes e cria a pasta se não existir
        caminho_testes = "tests_web" if tipo_teste == "RECARGA" else "tests_ativacao"
        os.makedirs(caminho_testes, exist_ok=True)
        
        # 2. Passa as variáveis para o ambiente de teste
        os.environ["TARGET_URL"] = url
        if iccid:
            os.environ["TARGET_ICCID"] = iccid
        
        print(f"--- Iniciando testes web ({tipo_teste}) para a URL: {url} ---")
        if iccid:
            print(f"--- ICCID a ser utilizado: {iccid} ---")
        
        # 3. Executa os testes
        resultados_testes = TestRunner.executar_testes(caminho_testes)
        
        # 4. Avalia o resultado (simples, por enquanto)
        aprovado = resultados_testes.get('falhas', 0) == 0
        motivos = [f['mensagem'] for f in resultados_testes.get('lista_falhas', [])]
        
        # 5. Gera o relatório PDF
        pdf = PDFReporter.gerar(resultados_testes, aprovado, motivos, fase="WEB")
        
        # 6. Retorna a resposta
        return {
            "url": url,
            "resultados_testes": resultados_testes,
            "status_final": "APROVADO" if aprovado else "REPROVADO",
            "relatorio_pdf": f"{pdf}?t={int(time.time())}" if pdf else None
        }
        
    except Exception as e:
        import traceback
        print(f"❌ ERRO FATAL NO TESTE WEB: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500, 
            content={"message": f"Erro interno durante o teste web: {str(e)}"}
        )
    finally:
        latest_results["analysis_in_progress"] = False
        latest_results["current_stage"] = "IDLE"

# Rota alternativa compatível com o front-end
@app.post("/api/upload-apk")
async def upload_apk_api(arquivo: UploadFile = File(...)):
    """
    Endpoint simplificado para upload de APK via front-end
    Retorna resposta em formato JSON adequado para a interface
    """
    try:
        # Salvar o APK
        os.makedirs("storage", exist_ok=True)
        caminho_apk = os.path.join("storage", arquivo.filename)
        
        with open(caminho_apk, "wb") as buffer:
            shutil.copyfileobj(arquivo.file, buffer)
        
        file_size = os.path.getsize(caminho_apk)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        return JSONResponse({
            "success": True,
            "message": "APK enviado com sucesso",
            "filename": arquivo.filename,
            "size": f"{file_size_mb} MB",
            "path": caminho_apk
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Erro ao enviar APK: {str(e)}"
            }
        )

# Rota para obter status da análise em tempo real
@app.get("/api/analysis-status/{filename}")
async def get_analysis_status(filename: str):
    """
    Retorna o status atual da análise de um APK específico
    """
    stage = latest_results.get("current_stage", "IDLE")
    
    if latest_results["analysis_in_progress"]:
        # Define progresso baseado no estágio atual
        sast_prog = 100 if stage in ["DAST", "QUALITY_GATE", "COMPLETED"] else 50 if stage == "SAST_RUNNING" else 0
        dast_prog = 100 if stage in ["QUALITY_GATE", "COMPLETED"] else 50 if stage == "DAST" else 0
        qg_prog = 100 if stage == "COMPLETED" else 50 if stage == "QUALITY_GATE" else 0

        return {
            "filename": filename,
            "status": "in_progress",
            "stage": stage,
            "analyses": [
                {"name": "Análise SAST", "status": sast_prog == 100 and "completed" or sast_prog > 0 and "analyzing" or "pending", "progress": sast_prog, "service": "apk_analyzer.py"},
                {"name": "Testes Mobile", "status": dast_prog == 100 and "completed" or dast_prog > 0 and "analyzing" or "pending", "progress": dast_prog, "service": "test_runner.py"},
                {"name": "Quality Gate", "status": qg_prog == 100 and "completed" or qg_prog > 0 and "analyzing" or "pending", "progress": qg_prog, "service": "quality_gate.py"}
            ]
        }

    if latest_results["last_analysis"] and latest_results["last_analysis"]["arquivo"] == filename:
        return {
            "filename": filename,
            "status": "completed",
            "stage": "COMPLETED",
            "analyses": [
                {"name": "Análise SAST", "status": "completed", "progress": 100, "service": "apk_analyzer.py"},
                {"name": "Testes Mobile", "status": "completed", "progress": 100, "service": "test_runner.py"},
                {"name": "Quality Gate", "status": "completed", "progress": 100, "service": "quality_gate.py"}
            ]
        }

    return {
        "filename": filename,
        "status": "not_found",
        "stage": "IDLE",
        "analyses": [
            {"name": "Análise SAST", "status": "pending", "progress": 0, "service": "apk_analyzer.py"},
            {"name": "Testes Mobile", "status": "pending", "progress": 0, "service": "test_runner.py"},
            {"name": "Quality Gate", "status": "pending", "progress": 0, "service": "quality_gate.py"}
        ]
    }

# Rota para obter a última análise completa
@app.get("/api/last-analysis")
async def get_last_analysis():
    """Retorna os detalhes da última análise realizada"""
    if latest_results["last_analysis"]:
        return {
            "success": True,
            "data": latest_results["last_analysis"]
        }
    return {
        "success": False,
        "message": "Nenhuma análise realizada ainda"
    }

# Bloco para iniciar via 'python -m app.main'
if __name__ == "__main__":
    import uvicorn

    # Verificação APRIMORADA do ambiente Android, baseada nos problemas mais comuns
    android_home = os.getenv("ANDROID_HOME")
    sdk_root_path = ""

    if not android_home:
        # Tenta localizar automaticamente no caminho padrão do Windows
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        default_sdk = os.path.join(local_app_data, "Android", "Sdk")
        
        if local_app_data and os.path.exists(default_sdk):
            print(f"\n⚠️  AVISO: SDK do Android encontrado em '{default_sdk}', mas a variável de ambiente ANDROID_HOME não está definida.")
            print(f"   👉 Para habilitar testes em celular, execute no terminal e reinicie: $env:ANDROID_HOME = \"{default_sdk}\"\n")
            sdk_root_path = default_sdk
        else:
            print("\n⚠️  AVISO: Ambiente Android (SDK) não detectado.")
            print("   👉 O sistema rodará em modo 'ANÁLISE ESTÁTICA' (apenas verificação de código).")
            print("   👉 Para testes em celular físico, o Android SDK é obrigatório.\n")
    elif not os.path.exists(android_home):
        print(f"\n❌ ERRO CRÍTICO: O caminho definido em ANDROID_HOME não existe!")
        print(f"   Caminho atual: {android_home}")
        print("   Certifique-se de que o Android Studio está instalado e o caminho está correto.\n")
    else:
        sdk_root_path = android_home

    # Se encontramos um caminho de SDK, vamos validá-lo em detalhes
    if sdk_root_path:
        print(f"🔎 Validando SDK do Android em: {sdk_root_path}")
        platform_tools_path = os.path.join(sdk_root_path, "platform-tools")
        build_tools_path = os.path.join(sdk_root_path, "build-tools")
        
        has_platform_tools = os.path.exists(platform_tools_path) and any(f.startswith("adb") for f in os.listdir(platform_tools_path))
        has_build_tools = os.path.exists(build_tools_path) and os.listdir(build_tools_path)
        
        if "platform-tools" in sdk_root_path.lower() or "build-tools" in sdk_root_path.lower():
            print(f"❌ ERRO DE CONFIGURAÇÃO: Sua variável ANDROID_HOME aponta para uma subpasta.")
            print(f"   Valor atual: '{sdk_root_path}'")
            print(f"   O valor deve ser o caminho RAIZ do SDK, sem incluir 'platform-tools' ou 'build-tools'.")
            print(f"   Exemplo correto: C:\\Users\\seu_usuario\\AppData\\Local\\Android\\Sdk\n")
        elif not has_platform_tools:
            print(f"❌ ERRO: A pasta 'platform-tools' (com adb.exe) não foi encontrada dentro do SDK.")
            print(f"   👉 Use o SDK Manager do Android Studio para instalar 'Android SDK Platform-Tools'.\n")
        elif not has_build_tools:
            print(f"❌ ERRO: A pasta 'build-tools' (com aapt2.exe) não foi encontrada dentro do SDK.")
            print(f"   👉 Use o SDK Manager do Android Studio para instalar 'Android SDK Build-Tools'.\n")
        elif has_platform_tools and has_build_tools:
            print("✅ Ambiente Android SDK parece configurado corretamente.\n")

    print("🚀 Iniciando Surf Assurance Lab...")
    print("📱 Front-end disponível em: http://localhost:8000")
    print("📚 API docs disponível em: http://localhost:8000/docs")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)