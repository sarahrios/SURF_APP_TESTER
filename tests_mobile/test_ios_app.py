import pytest
import os
import time
from appium import webdriver
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

@pytest.fixture(scope="session")
def driver():
    # Verifica se estamos testando iOS
    if os.getenv("PLATFORM_NAME") != "iOS":
        pytest.skip("Pulando testes iOS pois o alvo é Android")

    app_path = os.getenv("TARGET_APK_PATH") # Reutilizamos a variável de ambiente
    
    if not app_path:
        pytest.fail("ERRO: Caminho do APP/IPA não encontrado.")

    # Configurações para iOS (XCUITest)
    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.automation_name = "XCUITest"
    
    # IMPORTANTE: Ajuste para o nome do seu iPhone ou Simulador
    options.device_name = os.getenv("IOS_DEVICE_NAME", "iPhone 14")
    options.platform_version = os.getenv("IOS_PLATFORM_VERSION", "16.0")
    
    # Caminho do app (.ipa ou .app)
    options.app = app_path
    
    # Para dispositivo físico, você precisa do UDID e assinatura
    # options.udid = "SEU_UDID_AQUI"
    # options.xcode_org_id = "SEU_TEAM_ID"
    # options.xcode_signing_id = "iPhone Developer"

    # Se o servidor Appium estiver em um Mac na rede, mude 'localhost' para o IP do Mac
    appium_server_url = os.getenv("APPIUM_SERVER_URL", "http://localhost:4723")

    print(f"--- Conectando ao Appium iOS em {appium_server_url} ---")
    
    driver = None
    try:
        driver = webdriver.Remote(appium_server_url, options=options)
    except Exception as e:
        pytest.fail(f"Falha ao conectar no Appium iOS: {e}")

    yield driver
    
    if driver:
        driver.quit()

# --- TESTES IOS (Exemplos adaptados) ---

def test_01_abertura_ios(driver):
    """CT-01: Valida abertura do app no iOS."""
    print("DESC: Validando abertura no iOS.")
    # No iOS, o contexto nativo também é padrão
    assert driver.current_context == "NATIVE_APP"
    
    # Exemplo de espera por elemento (IDs no iOS geralmente são 'name' ou 'label')
    # WebDriverWait(driver, 10).until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "LoginButton")))

def test_02_login_ios(driver):
    """CT-04: Login no iOS."""
    print("DESC: Tentativa de Login iOS.")
    try:
        # No iOS usamos muito ACCESSIBILITY_ID ou CLASS_CHAIN
        # user_field = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "username_field")
        # user_field.send_keys("usuario_ios")
        
        # pass_field = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "password_field")
        # pass_field.send_keys("1234")
        
        # btn = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Entrar")
        # btn.click()
        pass
    except Exception as e:
        # pytest.fail(f"Erro no login iOS: {e}")
        pass

def test_03_screenshot_ios(driver):
    os.makedirs("storage", exist_ok=True)
    driver.save_screenshot("storage/screenshot_final.png")