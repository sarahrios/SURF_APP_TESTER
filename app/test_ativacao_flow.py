import pytest
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

@pytest.fixture(scope="session")
def browser():
    url = os.getenv("TARGET_URL")
    iccid = os.getenv("TARGET_ICCID")
    
    if not url:
        pytest.fail("ERRO: Nenhuma URL de destino foi fornecida.")
    if not iccid:
        pytest.fail("ERRO: Nenhum ICCID foi fornecido para a ativação.")

    chrome_options = Options()
    chrome_options.add_argument("--headless") # Roda silenciosamente
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = None
    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        driver.get(url)
        print(f"✅ Navegador aberto com sucesso na URL: {url}")
        print(f"✅ ICCID recebido para teste: {iccid}")
    except Exception as e:
        pytest.fail(f"ERRO CRÍTICO: Falha ao iniciar Selenium/Chrome. {e}")

    yield driver

    if driver:
        driver.quit()

def test_01_iniciar_ativacao(browser):
    """ETAPA 1: Carrega o site e prepara o ICCID."""
    print("DESC: ETAPA 1 - Inicialização do site de Ativação.")
    iccid = os.getenv("TARGET_ICCID") # AQUI ESTÁ O SEU ICCID COPIADO!
    try:
        time.sleep(3) # Aguarda carregamento inicial
        
        # Verifica se não carregou uma página de erro padrão do Chrome
        if "chromewebdata" in browser.current_url or "chrome-error" in browser.page_source:
            raise Exception("A página não existe ou está fora do ar (Erro DNS/Conexão).")

        # Aguarda a renderização do título da página
        WebDriverWait(browser, 15).until(lambda driver: driver.title != "")
        assert browser.title != "", "A página carregou, mas não possui um título."
        print(f"✅ Site de ativação carregado: {browser.title}")
        print(f"⏳ Aguardando os seus próximos passos para digitar o ICCID: {iccid}")
        
        os.makedirs("storage", exist_ok=True)
        
        # O nome do print DEVE ser igual ao nome da função de teste!
        browser.save_screenshot("storage/test_01_iniciar_ativacao.png")
    except Exception as e:
        os.makedirs("storage", exist_ok=True)
        browser.save_screenshot("storage/test_01_iniciar_ativacao_erro.png")
        pytest.fail(f"Falha na página de ativação: {e}")