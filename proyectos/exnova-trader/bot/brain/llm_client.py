import os, json, time, traceback
from typing import Optional, Dict, List

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat:free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

NVIDIA_NIM_BRIDGE_URL = os.getenv("NVIDIA_NIM_BRIDGE_URL", "http://localhost:3000/v1")
NVIDIA_NIM_BRIDGE_API_KEY = os.getenv("NVIDIA_NIM_BRIDGE_API_KEY", "")
NVIDIA_NIM_BRIDGE_MODEL = os.getenv("NVIDIA_NIM_BRIDGE_MODEL", "moonshotai/kimi-k2.6")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_MODEL = os.getenv("GITHUB_MODEL", "gpt-4o")
GITHUB_BASE_URL = "https://models.inference.ai.azure.com"

PROVIDER_ORDER = ["openrouter", "nvidia", "github"]


class LLMClient:
    def __init__(self):
        self._last_call = 0
        self._min_interval = 0.8
        self._provider_index = 0
        self._current_provider = None
        self._fallback_logged = set()

        self._clients = {}

        if OPENROUTER_API_KEY:
            from openai import OpenAI
            self._clients["openrouter"] = {
                "client": OpenAI(
                    api_key=OPENROUTER_API_KEY,
                    base_url=OPENROUTER_BASE_URL
                ),
                "model": OPENROUTER_MODEL,
                "name": "OpenRouter"
            }

        if NVIDIA_NIM_BRIDGE_URL and NVIDIA_NIM_BRIDGE_API_KEY:
            from openai import OpenAI
            self._clients["nvidia"] = {
                "client": OpenAI(
                    api_key=NVIDIA_NIM_BRIDGE_API_KEY,
                    base_url=NVIDIA_NIM_BRIDGE_URL
                ),
                "model": NVIDIA_NIM_BRIDGE_MODEL,
                "name": "NVIDIA NIM"
            }

        if GITHUB_TOKEN:
            from openai import OpenAI
            self._clients["github"] = {
                "client": OpenAI(
                    api_key=GITHUB_TOKEN,
                    base_url=GITHUB_BASE_URL
                ),
                "model": GITHUB_MODEL,
                "name": "GitHub Models"
            }

        self._provider_list = [p for p in PROVIDER_ORDER if p in self._clients]
        self._current_provider = self._provider_list[0] if self._provider_list else None

    def _get_provider_name(self, provider_id: str) -> str:
        return self._clients.get(provider_id, {}).get("name", provider_id)

    def _rate_limit(self):
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.time()

    def _query(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.3) -> str:
        if not self._provider_list:
            return "Error: No hay proveedores LLM configurados"

        for attempt in range(len(self._provider_list) * 2):
            provider_id = self._provider_list[self._provider_index % len(self._provider_list)]
            provider = self._clients[provider_id]

            try:
                self._rate_limit()
                resp = provider["client"].chat.completions.create(
                    model=provider["model"],
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                self._current_provider = provider_id
                return resp.choices[0].message.content.strip()

            except Exception as e:
                err_str = str(e)
                if provider_id not in self._fallback_logged:
                    print(f"[LLM] {provider['name']} error: {err_str[:120]}")
                    self._fallback_logged.add(provider_id)

                self._provider_index = (self._provider_index + 1) % len(self._provider_list)

        return "Error: Todos los proveedores LLM fallaron"

    def analyze(self, prompt: str) -> str:
        return self._query(prompt, max_tokens=2048, temperature=0.2)

    def get_advice(self, context: str) -> str:
        prompt = (
            "You are an expert binary options trading advisor. "
            "Analyze the following market context and give clear, concise advice. "
            "Respond in SPANISH. Max 3 sentences.\n\n"
            f"Context:\n{context}"
        )
        return self._query(prompt, max_tokens=512, temperature=0.3)

    def analyze_entry_timing(self, df, proposed_action: str, proposed_asset: str, extra_context: str) -> Dict:
        last_candles = df.tail(10).to_dict("records") if df is not None else []
        prompt = (
            "You are a binary options entry timing expert. "
            "Given the following data, decide if now is the right time to enter a trade. "
            "Respond in JSON format with keys: should_trade (bool), confidence (0-100), reason (str).\n\n"
            f"Asset: {proposed_asset}\n"
            f"Proposed Action: {proposed_action}\n"
            f"Context: {extra_context}\n"
            f"Last 10 candles (index,open,high,low,close): {json.dumps(last_candles, default=str)[:2000]}\n\n"
            "JSON:"
        )
        raw = self._query(prompt, max_tokens=512, temperature=0.2)
        return self._parse_json_response(raw, {"should_trade": False, "confidence": 0, "reason": raw[:200]})

    def analyze_complete_trading_opportunity(
        self, market_data_summary: str, smart_money_analysis: str,
        learning_insights: str, asset: str, current_balance: float
    ) -> Dict:
        prompt = (
            "You are an expert trading AI. Analyze this complete trading opportunity and decide. "
            "Respond in JSON with keys: should_trade (bool), direction (CALL/PUT), "
            "confidence (0-100), primary_reason (str), risk_factors (list of str).\n\n"
            f"Asset: {asset}\n"
            f"Balance: ${current_balance}\n\n"
            f"Market Data:\n{market_data_summary[:1500]}\n\n"
            f"Smart Money Analysis:\n{smart_money_analysis[:1000]}\n\n"
            f"Learning Insights:\n{learning_insights[:1000]}\n\n"
            "JSON:"
        )
        raw = self._query(prompt, max_tokens=1024, temperature=0.2)
        return self._parse_json_response(raw, {
            "should_trade": False, "direction": "CALL",
            "confidence": 0, "primary_reason": raw[:200],
            "risk_factors": ["LLM error"]
        })

    def reason_market(self, asset: str, current_price: float, zone_data: str,
                      cascade_data: str, context_data: str, candle_summary: str,
                      extra_m1_data: str = "") -> Dict:
        prompt = (
            "Eres un trader profesional de opciones binarias con 20 anios de experiencia. "
            "Analiza el mercado en profundidad y decide.\n\n"
            "REGLAS DE ORO:\n"
            "- Si el precio esta en una zona de soporte fuerte Y la cascada muestra tendencia alcista "
            "Y hay patron de rechazo -> CALL (compra). El precio rebotara.\n"
            "- Si el precio esta en una zona de resistencia fuerte Y la cascada muestra tendencia bajista "
            "Y hay patron de rechazo -> PUT (venta). El precio caera.\n"
            "- NO uses el RSI como filtro estricto. RSI en 50 es NEUTRAL, no impide una operacion.\n"
            "- Si la zona se ha tocado muchas veces (3+) y se mantiene -> es confiable.\n"
            "- Si la cascada H1/M15/M5 esta alineada en una direccion -> prioriza esa direccion.\n"
            "- Una vela con mecha larga en zona de soporte/resistencia = rechazo = entrada.\n\n"
            "Responde SOLO en JSON con estas claves:\n"
            "  market_narrative (str): explica en espaniol que esta pasando\n"
            "  reasoning_steps (list): pasos de tu razonamiento\n"
            "  direction (CALL/PUT/HOLD): que direccion recomiendas\n"
            "  recommended_action (TRADE/WAIT/SKIP): TRADE si es momento de entrar\n"
            "  conviction (0-100): que tan seguro estas\n"
            "  risk_flags (list): riesgos que ves\n"
            "  next_steps (list): que hacer ahora\n"
            "  entry_zone_pct (float): si recomiendas TRADE, a que % del rango de la vela "
            "esperar para entrar (0.0 = ahora, 0.5 = mitad de la vela, 1.0 = cierre)\n\n"
            f"Activo: {asset}\n"
            f"Precio actual: {current_price}\n\n"
            f"ZONAS:\n{zone_data[:1200]}\n\n"
            f"CASCADA H1->M15->M5:\n{cascade_data[:1200]}\n\n"
            f"CONTEXTO:\n{context_data[:1200]}\n\n"
            f"VELA M1:\n{candle_summary[:1200]}\n\n"
            f"DATOS ADICIONALES M1:\n{extra_m1_data[:1000]}\n\n"
            "Analiza oferta vs demanda. Si el precio fue VENDIDO agresivamente en soporte "
            "y esta rebotando -> CALL. Si fue COMPRADO agresivamente en resistencia y "
            "esta cayendo -> PUT. Piensa como trader, no como indicador.\n"
            "JSON:"
        )
        raw = self._query(prompt, max_tokens=3072, temperature=0.3)
        return self._parse_json_response(raw, {
            "market_narrative": raw[:300],
            "reasoning_steps": ["LLM fallback"],
            "direction": "HOLD",
            "recommended_action": "WAIT",
            "conviction": 0,
            "risk_flags": ["error en LLM"],
            "next_steps": ["reintentar en proximo ciclo"],
            "entry_zone_pct": 0.0
        })

    def _parse_json_response(self, raw: str, fallback: Dict) -> Dict:
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(l for l in lines if not l.startswith("```"))
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                return json.loads(cleaned[start:end+1])
            return json.loads(cleaned)
        except Exception:
            return fallback


_client_instance: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = LLMClient()
    return _client_instance
