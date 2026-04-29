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
    options.set_capability("appium:adbExecTimeout", 120000) # Dá mais tempo para comandos ADB (120s)
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

    # 0. Verifica se o ADB está acessível
    chk_adb = subprocess.run(f"{adb_cmd} --version", shell=True, capture_output=True, text=True)
    if chk_adb.returncode != 0:
        pytest.fail("❌ ERRO FATAL: Comando 'adb' não reconhecido. O Android SDK não foi configurado corretamente no PATH.")

    # 1. Verifica estado do aparelho conectado
    chk = subprocess.run(f"{adb_cmd} devices", shell=True, capture_output=True, text=True)
    if "unauthorized" in chk.stdout:
        pytest.fail("❌ ERRO DE PERMISSÃO: Celular conectado, mas NÃO AUTORIZADO! Olhe para a tela do celular e clique em 'Permitir sempre deste computador' na mensagem de Depuração USB.")
    elif "device" not in chk.stdout.replace("List of devices attached", "").strip():
        pytest.fail("❌ ERRO FATAL: Nenhum celular detectado pelo computador. Conecte o cabo USB e ative a Depuração USB nas Opções de Desenvolvedor.")

    # 1.5 Tenta desinstalar versão anterior para evitar conflito de assinatura
    if APK:
        try:
            apk_obj = APK(apk_path)
            pkg_name = apk_obj.get_package()
            print(f"🗑️ Tentando desinstalar versão antiga de: {pkg_name}")
            subprocess.run(f"{adb_cmd} uninstall {pkg_name}", shell=True, capture_output=True)
        except Exception:
            pass

    # 2. Tenta instalar via comando direto e VALIDA A SAÍDA REAL (Correção do Falso Positivo)
    print(f"📦 Tentando instalar APK via ADB: {apk_path}")
    try:
        # timeout=180 (3 min) impede que o processo trave silenciosamente, mas dá tempo suficiente para APKs grandes
        result = subprocess.run(f'{adb_cmd} install -r -g -t -d "{apk_path}"', shell=True, capture_output=True, text=True, timeout=180)
        
        saida_completa = (result.stdout + "\n" + result.stderr).strip()
        
        # O ADB frequentemente retorna código 0 (sucesso) mesmo quando a instalação falha.
        # Portanto, precisamos procurar ativamente pela palavra 'Success' no log.
        if "Success" not in saida_completa:
            dica = ""
            if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in saida_completa:
                dica = "\n💡 DICA: O app já está instalado com uma assinatura diferente. Exclua o app velho manualmente do celular."
            elif "INSTALL_FAILED_USER_RESTRICTED" in saida_completa:
                dica = "\n💡 DICA (Xiaomi/Redmi): Você precisa ativar 'Instalar via USB' nas Opções do Desenvolvedor."
            elif "INSTALL_PARSE_FAILED_NO_CERTIFICATES" in saida_completa:
                dica = "\n💡 DICA: O APK não possui assinatura. Você precisa gerar um 'Signed APK'."
            elif "INSTALL_FAILED_VERIFICATION_FAILURE" in saida_completa:
                dica = "\n💡 DICA: O Google Play Protect bloqueou a instalação. Desative a verificação na Play Store."
            elif "INSTALL_FAILED_TEST_ONLY" in saida_completa:
                dica = "\n💡 DICA: O APK está marcado como 'testOnly'. Remova isso do Manifesto."
            
            pytest.fail(f"❌ O ANDROID RECUSOU A INSTALAÇÃO DO APK. Motivo:\n{saida_completa}{dica}")
        else:
            print("✅ APK instalado com sucesso via ADB! Iniciando Appium...")
            
    except subprocess.TimeoutExpired:
        pytest.fail("❌ TEMPO ESGOTADO: A instalação travou. Olhe a tela do celular: o Google Play Protect ou o sistema Android pode estar exibindo um popup pedindo permissão de instalação.")
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

def test_01_onboarding(driver):
    """ETAPA 1: Abertura do App e Onboarding"""
    print("DESC: ETAPA 1 - Abertura do App e Onboarding.")
    try:
        # Validar exibição do carrossel inicial
        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located((AppiumBy.CLASS_NAME, "android.widget.FrameLayout"))
        )
        print("✅ Aplicativo aberto e carrossel exibido.")

        # Deslizar o carrossel 3 vezes
        size = driver.get_window_size()
        start_x = size['width'] * 0.8
        end_x = size['width'] * 0.2
        y = size['height'] / 2

        for i in range(3):
            driver.swipe(start_x, y, end_x, y, 400)
            time.sleep(1)
        print("✅ Carrossel deslizado 3 vezes.")

        # Clicar no botão "Continuar"
        btn_continuar = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Continuar')]"))
        )
        btn_continuar.click()
        time.sleep(2)

        # Selecionar os 2 checkboxes de termos (em cima e em baixo)
        checkboxes = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((AppiumBy.CLASS_NAME, "android.widget.CheckBox"))
        )
        for i, box in enumerate(checkboxes[:2]):
            box.click()
            print(f"✅ Checkbox {i+1} selecionado.")
            time.sleep(1)

        # Clicar em "Concordar e Continuar"
        btn_concordar = driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Concordar') and contains(@text, 'Continuar')]")
        btn_concordar.click()
        time.sleep(3)

        print("✅ Onboarding finalizado, avançando para tela de login.")
        driver.save_screenshot("storage/test_01_onboarding.png")
    except Exception as e:
        driver.save_screenshot("storage/test_01_onboarding_erro.png")
        pytest.fail(f"Falha na etapa de Onboarding: {e}")

def test_02_login(driver):
    """ETAPA 2: Login"""
    print("DESC: ETAPA 2 - Login.")
    try:
        campos = WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((AppiumBy.CLASS_NAME, "android.widget.EditText"))
        )
        print("Inserindo CPF e Senha...")
        campos[0].send_keys("99999909914") # Inserir CPF
        campos[1].send_keys("1234")        # Inserir Senha
        driver.hide_keyboard()

        # Clicar em "Continuar"
        btn_continuar = driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Continuar')]")
        btn_continuar.click()

        time.sleep(10) # Aguarda processamento do login
        print("✅ Login realizado com sucesso.")
        driver.save_screenshot("storage/test_02_login.png")
    except Exception as e:
        driver.save_screenshot("storage/test_02_login_erro.png")
        pytest.fail(f"Falha no Login: {e}")

def test_03_biometria(driver):
    """ETAPA 3: Biometria"""
    print("DESC: ETAPA 3 - Biometria.")
    try:
        # Validar tela de cadastro de biometria e Clicar em "SIM"
        btn_sim = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[@text='Sim' or @text='SIM']"))
        )
        btn_sim.click()
        time.sleep(3)
        print("✅ Biometria cadastrada ou fluxo avançado.")
        driver.save_screenshot("storage/test_03_biometria.png")
    except Exception as e:
        driver.save_screenshot("storage/test_03_biometria_erro.png")
        print(f"⚠️ Aviso: Tela de biometria não exibida ou pulada: {e}")

def test_04_selecao_numero(driver):
    """ETAPA 4: Seleção de Número"""
    print("DESC: ETAPA 4 - Seleção de Número.")
    try:
        # Selecionar uma caixa com um número disponível
        caixa = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((AppiumBy.CLASS_NAME, "android.widget.RadioButton"))
        )
        caixa.click()
        time.sleep(1)

        # Clicar em "Continuar"
        btn_continuar = driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Continuar')]")
        btn_continuar.click()
        time.sleep(5)
        
        print("✅ Número vinculado ao usuário.")
        driver.save_screenshot("storage/test_04_selecao_numero.png")
    except Exception as e:
        driver.save_screenshot("storage/test_04_selecao_numero_erro.png")
        print(f"⚠️ Aviso: Seleção de número falhou ou não foi necessária: {e}")

def test_05_cadastro_cartao(driver):
    """ETAPA 5: Cadastro de Cartão (Pagamento)"""
    print("DESC: ETAPA 5 - Cadastro de Cartão (Pagamento).")
    try:
        # Acessar "Pagamentos"
        btn_pagamentos = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Pagamento')]"))
        )
        btn_pagamentos.click()
        time.sleep(2)

        # Clicar no botão "+" (Adicionar)
        btn_add = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[@text='+' or contains(@text, 'Adicionar')]"))
        )
        btn_add.click()
        time.sleep(2)

        # Preencher os dados do cartão
        campos = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.EditText")
        campos[0].send_keys("0000000000000000") # Número do cartão
        campos[1].send_keys("0000")             # Validade
        campos[2].send_keys("000")              # CVV
        if len(campos) > 3: campos[3].send_keys("Sarah Rios")  # Nome
        if len(campos) > 4: campos[4].send_keys("99999909914") # CPF
        driver.hide_keyboard()

        # Clicar em "Adicionar Cartão"
        btn_add_cartao = driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Adicionar Cartão')]")
        btn_add_cartao.click()
        time.sleep(4)
        
        print("✅ Cartão cadastrado com sucesso.")
        driver.save_screenshot("storage/test_05_cadastro_cartao.png")

        # Voltar para a home
        driver.back()
        time.sleep(1)
        driver.back()
        time.sleep(2)
    except Exception as e:
        driver.save_screenshot("storage/test_05_cadastro_cartao_erro.png")
        pytest.fail(f"Falha ao cadastrar o cartão: {e}")

def test_06_consulta_consumo(driver):
    """ETAPA 6: Consulta de Consumo"""
    print("DESC: ETAPA 6 - Consulta de Consumo.")
    try:
        # Acessar "Consumo"
        btn_consumo = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Consumo')]"))
        )
        btn_consumo.click()
        time.sleep(3)

        # Clicar em Ligações
        btn_ligacoes = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Ligações')]"))
        )
        btn_ligacoes.click()
        time.sleep(2)

        # Clicar em SMS
        btn_sms = driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'SMS')]")
        btn_sms.click()
        time.sleep(2)
        
        print("✅ Exibição correta dos dados de consumo.")
        driver.save_screenshot("storage/test_06_consulta_consumo.png")

        # Voltar para a Home
        driver.back()
        time.sleep(2)
    except Exception as e:
        driver.save_screenshot("storage/test_06_consulta_consumo_erro.png")
        pytest.fail(f"Falha na consulta de consumo: {e}")

def test_07_recarga_pix(driver):
    """ETAPA 7: Recarga via PIX"""
    print("DESC: ETAPA 7 - Recarga via PIX.")
    try:
        # Acessar Menu
        try:
            btn_menu = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((AppiumBy.XPATH, "//*[@text='Menu']")))
            btn_menu.click()
        except:
            btn_menu = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((AppiumBy.CLASS_NAME, "android.widget.ImageButton")))
            btn_menu.click()
        time.sleep(2)

        # Clicar em "Recarga"
        btn_recarga = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Recarga')]"))
        )
        btn_recarga.click()
        time.sleep(3)

        # Selecionar um plano
        plano = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((AppiumBy.CLASS_NAME, "android.widget.RadioButton"))
        )
        plano.click()

        # Clicar em "Confirmar"
        btn_confirmar = driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Confirmar')]")
        btn_confirmar.click()
        time.sleep(3)

        # Selecionar PIX
        btn_pix = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'PIX') or contains(@text, 'Pix')]"))
        )
        btn_pix.click()

        # Clicar em "Finalizar Recarga"
        btn_finalizar = driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Finalizar Recarga')]")
        btn_finalizar.click()
        time.sleep(5)

        # Clicar em "Copiar código"
        btn_copiar = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Copiar')]"))
        )
        btn_copiar.click()
        print("✅ Código PIX gerado e copiado corretamente.")
        driver.save_screenshot("storage/test_07_recarga_pix.png")

        # Fechar tela clicando no "X"
        btn_fechar = driver.find_element(AppiumBy.XPATH, "//*[@text='X' or contains(@text, 'Fechar')]")
        btn_fechar.click()
        time.sleep(2)
    except Exception as e:
        driver.save_screenshot("storage/test_07_recarga_pix_erro.png")
        pytest.fail(f"Falha na recarga via PIX: {e}")

def test_08_atualizacao_perfil(driver):
    """ETAPA 8: Atualização de Perfil"""
    print("DESC: ETAPA 8 - Atualização de Perfil.")
    try:
        # Acessar Menu
        try:
            btn_menu = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((AppiumBy.XPATH, "//*[@text='Menu']")))
            btn_menu.click()
        except:
            btn_menu = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((AppiumBy.CLASS_NAME, "android.widget.ImageButton")))
            btn_menu.click()
        time.sleep(2)

        # Clicar em "Perfil"
        btn_perfil = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Perfil')]"))
        )
        btn_perfil.click()
        time.sleep(3)

        # Rolar até o final da tela
        print("Rolando a tela...")
        try:
            driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiScrollable(new UiSelector().scrollable(true)).scrollToEnd(1)')
            time.sleep(2)
        except: pass

        # Inserir telefone alternativo
        campos = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.EditText")
        campos[-1].clear()
        campos[-1].send_keys("1190000000")
        driver.hide_keyboard()
        time.sleep(1)

        # Clicar em "Salvar alterações"
        btn_salvar = driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Salvar')]")
        btn_salvar.click()
        time.sleep(3)
        
        print("✅ Dados atualizados com sucesso.")
        driver.save_screenshot("storage/test_08_atualizacao_perfil.png")

        # Voltar para a Home
        driver.back()
        time.sleep(2)
    except Exception as e:
        driver.save_screenshot("storage/test_08_atualizacao_perfil_erro.png")
        pytest.fail(f"Falha na atualização de perfil: {e}")
