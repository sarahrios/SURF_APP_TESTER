# Arquivo: tests_web/test_web_flow.py
import pytest
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

@pytest.fixture(scope="session")
def browser():
    """
    Configura o navegador (Chrome) para os testes web.
    Roda em modo headless (sem interface gráfica).
    """
    url = os.getenv("TARGET_URL")
    if not url:
        pytest.fail("ERRO: Nenhuma URL de destino foi fornecida. Insira a URL na plataforma.")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = None
    try:
        # Assume que o chromedriver está no PATH do sistema.
        # Para CI/CD, ele precisa ser instalado no ambiente.
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        print(f"✅ Navegador aberto com sucesso na URL: {url}")
    except Exception as e:
        pytest.fail(f"ERRO CRÍTICO: Não foi possível iniciar o Selenium/Chrome. Verifique se o webdriver está instalado e no PATH. Erro: {e}")

    yield driver

    # Finaliza o navegador após todos os testes
    if driver:
        driver.quit()

def test_01_titulo_da_pagina(browser):
    """ETAPA 1: Verifica se a página carrega e tem um título."""
    print("DESC: ETAPA 1 - Validação do Título da Página.")
    try:
        WebDriverWait(browser, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        assert browser.title != "", "A página carregou, mas não possui um título."
        print(f"✅ Título encontrado: {browser.title}")
        browser.save_screenshot("storage/test_web_01_titulo.png")
    except Exception as e:
        browser.save_screenshot("storage/test_web_01_titulo_erro.png")
        pytest.fail(f"A página demorou muito para carregar ou não é válida. Erro: {e}")