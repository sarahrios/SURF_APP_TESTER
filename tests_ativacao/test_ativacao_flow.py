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
        browser.save_screenshot("storage/test_01_iniciar_ativacao.png")
        pytest.fail(f"Falha na página de ativação: {e}")

def test_02_inserir_cpf(browser):
    """ETAPA 2: Insere CPF e clica em Continuar."""
    print("DESC: ETAPA 2 - Inserir CPF.")
    try:
        # Tenta localizar o campo de CPF
        try:
            campo_cpf = WebDriverWait(browser, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//input[contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cpf') or contains(translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cpf') or contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cpf')]"))
            )
        except:
            # Fallback para o primeiro input de texto visível na tela
            campo_cpf = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='text' or @type='tel' or @type='number']"))
            )
        
        campo_cpf.clear()
        time.sleep(0.5)
        campo_cpf.send_keys("99999909914")
        print("✅ CPF inserido com sucesso.")

        os.makedirs("storage", exist_ok=True)
        browser.save_screenshot("storage/test_02_inserir_cpf.png")

        # Clicar em "Continuar"
        btn_continuar = WebDriverWait(browser, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'CONTINUAR') or contains(translate(@value, 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'CONTINUAR') or @type='submit']"))
        )
        btn_continuar.click()
        print("✅ Botão 'Continuar' clicado.")
        time.sleep(4) # Aguarda a próxima tela carregar
        
    except Exception as e:
        browser.save_screenshot("storage/test_02_inserir_cpf.png")
        pytest.fail(f"Falha ao inserir CPF: {e}")

def test_03_inserir_ddd(browser):
    """ETAPA 3: Insere DDD e clica em Continuar."""
    print("DESC: ETAPA 3 - Inserir DDD.")
    try:
        print("⏳ Aguardando transição para a tela de DDD...")
        time.sleep(3) # Pausa estendida para a animação da troca de tela (SPA)
        
        # Em formulários de múltiplas etapas, a tela antiga costuma ficar oculta. 
        # Vamos pegar apenas os campos visíveis e utilizar o último (que representa a tela atual).
        inputs = browser.find_elements(By.XPATH, "//input[not(@type='hidden') and not(@type='radio') and not(@type='checkbox')]")
        inputs_visiveis = [inp for inp in inputs if inp.is_displayed() and inp.is_enabled()]
        
        if not inputs_visiveis:
            raise Exception("Nenhum campo de texto visível para o DDD encontrado.")
            
        campo_ddd = inputs_visiveis[-1]
        
        # Força foco no campo (ajuda na validação de sites React/Vue)
        browser.execute_script("arguments[0].focus();", campo_ddd)
        browser.execute_script("arguments[0].click();", campo_ddd)
        time.sleep(0.5)

        campo_ddd.clear()
        time.sleep(0.5)
        campo_ddd.send_keys("11")
        print("✅ DDD 11 inserido com sucesso.")

        os.makedirs("storage", exist_ok=True)
        browser.save_screenshot("storage/test_03_inserir_ddd.png")

        # Clicar em "Continuar"
        print("⏳ Procurando botão de Continuar na tela do DDD...")
        time.sleep(1.5) # Espera validação do campo liberar o botão
        
        botoes = browser.find_elements(By.XPATH, "//button | //input[@type='submit' or @type='button'] | //a")
        
        sucesso_clique = False
        for btn in reversed(botoes):
            if btn.is_displayed() and btn.is_enabled():
                texto = (btn.text or btn.get_attribute("value") or "").upper()
                if "CONTINUAR" in texto or "AVANÇAR" in texto or "PRÓXIMO" in texto or btn.get_attribute("type") == "submit":
                    browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.5)
                    browser.execute_script("arguments[0].click();", btn)
                    sucesso_clique = True
                    print("✅ Botão da etapa de DDD clicado com sucesso!")
                    break
                
        if not sucesso_clique:
            raise Exception("Não foi possível encontrar um botão Continuar visível após preencher o DDD.")

        time.sleep(6) # Aguarda a próxima tela carregar (ICCID)

    except Exception as e:
        browser.save_screenshot("storage/test_03_inserir_ddd.png")
        pytest.fail(f"Falha ao inserir DDD: {e}")

def test_04_inserir_iccid_e_ativar(browser):
    """ETAPA 4: Insere ICCID e clica em Ativar agora."""
    print("DESC: ETAPA 4 - Inserir ICCID e Ativar.")
    iccid = os.getenv("TARGET_ICCID")
    if not iccid:
        pytest.skip("ICCID não fornecido na interface. Teste pulado.")

    try:
        print("⏳ Aguardando transição para a tela de ICCID...")
        time.sleep(3)
        
        inputs = browser.find_elements(By.XPATH, "//input[not(@type='hidden') and not(@type='radio') and not(@type='checkbox')]")
        inputs_visiveis = [inp for inp in inputs if inp.is_displayed() and inp.is_enabled()]
        
        if not inputs_visiveis:
            raise Exception("Nenhum campo de texto visível para o ICCID.")
            
        campo_iccid = inputs_visiveis[-1]
        browser.execute_script("arguments[0].focus();", campo_iccid)
        browser.execute_script("arguments[0].click();", campo_iccid)
        time.sleep(0.5)

        campo_iccid.clear()
        time.sleep(0.5)
        campo_iccid.send_keys(iccid)
        print(f"✅ ICCID '{iccid}' inserido com sucesso.")

        os.makedirs("storage", exist_ok=True)
        browser.save_screenshot("storage/test_04_inserir_iccid_antes.png")

        print("⏳ Procurando botão de Ativar...")
        time.sleep(1.5)
        
        botoes = browser.find_elements(By.XPATH, "//button | //input[@type='submit' or @type='button'] | //a")
        sucesso_clique = False
        for btn in reversed(botoes):
            if btn.is_displayed() and btn.is_enabled():
                texto = (btn.text or btn.get_attribute("value") or "").upper()
                if "ATIVAR" in texto or "CONFIRMAR" in texto or btn.get_attribute("type") == "submit":
                    browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.5)
                    browser.execute_script("arguments[0].click();", btn)
                    sucesso_clique = True
                    print("✅ Botão 'Ativar agora' clicado com sucesso.")
                    break

        if not sucesso_clique:
            print("⚠️ Botão de ativar não encontrado com os textos padrões, forçando o último botão visível...")
            visiveis = [b for b in botoes if b.is_displayed() and b.is_enabled()]
            if visiveis:
                browser.execute_script("arguments[0].click();", visiveis[-1])
        
        # Esperar a tela carregar o resultado da ativação (Tempo estendido por segurança)
        print("⏳ Aguardando processamento da ativação...")
        time.sleep(15)
        
        # Tirar o print final
        browser.save_screenshot("storage/test_04_inserir_iccid_e_ativar.png")
        print("✅ Processo de ativação concluído e tela final carregada.")

    except Exception as e:
        browser.save_screenshot("storage/test_04_inserir_iccid_e_ativar.png")
        pytest.fail(f"Falha ao inserir ICCID: {e}")