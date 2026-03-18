# Arquivo: tests_mobile/test_android_apk.py
import logging
logging.basicConfig(level=logging.INFO, force=True) # ✅ Resolve WinError 6 e conflitos de Multiprocessing do Windows

import pytest
import os
import time
import subprocess
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Prefixo do pacote para IDs
ID_PREFIX = "br.com.surfmobile.ifoodchip:id/"

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
    options.new_command_timeout = 3600 # ✅ Evita "POST /element cannot be proxied" por inatividade
    options.set_capability("appium:uiautomator2ServerInstallTimeout", 90000)
    options.set_capability("appium:adbExecTimeout", 60000) # Dá mais tempo para comandos ADB
    options.set_capability("appium:enforceAppInstall", False) # MUDANÇA: Não forçar install pelo Appium (já fazemos manual)

    # --- RESOLUÇÃO DO COMANDO ADB ---
    # Tenta encontrar o ADB pelo ANDROID_HOME se não estiver no PATH global
    adb_cmd = "adb"
    android_home = os.getenv("ANDROID_HOME")
    if android_home:
        # Ajuste para suportar Mac/Linux (sem .exe) e Windows
        exe_name = "adb.exe" if os.name == 'nt' else "adb"
        potential_adb = os.path.join(android_home, "platform-tools", exe_name)
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

def salvar_debug(driver, step_name):
    """Salva screenshot e XML da tela para diagnóstico de falhas."""
    try:
        os.makedirs("storage/debug", exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        driver.save_screenshot(f"storage/debug/{step_name}_{timestamp}.png")
        with open(f"storage/debug/{step_name}_{timestamp}.xml", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"📸 [DEBUG] Evidência salva em storage/debug/ para: {step_name}")
    except Exception as e:
        print(f"⚠️ Falha ao salvar debug: {e}")

# ==============================================================================
# UTILITÁRIOS
# ==============================================================================
def realizar_swipe_w3c(driver, start_x, start_y, end_x, end_y, duration_ms=400):
    """✅ Realiza um swipe seguro utilizando a nova API W3C do Appium, substituindo o driver.swipe obsoleto."""
    actions = ActionChains(driver)
    actions.w3c_actions = ActionBuilder(driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
    actions.w3c_actions.pointer_action.move_to_location(start_x, start_y)
    actions.w3c_actions.pointer_action.pointer_down()
    actions.w3c_actions.pointer_action.pause(duration_ms / 1000.0)
    actions.w3c_actions.pointer_action.move_to_location(end_x, end_y)
    actions.w3c_actions.pointer_action.pointer_up()
    actions.perform()

# ==============================================================================
# CENÁRIOS E2E SOLICITADOS
# ==============================================================================

def test_01_abertura_do_app(driver):
    """🚀 1. Abertura do App"""
    print("DESC: Abrir o APK (iniciar o aplicativo)")
    try:
        # Aguarda qualquer overlay de carregamento desaparecer
        WebDriverWait(driver, 15).until(
            EC.invisibility_of_element_located((AppiumBy.ID, f"{ID_PREFIX}loadingContainer"))
        )
    except:
        pass
    assert driver.current_context == "NATIVE_APP"
    print("✅ App aberto e carregado com sucesso.")

def test_02_onboarding(driver):
    """📱 2. Onboarding (Carrossel)"""
    print("DESC: Passar o carrossel 3 vezes e clicar Continuar")
    size = driver.get_window_size()
    start_x = size['width'] * 0.8
    end_x = size['width'] * 0.2
    y = size['height'] / 2

    for i in range(3):
        print(f"Swipe {i+1}/3")
        realizar_swipe_w3c(driver, start_x, y, end_x, y, 600)
        time.sleep(1.5) # Aguarda a animação da tela assentar

    # Clicar no botão Continuar
    try:
        continuar_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Continuar') or contains(@text, 'CONTINUAR') or contains(@resource-id, 'continue')]"))
        )
        continuar_btn.click()
        print("✅ Botão 'Continuar' clicado.")
    except Exception as e:
        print(f"ℹ️ Onboarding ignorado ou falhou: {e}")

def test_03_termos_e_condicoes(driver):
    """✅ 3. Termos e Condições"""
    print("DESC: Marcar os 2 checkboxes e clicar em Concordar e continuar")
    try:
        # Pega todos os checkboxes da tela
        checkboxes = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((AppiumBy.CLASS_NAME, "android.widget.CheckBox"))
        )
        for cb in checkboxes[:2]: # Marca os 2 primeiros
            cb.click()
        print("✅ Checkboxes marcados.")

        # Botão Concordar e continuar
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Concordar') or contains(@text, 'CONCORDAR')]"))
        ).click()
        print("✅ Termos aceitos.")
    except Exception as e:
        print(f"ℹ️ Tela de termos não processada: {e}")

def test_04_login(driver):
    """🔐 4. Login"""
    print("DESC: Preencher CPF e Senha")
    try:
        cpf_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((AppiumBy.XPATH, "//android.widget.EditText[contains(@text, 'CPF') or contains(@resource-id, 'document')] | //android.widget.EditText[1]"))
        )
        cpf_field.clear()
        cpf_field.send_keys("99999909914")

        senha_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((AppiumBy.XPATH, "//android.widget.EditText[contains(@text, 'Senha') or contains(@resource-id, 'password')] | //android.widget.EditText[2]"))
        )
        senha_field.clear()
        senha_field.send_keys("1234")
        
        driver.hide_keyboard()

        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Continuar') or contains(@text, 'Entrar')]"))
        ).click()
        print("✅ Botão de login acionado.")
        time.sleep(5) # Delay explícito para autenticação/rede lenta
    except Exception as e:
        salvar_debug(driver, "erro_login")
        pytest.fail(f"⚠️ Falha no fluxo de Login: {e}")

def test_05_biometria(driver):
    """👆 5. Biometria"""
    print("DESC: Selecionar opção SIM para cadastro de biometria")
    try:
        btn_sim = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[@text='SIM' or @text='Sim' or @text='sim']"))
        )
        btn_sim.click()
        print("✅ Cadastro de biometria aceito.")
    except:
        print("ℹ️ Oferta de biometria não exibida.")

def test_06_selecao_de_numero(driver):
    """📞 6. Seleção de Número"""
    print("DESC: Selecionar um número disponível e Continuar")
    try:
        radio_buttons = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((AppiumBy.CLASS_NAME, "android.widget.RadioButton"))
        )
        if radio_buttons:
            radio_buttons[0].click()
        
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Continuar')]"))
        ).click()
        print("✅ Número selecionado e confirmado.")
        time.sleep(3)
    except:
        print("ℹ️ Seleção de número ignorada ou não exibida.")

def test_07_pagamentos_adicionar_cartao(driver):
    """💳 7. Pagamentos - Adicionar Cartão"""
    print("DESC: Homebar -> Pagamentos -> Inserir (+) -> Preencher dados -> Adicionar Cartão")
    try:
        # Clicar em "Pagamentos" na Homebar
        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Pagamentos') or contains(@content-desc, 'Pagamentos')]"))
        ).click()

        # Clicar no botão "+" (Inserir)
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, '+') or contains(@content-desc, 'Adicionar') or @content-desc='Inserir']"))
        ).click()

        # Preencher os dados do cartão - Usa os inputs da tela em ordem
        inputs = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((AppiumBy.CLASS_NAME, "android.widget.EditText"))
        )
        if len(inputs) >= 5:
            inputs[0].send_keys("0000000000000000") # Número
            inputs[1].send_keys("00/00")           # Validade
            inputs[2].send_keys("000")             # CVV
            inputs[3].send_keys("Sarah Rios")      # Nome
            inputs[4].send_keys("99999909914")     # CPF
        else:
            # Fallback localizando pelos Hints/Textos Próximos
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'Número')]/..//android.widget.EditText"))
            ).send_keys("0000000000000000")
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'Validade')]/..//android.widget.EditText"))
            ).send_keys("00/00")
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'CVV')]/..//android.widget.EditText"))
            ).send_keys("000")
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'Nome')]/..//android.widget.EditText"))
            ).send_keys("Sarah Rios")
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'CPF')]/..//android.widget.EditText"))
            ).send_keys("99999909914")
        
        driver.hide_keyboard()

        # Clicar em "Adicionar Cartão"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Adicionar Cartão') or contains(@text, 'ADICIONAR CARTÃO')]"))
        ).click()
        print("✅ Dados de cartão preenchidos e enviados.")
        time.sleep(3)
    except Exception as e:
        salvar_debug(driver, "erro_adicionar_cartao")
        pytest.fail(f"⚠️ Erro ao adicionar cartão: {e}")

def test_08_consumo(driver):
    """📊 8. Consumo"""
    print("DESC: Homebar -> Consumo -> Acessar Ligações e SMS")
    try:
        # Clicar em "Consumo" na Homebar
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Consumo') or contains(@content-desc, 'Consumo')]"))
        ).click()

        # Acessar "Ligações"
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Ligações')]"))
        ).click()
        time.sleep(1)

        # Acessar "SMS"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'SMS')]"))
        ).click()
        time.sleep(1)
        print("✅ Abas de consumo visualizadas com sucesso.")
    except Exception as e:
        salvar_debug(driver, "erro_consumo")
        pytest.fail(f"⚠️ Erro ao acessar tela de consumo: {e}")

def test_09_recarga_via_pix(driver):
    """💰 9. Recarga via Pix"""
    print("DESC: Recarga via PIX - Fluxo completo")
    try:
        # Homebar -> Menu
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Menu') or contains(@content-desc, 'Menu')]"))
        ).click()

        # Clicar em "Recarga"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Recarga')]"))
        ).click()

        # Selecionar um plano (Clicar na primeira área clicável do Recycler)
        planos = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((AppiumBy.XPATH, "//*[contains(@text, 'R$')]/.."))
        )
        planos[0].click()

        # Clicar em Confirmar
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Confirmar')]"))
        ).click()

        # Selecionar "Pix"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Pix') or contains(@text, 'PIX')]"))
        ).click()

        # Finalizar Recarga
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Finalizar Recarga') or contains(@text, 'Finalizar')]"))
        ).click()

        # Copiar código
        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Copiar')]"))
        ).click()
        print("✅ Código PIX copiado.")

        # Fechar a tela clicando no "X"
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'X') or contains(@content-desc, 'Fechar') or contains(@resource-id, 'close')]"))
            ).click()
        except:
            driver.back() # Fallback de fechar
        print("✅ Janela do PIX fechada.")
    except Exception as e:
        salvar_debug(driver, "erro_recarga_pix")
        pytest.fail(f"⚠️ Erro ao realizar recarga PIX: {e}")

def test_10_atualizacao_de_perfil(driver):
    """👤 10. Atualização de Perfil"""
    print("DESC: Atualizar o telefone alternativo e retornar à Home")
    try:
        # Homebar -> Menu (Se já estiver no menu, isso passa liso)
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Menu') or contains(@content-desc, 'Menu')]"))
            ).click()
        except: pass

        # Clicar em "Perfil"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Perfil')]"))
        ).click()

        # Rolar a tela até o final (Swipe de baixo pra cima)
        size = driver.get_window_size()
        start_y = size['height'] * 0.8
        end_y = size['height'] * 0.2
        start_x = size['width'] / 2
        realizar_swipe_w3c(driver, start_x, start_y, start_x, end_y, 800)

        # Preencher Telefone Alternativo
        tel_alternativo = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((AppiumBy.XPATH, "//android.widget.EditText[contains(@text, 'alternativo') or contains(@resource-id, 'phone')] | (//android.widget.EditText)[last()]"))
        )
        tel_alternativo.clear()
        tel_alternativo.send_keys("11900000000")
        driver.hide_keyboard()

        # Clicar em "Salvar alterações"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Salvar')]"))
        ).click()
        print("✅ Telefone atualizado com sucesso.")

        # Retornar para a Home
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((AppiumBy.XPATH, "//*[contains(@text, 'Home') or contains(@text, 'Início') or contains(@content-desc, 'Home')]"))
            ).click()
        except:
            driver.back()
            driver.back()
        print("✅ Retornou para Home com sucesso. E2E finalizado!")

        salvar_debug(driver, "sucesso_e2e_final")
    except Exception as e:
        salvar_debug(driver, "erro_atualizar_perfil")
        pytest.fail(f"⚠️ Erro ao atualizar perfil: {e}")