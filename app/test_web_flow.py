# Arquivo: tests_web/test_web_flow.py
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
    """
    Configura o navegador (Chrome) para os testes web.
    Roda em modo headless (sem interface gráfica).
    """
    url = os.getenv("TARGET_URL")
    msisdn = os.getenv("TARGET_MSISDN")
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
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        driver.get(url)
        print(f"✅ Navegador aberto com sucesso na URL: {url}")
        if msisdn:
            print(f"✅ MSISDN recebido para teste: {msisdn}")
    except Exception as e:
        pytest.fail(f"ERRO CRÍTICO: Não foi possível iniciar o Selenium/Chrome. Verifique se o webdriver está instalado e no PATH. Erro: {e}")

    yield driver

    # Finaliza o navegador após todos os testes
    if driver:
        driver.quit()

def test_01_titulo_da_pagina(browser):
    """ETAPA 1: Verifica se a página carrega e tem um título."""
    print("DESC: ETAPA 1 - Validação do Título da Página.")
    msisdn = os.getenv("TARGET_MSISDN")
    try:
        WebDriverWait(browser, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Verifica se não carregou uma página de erro padrão do Chrome
        if "chromewebdata" in browser.current_url or "chrome-error" in browser.page_source:
            raise Exception("A página não existe ou está fora do ar (Erro DNS/Conexão).")

        # Espera até que o título não seja vazio (útil para SPAs)
        WebDriverWait(browser, 15).until(lambda driver: driver.title != "")
        assert browser.title != "", "A página carregou, mas não possui um título."
        print(f"✅ Título encontrado: {browser.title}")
        if msisdn:
            print(f"⏳ Aguardando os próximos passos para interagir com o MSISDN: {msisdn}")
            
        os.makedirs("storage", exist_ok=True)
        
        # O nome do print DEVE ser igual ao nome da função de teste!
        browser.save_screenshot("storage/test_01_titulo_da_pagina.png")
    except Exception as e:
        os.makedirs("storage", exist_ok=True)
        browser.save_screenshot("storage/test_01_titulo_da_pagina_erro.png")
        pytest.fail(f"A página demorou muito para carregar ou não é válida. Erro: {e}")

def test_02_inserir_msisdn_e_ver_planos(browser):
    """ETAPA 2: Preenche o MSISDN e avança para os planos."""
    print("DESC: ETAPA 2 - Preenchimento do MSISDN e busca de planos.")
    msisdn = os.getenv("TARGET_MSISDN")
    
    if not msisdn:
        pytest.skip("MSISDN não fornecido. Teste pulado.")
        
    os.makedirs("storage", exist_ok=True)
    
    # 📸 Print inicial (Começo da etapa)
    browser.save_screenshot("storage/test_02_inserir_msisdn_inicio.png")
    
    try:
        # Tenta localizar o campo pelo tipo, id ou name comum
        try:
            campo_numero = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='tel' or contains(@name, 'msisdn') or contains(@id, 'numero') or contains(@id, 'telefone')]"))
            )
        except:
            # Fallback Inteligente: pega o primeiro input de texto vísivel na tela se o site não usar os nomes acima
            campo_numero = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='text' or @type='tel']"))
            )
        
        # Limpa o campo e digita o número
        campo_numero.clear()
        time.sleep(0.5)
        campo_numero.send_keys(msisdn)
        print(f"✅ MSISDN '{msisdn}' inserido com sucesso no campo.")
        
        # 📸 Print intermediário (Após preencher, antes de clicar)
        browser.save_screenshot("storage/test_02_inserir_msisdn_preenchido.png")
        
        # Localiza o botão "VER PLANOS" (Ignorando se está escrito em maiúsculo ou minúsculo no site)
        btn_xpath = "//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'VER PLANOS') or contains(translate(@value, 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'VER PLANOS')]"
        
        botao_planos = WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.XPATH, btn_xpath)))
        botao_planos.click()
        print("✅ Botão 'VER PLANOS' clicado com sucesso.")
        
        # Aguarda a próxima tela carregar (Transição)
        time.sleep(5)
        
        # 📸 Print do Fim (Este print irá automaticamente para o PDF pois tem o exato nome da função!)
        browser.save_screenshot("storage/test_02_inserir_msisdn_e_ver_planos.png")
        
    except Exception as e:
        # 📸 Print em caso de falha/erro nessa fase
        browser.save_screenshot("storage/test_02_inserir_msisdn_e_ver_planos_erro.png")
        pytest.fail(f"Falha ao inserir MSISDN ou clicar no botão VER PLANOS. O layout do site pode ser diferente do esperado: {e}")

def test_03_selecionar_plano_e_pix(browser):
    """ETAPA 3: Seleciona o plano e escolhe a forma de pagamento PIX."""
    print("DESC: ETAPA 3 - Seleção de Plano e Pagamento via PIX.")
    msisdn = os.getenv("TARGET_MSISDN")
    
    if not msisdn:
        pytest.skip("MSISDN não fornecido. Teste pulado.")
        
    os.makedirs("storage", exist_ok=True)
    
    # 📸 Print inicial (Logo após carregar a tela de planos)
    browser.save_screenshot("storage/test_03_selecionar_plano_inicio.png")
    
    try:
        # 1. Localiza e clica no botão "Selecionar plano"
        btn_selecionar_plano_xpath = "//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'SELECIONAR PLANO') or contains(translate(@value, 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'SELECIONAR PLANO')]"
        botao_selecionar = WebDriverWait(browser, 15).until(EC.element_to_be_clickable((By.XPATH, btn_selecionar_plano_xpath)))
        botao_selecionar.click()
        print("✅ Botão 'Selecionar plano' clicado com sucesso.")
        
        time.sleep(3) # Aguarda transição/animação da tela
        
        # 📸 Print intermediário (Após clicar em selecionar plano)
        browser.save_screenshot("storage/test_03_selecionar_plano_meio.png")
        
        # 2. Localiza e clica no botão "PIX"
        btn_pix_xpath = "//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'PIX') or contains(translate(@value, 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'PIX')]"
        botao_pix = WebDriverWait(browser, 15).until(EC.element_to_be_clickable((By.XPATH, btn_pix_xpath)))
        botao_pix.click()
        print("✅ Opção de pagamento 'PIX' selecionada com sucesso.")
        
        time.sleep(5) # Aguarda transição para tela do QRCode/Pix
        
        # 📸 Print do Fim (Este print irá automaticamente para o PDF com o nome exato da função)
        browser.save_screenshot("storage/test_03_selecionar_plano_e_pix.png")
        
    except Exception as e:
        # 📸 Print em caso de falha/erro nessa fase
        browser.save_screenshot("storage/test_03_selecionar_plano_e_pix_erro.png")
        pytest.fail(f"Falha ao selecionar plano ou escolher PIX. Verifique se os botões existem e estão visíveis na tela. Erro: {e}")