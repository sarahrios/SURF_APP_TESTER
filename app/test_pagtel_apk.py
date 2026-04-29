import pytest
import os
import time
from appium import webdriver
from appium.options.android import UiAutomator2Options

@pytest.fixture(scope="session")
def driver():
    apk_path = os.getenv("TARGET_APK_PATH")
    if not apk_path:
        pytest.fail("ERRO: Caminho do APK não encontrado.")

    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.device_name = "Android Device" 
    options.app = apk_path
    options.auto_grant_permissions = True
    
    # Tempos limites básicos
    options.new_command_timeout = 600

    print(f"--- Conectando ao Appium para o app PAGTEL: {apk_path} ---")
    try:
        driver = webdriver.Remote("http://localhost:4723", options=options)
        print("✅ Conexão estabelecida com sucesso!")
    except Exception as e:
        pytest.fail(f"FALHA DE CONEXÃO: {e}")

    yield driver
    
    if driver:
        driver.quit()

def test_01_abertura_pagtel(driver):
    """ETAPA 1: Abertura do App Pagtel"""
    print("DESC: ETAPA 1 - Abertura inicial do Pagtel.")
    try:
        # Aguarda 5 segundos só para o app respirar e tira um print
        time.sleep(5)
        print("✅ App Pagtel aberto com sucesso na tela inicial.")
        os.makedirs("storage", exist_ok=True)
        driver.save_screenshot("storage/test_pagtel_01_abertura.png")
    except Exception as e:
        driver.save_screenshot("storage/test_pagtel_01_abertura_erro.png")
        pytest.fail(f"Falha ao abrir Pagtel: {e}")

def test_02_fluxo_a_definir():
    """ETAPA 2: Testes customizados (A DEFINIR)"""
    print("DESC: ETAPA 2 - Fluxo customizado (Em construção).")
    # Você pode adicionar seus novos passos aqui futuramente!
    assert True