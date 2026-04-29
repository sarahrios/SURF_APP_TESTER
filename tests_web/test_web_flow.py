import pytest
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

@pytest.fixture(scope="session")
def browser():
    url = os.getenv("TARGET_URL")
    if not url:
        pytest.fail("ERRO: Nenhuma URL de destino foi fornecida.")

    chrome_options = Options()
    chrome_options.add_argument("--headless") # Roda silenciosamente
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        print(f"✅ Navegador aberto com sucesso na URL: {url}")
    except Exception as e:
        pytest.fail(f"ERRO CRÍTICO: Falha ao iniciar Selenium/Chrome. {e}")

    yield driver

    if driver:
        driver.quit()

def test_01_titulo_da_pagina(browser):
    """ETAPA 1: Verifica se a página carrega e tem um título."""
    print("DESC: ETAPA 1 - Validação do Título da Página.")
    try:
        # Espera o corpo da página carregar por até 15 segundos
        WebDriverWait(browser, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        assert browser.title != "", "A página carregou, mas não possui um título."
        print(f"✅ Título encontrado: {browser.title}")
        os.makedirs("storage", exist_ok=True)
        browser.save_screenshot("storage/test_web_01_titulo.png")
    except Exception as e:
        os.makedirs("storage", exist_ok=True)
        browser.save_screenshot("storage/test_web_01_titulo_erro.png")
        pytest.fail(f"Falha na página: {e}")