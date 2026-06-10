"""
Web Signal Scraper - AlgoritmoDeTrading.com
Automatiza el login y monitorea señales en tiempo real desde la web.
"""

import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from typing import Optional, Dict

class WebSignalScraper:
    def __init__(self, user_name: str, user_id: str):
        self.user_name = user_name
        self.user_id = user_id
        self.driver = None
        self.is_running = False
        
        # Configuración de Chrome (Optimizada para Docker/Linux)
        self.options = Options()
        self.options.add_argument("--headless=new") # Critico para servidores sin pantalla
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--window-size=1920,1080")
        self.options.add_argument("--disable-extensions")
        self.options.add_argument("--disable-infobars")
        
        # Anti-detección básica
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)

    def start(self):
        """Inicia el navegador y hace login"""
        try:
            # Estrategia de Selección de Driver (Docker vs Local)
            system_driver = "/usr/bin/chromedriver"
            if os.path.exists(system_driver):
                print(f"✅ Usando driver del sistema: {system_driver}")
                service = Service(executable_path=system_driver)
            else:
                print("⚒️ Driver del sistema no encontrado, usando webdriver-manager...")
                from webdriver_manager.chrome import ChromeDriverManager
                driver_path = ChromeDriverManager().install()
                service = Service(driver_path)

            self.driver = webdriver.Chrome(service=service, options=self.options)
            
            # Navegar a home
            print("🔗 Navegando a https://algoritmodetrading.com/ ...")
            self.driver.get("https://algoritmodetrading.com/")
            time.sleep(5)  # Esperar carga
            
            # Intentar Login
            if self._perform_login():
                self.is_running = True
                print("✅ Login exitoso (aparente)")
                # Ir a la página de señales por si acaso no redirigió
                if "algoritmo.html" not in self.driver.current_url:
                    self.driver.get("https://algoritmodetrading.com/algoritmo.html")
                    time.sleep(5)
            else:
                print("❌ Falló el login automático")
                self.stop()
                
        except Exception as e:
            print(f"❌ Error iniciando WebDriver: {e}")
            self.stop()

    def _perform_login(self) -> bool:
        """Intenta llenar el formulario de login"""
        try:
            # Buscar campos de texto
            # Estrategia: Buscar inputs de tipo text/number y llenarlos
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            
            filled_name = False
            filled_id = False
            
            print(f"🔍 Encontrados {len(inputs)} campos de entrada")
            
            for inp in inputs:
                inp_type = inp.get_attribute("type")
                inp_name = inp.get_attribute("name") or ""
                inp_id = inp.get_attribute("id") or ""
                inp_placeholder = inp.get_attribute("placeholder") or ""
                
                # Debug info
                # print(f"   Input: type={inp_type} name={inp_name} id={inp_id} ph={inp_placeholder}")
                
                if inp_type in ["hidden", "submit", "button", "checkbox"]:
                    continue
                
                # Heurística para user ID
                if any(x in (inp_name + inp_id + inp_placeholder).lower() for x in ["id", "iq", "cuenta", "user", "numero"]):
                    if not filled_id:
                        print(f"   ✍️ Llenando ID en campo '{inp_name or inp_id}'")
                        inp.clear()
                        inp.send_keys(self.user_id)
                        filled_id = True
                        continue

                # Heurística para Nombre
                if any(x in (inp_name + inp_id + inp_placeholder).lower() for x in ["name", "nombre", "nam", "usuario"]):
                    if not filled_name:
                        print(f"   ✍️ Llenando Nombre en campo '{inp_name or inp_id}'")
                        inp.clear()
                        inp.send_keys(self.user_name)
                        filled_name = True
                        continue
            
            # Buscar botón de submit
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            submit_btn = None
            
            # Priorizar botón tipo submit
            for btn in buttons:
                if btn.get_attribute("type") == "submit":
                    submit_btn = btn
                    break
            
            # Si no, buscar por texto
            if not submit_btn:
                for btn in buttons:
                    if any(x in btn.text.lower() for x in ["entrar", "iniciar", "login", "acceder"]):
                        submit_btn = btn
                        break
            
            if submit_btn:
                print(f"👆 Clickeando botón: {submit_btn.text}")
                submit_btn.click()
                time.sleep(5)
                return True
            else:
                print("⚠️ No encontré botón de entrar. Intentando Enter en el último input...")
                if inputs:
                    inputs[-1].send_keys(u'\ue007') # Enter key
                    time.sleep(5)
                    return True
            
            return False

        except Exception as e:
            print(f"⚠️ Error en login: {e}")
            return False

    def get_latest_signal(self) -> Optional[Dict]:
        """
        Lee la señal actual de la página.
        Debe adaptarse al HTML específico de algoritmo.html
        """
        if not self.driver:
            return None
            
        try:
            # Aquí va la lógica de scraping específica
            # Ejemplo: Buscar divs con clases 'signal', 'asset', etc.
            # Como no conozco el HTML exacto, voy a volcar el texto visible y pasarlo a la IA
            
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            # Retornar texto crudo para que el parser IA lo procese
            return {
                "raw_text": body_text,
                "source": "web_algoritmo",
                "timestamp": time.time()
            }
            
        except Exception as e:
            print(f"⚠️ Error leyendo señal web: {e}")
            return None

    def stop(self):
        if self.driver:
            self.driver.quit()
        self.is_running = False
        print("🛑 Navegador web cerrado")

# Prueba independiente
if __name__ == "__main__":
    scraper = WebSignalScraper("Duvier mena", "167326711")
    try:
        scraper.start()
        print("Espera 20 segundos para ver si carga...")
        time.sleep(20)
        signal = scraper.get_latest_signal()
        print("\n--- CONTENIDO DETECTADO ---")
        print(signal['raw_text'][:500] if signal else "Nada detectado")
    finally:
        scraper.stop()
