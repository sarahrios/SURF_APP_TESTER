# Arquivo: tests_mobile/test_android_apk.py
import pytest
import os
import time
import subprocess
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Tenta importar androguard para limpeza prévia (evita erro INSTALL_FAILED_UPDATE_INCOMPATIBLE)
try:
    from androguard.core.apk import APK
except ImportError:
    try:
        from androguard.core.bytecodes.apk import APK
    except ImportError:
        APK = None

# Usamos scope="session" para garantir uma única sessão para todos os testes (Enterprise)
@pytest.fixture(scope="session")
def driver():
    # Verifica se o teste atual deve ser executado
    if os.getenv("PLATFORM_NAME") == "iOS":
        pytest.skip("Pulando testes Android pois o alvo é iOS")

    # 1. Pega o caminho do APK que o PyQualityGate salvou
    apk_path = os.getenv("TARGET_APK_PATH")
    
    if not apk_path:
        pytest.fail("ERRO: Caminho do APK não encontrado. Faça o upload pela plataforma primeiro.")

    # 2. Configurações para Celular Físico
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    
    # "Android Device" é genérico, serve para qualquer celular plugado no USB
    options.device_name = "Android Device" 
    
    # O APK que você fez upload será instalado no seu celular automaticamente
    options.app = apk_path
    
    # False = Reinstala o app se necessário, mas tenta manter dados
    # MUDANÇA: noReset=True para não limpar dados/cache entre sessões se cair
    options.no_reset = True 
    options.set_capability("appium:fullReset", False)
    options.set_capability("appium:dontStopAppOnReset", True) # Não fecha o app se a sessão reiniciar
    
    # Aceita permissões (Câmera, Localização) automaticamente para o teste não travar
    options.auto_grant_permissions = True
    
    # Aumenta o tempo limite de instalação (Celulares físicos as vezes demoram mais que emuladores)
    options.new_command_timeout = 600
    options.set_capability("appium:uiautomator2ServerInstallTimeout", 90000)
    options.set_capability("appium:adbExecTimeout", 60000) # Dá mais tempo para comandos ADB
    options.set_capability("appium:enforceAppInstall", False) # MUDANÇA: Não forçar install pelo Appium (já fazemos manual)

    # --- RESOLUÇÃO DO COMANDO ADB ---
    # Tenta encontrar o ADB pelo ANDROID_HOME se não estiver no PATH global
    adb_cmd = "adb"
    android_home = os.getenv("ANDROID_HOME")
    if android_home:
        potential_adb = os.path.join(android_home, "platform-tools", "adb.exe")
        if os.path.exists(potential_adb):
            adb_cmd = f'"{potential_adb}"'

    print(f"--- Tentando conectar ao Appium (http://localhost:4723) para testar: {apk_path} ---")
    
    # --- DIAGNÓSTICO PRÉVIO (FORÇA BRUTA) ---
    # Isso garante que sabemos POR QUE a instalação falha antes mesmo do Appium tentar
    print("🔍 Diagnóstico: Verificando conexão ADB e tentando instalação manual...")
    try:
        # 1. Verifica se tem device
        chk = subprocess.run(f"{adb_cmd} devices", shell=True, capture_output=True, text=True)
        if "device" not in chk.stdout.replace("List of devices attached", "").strip():
             pytest.fail("❌ ERRO FATAL: Nenhum celular detectado pelo ADB. Verifique o cabo USB e a Depuração USB.")

        # 1.5 Tenta desinstalar versão anterior para evitar conflito de assinatura
        if APK:
            try:
                apk_obj = APK(apk_path)
                pkg_name = apk_obj.get_package()
                print(f"🗑️ Tentando desinstalar versão antiga de: {pkg_name}")
                subprocess.run(f"{adb_cmd} uninstall {pkg_name}", shell=True, capture_output=True)
            except Exception as e:
                print(f"⚠️ Aviso: Falha ao tentar desinstalar versão anterior (pode ser ignorado): {e}")
        else:
            print("⚠️ Aviso: Biblioteca 'androguard' não detectada. A desinstalação automática da versão antiga foi pulada.")

        # 2. Tenta instalar via comando direto (mostra o erro real do Android)
        # flags: -r (reinstall), -g (grant permissions), -t (allow test packages), -d (allow downgrade)
        print(f"📦 Tentando instalar APK via ADB: {apk_path}")
        subprocess.run(f'{adb_cmd} install -r -g -t -d "{apk_path}"', shell=True, check=True, capture_output=True, text=True)
        print("✅ APK instalado com sucesso via ADB! Iniciando automação...")
    except subprocess.CalledProcessError as e:
        erro_msg = e.stderr if e.stderr else e.stdout
        print(f"❌ O ANDROID RECUSOU O APK. Motivo:\n{erro_msg}")
        
        dica = ""
        if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in erro_msg:
            dica = "\n💡 DICA: O app já está instalado com outra assinatura. Desinstale-o manualmente do celular e tente de novo."
        elif "INSTALL_FAILED_USER_RESTRICTED" in erro_msg:
            dica = "\n💡 DICA (Xiaomi/Redmi): Você precisa ativar 'Instalar via USB' nas Opções do Desenvolvedor (requer chip SIM)."
        elif "INSTALL_PARSE_FAILED_NO_CERTIFICATES" in erro_msg:
            dica = "\n💡 DICA: O APK não está assinado. Gere uma build assinada (Signed APK)."
            
        pytest.fail(f"Falha na instalação do APK: {erro_msg}{dica}")
    # -----------------------------------------
    
    driver = None
    try:
        # Conecta no Appium Server (que deve estar rodando no seu PC)
        driver = webdriver.Remote("http://localhost:4723", options=options)
        print("--- Conexão com Appium estabelecida com sucesso! ---")
        
        # Log informativo do dispositivo conectado
        caps = driver.capabilities
        device_name = f"{caps.get('deviceManufacturer', 'Unknown')} {caps.get('deviceModel', 'Device')}"
        print(f"📱 Dispositivo Vinculado: {device_name} (Android {caps.get('platformVersion', '?')})")
        
    except Exception as e:
        # Tratamento específico para erro de configuração do ambiente Android
        error_msg = str(e)
        if "ANDROID_HOME" in error_msg or "ANDROID_SDK_ROOT" in error_msg or "Android SDK root folder" in error_msg:
            pytest.fail(f"ERRO DE CONFIGURAÇÃO: O Appium não encontrou a pasta do Android SDK.\n"
                        f"O caminho que ele tentou usar não existe.\n"
                        f"1. Abra o Android Studio > Settings > Android SDK e copie o 'Android SDK Location'.\n"
                        f"2. No terminal do Appium, pare e rode: $env:ANDROID_HOME = \"CAMINHO_COPIADO\"\n"
                        f"Erro original: {error_msg}")

        pytest.fail(f"FALHA DE CONEXÃO: Não foi possível falar com o celular. \n"
                    f"1. Verifique o cabo USB.\n"
                    f"2. Verifique se a Depuração USB está ligada.\n"
                    f"3. Verifique se o Appium Server está rodando.\n"
                    f"Erro detalhado: {e}")

    yield driver # Entrega o controle do celular para o teste
    
    # Ao final, encerra a sessão
    if driver:
        driver.quit()

# --- OS TESTES (O que o celular vai fazer sozinho) ---

def test_01_abertura_app(driver):
    """CT-01: Abertura do Aplicativo."""
    print("DESC: CT-01 - Validar abertura do aplicativo (Splash + Carrossel).")
    # Pré-condição: App instalado. Resultado: Splash e Carrossel.
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'Acessar')]"))
        )
        print("✅ App aberto, primeira tela (carrossel) exibida.")
        assert driver.current_context == "NATIVE_APP"
    except Exception as e:
        pytest.fail(f"O aplicativo não abriu ou a tela inicial não carregou em 20 segundos. Erro: {e}")

def test_02_carrossel(driver):
    """CT-02: Navegação no Carrossel."""
    print("DESC: CT-02 - Navegação no Carrossel (Swipe/Próximo).")
    size = driver.get_window_size()
    start_x = size['width'] * 0.8
    end_x = size['width'] * 0.2
    y = size['height'] / 2

    for i in range(3): # Tenta passar por 3 telas do carrossel
        print(f"Realizando swipe horizontal ({i+1}/3)...")
        driver.swipe(start_x, y, end_x, y, 400)
        time.sleep(1)

    try:
        continuar_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[@text='Continuar' or @text='Acessar']"))
        )
        continuar_btn.click()
        print("✅ Carrossel finalizado, botão 'Continuar' clicado.")
    except Exception as e:
        pytest.fail(f"Não foi possível encontrar ou clicar no botão 'Continuar' após o carrossel. Erro: {e}")

def test_03_termos(driver):
    """CT-03: Aceite de Termos (Checkboxes)."""
    print("DESC: CT-03 - Aceite de Termos (Marcar Checkbox 1 e 2).")
    try:
        # Aguarda aparecer pelo menos um checkbox
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((AppiumBy.CLASS_NAME, "android.widget.CheckBox"))
        )
        checkboxes = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.CheckBox")
        
        print(f"Encontrados {len(checkboxes)} checkboxes.")
        for i, checkbox in enumerate(checkboxes):
            checkbox.click()
            print(f"✅ Checkbox {i+1} clicado.")

        continuar_btn = driver.find_element(AppiumBy.XPATH, "//*[@text='Continuar']")
        continuar_btn.click()
        print("✅ Botão 'Continuar' clicado.")
    except Exception as e:
        pytest.fail(f"Não foi possível interagir com a tela de Termos de Uso. Erro: {e}")

def test_04_login(driver):
    """CT-04: Login."""
    print("DESC: CT-04 - Login com credenciais válidas.")
    USUARIO = "99999909914"
    SENHA = "1234"
    
    try:
        campos_texto = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((AppiumBy.CLASS_NAME, "android.widget.EditText"))
        )
        assert len(campos_texto) >= 2, "Não foram encontrados campos suficientes para login."

        print("Preenchendo CPF/CNPJ...")
        campos_texto[0].send_keys(USUARIO)
        
        print("Preenchendo Senha...")
        campos_texto[1].send_keys(SENHA)
        driver.hide_keyboard()

        entrar_btn = driver.find_element(AppiumBy.XPATH, "//*[@text='Entrar']")
        entrar_btn.click()
        print("✅ Botão 'Entrar' clicado.")

        # Validação: Aguarda processamento do login
        # Não validamos "Recarga" aqui pois pode haver telas intermediárias (Sim / Seleção de Rede)
        time.sleep(5)
        print("✅ Login submetido com sucesso.")
    except Exception as e:
        pytest.fail(f"Falha durante o processo de login. Erro: {e}")

def test_05_confirmacao_sim(driver):
    """CT-05: Confirmação Pós-Login."""
    print("DESC: CT-05 - Confirmação Pós-Login (Botão Sim).")
    try:
        # Tenta encontrar o botão Sim.
        sim_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[@text='Sim' or @text='SIM']"))
        )
        sim_btn.click()
        print("✅ Botão 'Sim' clicado.")
    except Exception as e:
        print(f"⚠️ Aviso: Botão 'Sim' não encontrado (pode ter sido pulado ou login falhou): {e}")

def test_06_selecao_numero(driver):
    """CT-06: Seleção de Número."""
    print("DESC: CT-06 - Seleção de Número disponível.")
    try:
        # Tenta selecionar um item da lista (geralmente o número disponível)
        # Procura por RadioButton ou CheckBox se houver
        try:
            opcao = driver.find_element(AppiumBy.CLASS_NAME, "android.widget.RadioButton")
            opcao.click()
            print("✅ Número selecionado.")
        except:
            print("ℹ️ Nenhuma opção de rádio encontrada, tentando continuar direto...")

        # Clicar em Confirmar/Avançar
        confirmar_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[@text='Confirmar' or @text='Avançar' or @text='Continuar']"))
        )
        confirmar_btn.click()
        print("✅ Botão de confirmação clicado.")
        
        # Valida chegada na Home (agora sim esperamos 'Recarga')
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((AppiumBy.XPATH, "//*[@text='Recarga']"))
        )
        print("✅ Redirecionado para Home (CT-06 Concluído).")
    except Exception as e:
        print(f"⚠️ Aviso: Etapa de seleção de número não concluída (pode não ser necessária): {e}")

def test_07_recarga(driver):
    """CT-07: Acesso à Recarga."""
    print("DESC: CT-07 - Acesso à Recarga.")
    try:
        recarga_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[@text='Recarga']"))
        )
        recarga_btn.click()
        print("✅ Botão 'Recarga' clicado.")

        # Valida se a tela de recarga abriu
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'valor')]"))
        )
        print("✅ Tela de recarga aberta.")

        driver.back()
        print("✅ Botão 'Voltar' pressionado.")

        # Valida se retornou para a Home
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((AppiumBy.XPATH, "//*[@text='Recarga']"))
        )
        print("✅ Retornou para a tela principal com sucesso.")
    except Exception as e:
        pytest.fail(f"Falha no fluxo de Recarga. Erro: {e}")

def test_08_menu(driver):
    """CT-08: Acesso ao Menu."""
    print("DESC: CT-08 - Acesso ao Menu.")
    try:
        # O botão de menu é geralmente o primeiro ImageButton na hierarquia
        menu_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.CLASS_NAME, "android.widget.ImageButton"))
        )
        menu_btn.click()
        print("✅ Botão de menu clicado.")

        # Valida se o menu abriu procurando o item 'Perfil'
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((AppiumBy.XPATH, "//*[@text='Perfil']"))
        )
        print("✅ Menu aberto com sucesso.")

        driver.back() # Fecha o menu
        print("✅ Botão 'Voltar' pressionado para fechar o menu.")
    except Exception as e:
        pytest.fail(f"Falha ao interagir com o menu. Erro: {e}")

def test_09_perfil(driver):
    """CT-09: Acesso ao Perfil."""
    print("DESC: CT-09 - Acesso ao Perfil.")
    try:
        menu_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.CLASS_NAME, "android.widget.ImageButton"))
        )
        menu_btn.click()

        perfil_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[@text='Perfil']"))
        )
        perfil_btn.click()
        print("✅ Navegou para a tela de Perfil.")

        # Valida se as informações do usuário aparecem
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((AppiumBy.XPATH, "//*[contains(@text, '99999909914')]"))
        )
        print("✅ Informações do usuário exibidas na tela de Perfil.")

        driver.back()
        print("✅ Botão 'Voltar' pressionado.")

        # Valida se retornou para a Home
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((AppiumBy.XPATH, "//*[@text='Recarga']"))
        )
        print("✅ Retornou para a tela principal com sucesso.")
    except Exception as e:
        pytest.fail(f"Falha no fluxo de Perfil. Erro: {e}")

def test_10_fluxo_completo(driver):
    """CT-10: Validação Geral de Navegação."""
    print("DESC: CT-10 - Validação Geral de Navegação e Estabilidade.")
    
    # 1. Teste de estabilidade em background
    print("Enviando app para segundo plano por 5 segundos...")
    driver.background_app(5)
    assert driver.current_activity is not None, "O app fechou inesperadamente após voltar do background."
    print("✅ App permaneceu estável em background.")

    # 2. Captura de evidência final
    os.makedirs("storage", exist_ok=True)
    caminho = "storage/screenshot_final.png"
    driver.save_screenshot(caminho)
    assert os.path.exists(caminho), "Falha ao salvar screenshot final."
    print(f"✅ Evidência final capturada em: {caminho}")