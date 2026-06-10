"""
Async Exnova Connector - Conexión Asíncrona No-Bloqueante
Reemplaza los WebSockets bloqueantes con arquitectura async moderna
"""
import asyncio
import websockets
import json
import time
from typing import Dict, Optional, Callable, Any, List
from dataclasses import dataclass
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor


@dataclass
class ConnectionState:
    """Estado de la conexión"""
    connected: bool = False
    last_ping: float = 0.0
    last_pong: float = 0.0
    latency_ms: float = 0.0
    reconnect_attempts: int = 0
    last_error: Optional[str] = None
    messages_sent: int = 0
    messages_received: int = 0


class CircuitBreaker:
    """
    Circuit Breaker para proteger contra fallos en cascada

    Estados:
    - CLOSED: Operación normal
    - OPEN: Fallos detectados, rechazar operaciones
    - HALF_OPEN: Probando si se recuperó
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = "CLOSED"
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Ejecutar función con circuit breaker"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                self.half_open_calls = 0
            else:
                raise Exception(f"Circuit breaker OPEN. Last failure: {self.last_failure_time}")

        if self.state == "HALF_OPEN":
            if self.half_open_calls >= self.half_open_max_calls:
                raise Exception("Circuit breaker HALF_OPEN: máximo de llamadas alcanzado")
            self.half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Registrar éxito"""
        self.failure_count = 0
        if self.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                self.state = "CLOSED"
                self.success_count = 0

    def _on_failure(self):
        """Registrar fallo"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            print(f"🛡️ Circuit breaker OPEN después de {self.failure_count} fallos")


class RateLimiter:
    """
    Rate Limiter para controlar frecuencia de operaciones

    Usa token bucket algorithm
    """

    def __init__(self, max_calls: int, period: float):
        """
        Args:
            max_calls: Máximo de llamadas permitidas
            period: Período en segundos
        """
        self.max_calls = max_calls
        self.period = period
        self.tokens = max_calls
        self.last_update = time.time()
        self._lock = threading.Lock()

    def acquire(self, blocking: bool = True, timeout: float = 10.0) -> bool:
        """
        Adquirir token

        Args:
            blocking: Si True, espera hasta obtener token
            timeout: Tiempo máximo de espera

        Returns:
            True si adquirió token, False si timeout
        """
        start_time = time.time()

        while True:
            with self._lock:
                now = time.time()
                elapsed = now - self.last_update

                # Recargar tokens basados en tiempo transcurrido
                tokens_to_add = (elapsed / self.period) * self.max_calls
                self.tokens = min(self.max_calls, self.tokens + tokens_to_add)
                self.last_update = now

                if self.tokens >= 1:
                    self.tokens -= 1
                    return True

            if not blocking:
                return False

            if time.time() - start_time > timeout:
                return False

            time.sleep(0.1)  # Esperar 100ms antes de reintentar

    async def acquire_async(self, timeout: float = 10.0) -> bool:
        """Versión asíncrona de acquire"""
        start_time = time.time()

        while True:
            with self._lock:
                now = time.time()
                elapsed = now - self.last_update
                tokens_to_add = (elapsed / self.period) * self.max_calls
                self.tokens = min(self.max_calls, self.tokens + tokens_to_add)
                self.last_update = now

                if self.tokens >= 1:
                    self.tokens -= 1
                    return True

            if time.time() - start_time > timeout:
                return False

            await asyncio.sleep(0.1)


class AsyncExnovaConnector:
    """
    Conector Asíncrono para Exnova API

    Características:
    - WebSockets no bloqueantes con asyncio
    - Reconexión automática exponencial backoff
    - Circuit breaker para protección
    - Rate limiting configurable
    - Heartbeat automático
    - Cola de mensajes pendiente
    - Métricas de latencia
    """

    def __init__(
        self,
        ws_url: str = "wss://ws.exnova.com",
        http_base: str = "https://api.exnova.com",
        max_reconnect_attempts: int = 10,
        heartbeat_interval: float = 30.0,
        rate_limit_calls: int = 100,
        rate_limit_period: float = 60.0,
    ):
        self.ws_url = ws_url
        self.http_base = http_base
        self.max_reconnect_attempts = max_reconnect_attempts
        self.heartbeat_interval = heartbeat_interval

        # Estado
        self.connection_state = ConnectionState()
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._authenticated = False

        # Rate limiter: 100 llamadas/minuto
        self.rate_limiter = RateLimiter(rate_limit_calls, rate_limit_period)

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0
        )

        # Cola de mensajes pendientes
        self._pending_messages: Dict[str, asyncio.Future] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()

        # Callbacks
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._on_message: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

        # Loop de eventos
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._executor = ThreadPoolExecutor(max_workers=4)

        # Hilos
        self._ws_thread: Optional[threading.Thread] = None

    def set_auth_token(self, token: str):
        """Establecer token de autenticación"""
        self._auth_token = token
        self._authenticated = True

    def set_callbacks(
        self,
        on_connect: Optional[Callable] = None,
        on_disconnect: Optional[Callable] = None,
        on_message: Optional[Callable] = None,
        on_error: Optional[Callable] = None
    ):
        """Configurar callbacks"""
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_message = on_message
        self._on_error = on_error

    def start(self):
        """Iniciar conexión en hilo separado"""
        self._running = True
        self._ws_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._ws_thread.start()
        print("✅ AsyncExnovaConnector iniciado en hilo separado")

    def stop(self):
        """Detener conexión"""
        self._running = False
        self._executor.shutdown(wait=False)
        if self._ws_thread:
            self._ws_thread.join(timeout=5)
        print("🛑 AsyncExnovaConnector detenido")

    def _run_async_loop(self):
        """Ejecutar loop asyncio en hilo"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._main_loop())
        except Exception as e:
            print(f"❌ Error en loop asyncio: {e}")
            if self._on_error:
                self._on_error(e)
        finally:
            self._loop.close()

    async def _main_loop(self):
        """Loop principal con reconexión automática"""
        reconnect_delay = 1.0
        reconnect_count = 0

        while self._running:
            try:
                await self._connect()
                reconnect_count = 0
                reconnect_delay = 1.0

                # Mantener conexión activa
                await self._keep_alive()

            except Exception as e:
                reconnect_count += 1
                self.connection_state.reconnect_attempts = reconnect_count
                self.connection_state.last_error = str(e)

                print(f"⚠️ Error de conexión (intento {reconnect_count}/{self.max_reconnect_attempts}): {e}")

                if reconnect_count >= self.max_reconnect_attempts:
                    print(f"❌ Máximo de reconexiones alcanzado")
                    if self._on_error:
                        self._on_error(e)
                    break

                # Exponential backoff
                wait_time = min(reconnect_delay * (2 ** reconnect_count), 60)
                print(f"⏱️ Reintentando en {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)

    async def _connect(self):
        """Establecer conexión WebSocket"""
        headers = {}
        if hasattr(self, '_auth_token'):
            headers['Authorization'] = f'Bearer {self._auth_token}'

        self.ws = await websockets.connect(
            self.ws_url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
            extra_headers=headers,
            max_size=10 * 1024 * 1024,  # 10MB max message
        )

        self.connection_state.connected = True
        self.connection_state.last_ping = time.time()
        print("✅ WebSocket conectado")

        if self._on_connect:
            self._on_connect()

    async def _keep_alive(self):
        """Mantener conexión con heartbeat"""
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        receive_task = asyncio.create_task(self._receive_loop())

        try:
            await asyncio.gather(heartbeat_task, receive_task)
        except Exception as e:
            heartbeat_task.cancel()
            receive_task.cancel()
            raise e

    async def _heartbeat_loop(self):
        """Enviar ping periódico"""
        while self._running and self.ws:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                start = time.time()
                pong = await self.ws.ping()
                await asyncio.wait_for(pong, timeout=10)

                self.connection_state.last_ping = start
                self.connection_state.last_pong = time.time()
                self.connection_state.latency_ms = (self.connection_state.last_pong - start) * 1000

            except asyncio.TimeoutError:
                print("⚠️ Ping timeout - posible desconexión")
                raise Exception("Heartbeat timeout")
            except Exception as e:
                print(f"⚠️ Error en heartbeat: {e}")
                raise

    async def _receive_loop(self):
        """Recibir mensajes asíncronamente"""
        try:
            async for message in self.ws:
                self.connection_state.messages_received += 1

                try:
                    data = json.loads(message)

                    # Resolver mensaje pendiente si existe
                    if 'request_id' in data:
                        request_id = data['request_id']
                        if request_id in self._pending_messages:
                            self._pending_messages[request_id].set_result(data)
                            del self._pending_messages[request_id]

                    # Callback de mensaje
                    if self._on_message:
                        await self._call_async(self._on_message, data)

                except json.JSONDecodeError:
                    print(f"⚠️ Mensaje no JSON: {message[:100]}")

        except websockets.ConnectionClosed:
            print("🔌 Conexión cerrada")
            self.connection_state.connected = False
            raise

    async def send(
        self,
        action: str,
        data: Dict,
        timeout: float = 10.0,
        use_rate_limit: bool = True
    ) -> Dict:
        """
        Enviar mensaje y esperar respuesta

        Args:
            action: Nombre de la acción
            data: Datos a enviar
            timeout: Tiempo máximo de espera
            use_rate_limit: Usar rate limiter

        Returns:
            Respuesta del servidor
        """
        if not self.connection_state.connected:
            raise Exception("No conectado")

        if use_rate_limit and not await self.rate_limiter.acquire_async(timeout=5):
            raise Exception("Rate limit alcanzado")

        # Circuit breaker check
        if self.circuit_breaker.state == "OPEN":
            raise Exception("Circuit breaker OPEN")

        request_id = f"{action}_{int(time.time() * 1000)}"

        message = {
            "action": action,
            "data": data,
            "request_id": request_id
        }

        # Crear future para esperar respuesta
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending_messages[request_id] = future

        try:
            # Enviar mensaje
            await self.ws.send(json.dumps(message))
            self.connection_state.messages_sent += 1

            # Esperar respuesta
            response = await asyncio.wait_for(future, timeout=timeout)

            # Verificar error en respuesta
            if response.get('error'):
                self.circuit_breaker._on_failure()
                raise Exception(response['error'])

            self.circuit_breaker._on_success()
            return response

        except asyncio.TimeoutError:
            if request_id in self._pending_messages:
                del self._pending_messages[request_id]
            self.circuit_breaker._on_failure()
            raise Exception(f"Timeout esperando respuesta de {action}")

    async def _call_async(self, func: Callable, *args, **kwargs):
        """Llamar función (async o sync)"""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    # Métodos específicos de Exnova

    async def subscribe_candles(self, asset_id: str, timeframe: int = 60) -> Dict:
        """Suscribirse a velas de un activo"""
        return await self.send(
            "subscribe-candles",
            {"asset_id": asset_id, "timeframe": timeframe}
        )

    async def unsubscribe_candles(self, asset_id: str) -> Dict:
        """Desuscribirse de velas"""
        return await self.send(
            "unsubscribe-candles",
            {"asset_id": asset_id}
        )

    async def place_order(
        self,
        asset_id: str,
        amount: float,
        direction: str,
        expiration: int
    ) -> Dict:
        """
        Colocar orden de trading

        Args:
            asset_id: ID del activo
            amount: Monto en dólares
            direction: "call" o "put"
            expiration: Tiempo de expiración en segundos

        Returns:
            Respuesta con ID de orden
        """
        # Validar con circuit breaker
        def _validate():
            if not self._authenticated:
                raise Exception("No autenticado")

        self.circuit_breaker.call(_validate)

        return await self.send(
            "place-order",
            {
                "asset_id": asset_id,
                "amount": amount,
                "direction": direction,
                "expiration": expiration
            },
            timeout=5.0
        )

    async def get_balance(self) -> Dict:
        """Obtener balance"""
        return await self.send("get-balance", {}, timeout=5.0)

    async def get_assets(self) -> Dict:
        """Obtener lista de activos disponibles"""
        return await self.send("get-assets", {}, timeout=10.0)

    def get_status(self) -> Dict:
        """Obtener estado del conector"""
        return {
            'connected': self.connection_state.connected,
            'authenticated': self._authenticated,
            'latency_ms': self.connection_state.latency_ms,
            'messages_sent': self.connection_state.messages_sent,
            'messages_received': self.connection_state.messages_received,
            'reconnect_attempts': self.connection_state.reconnect_attempts,
            'circuit_breaker_state': self.circuit_breaker.state,
            'pending_messages': len(self._pending_messages),
        }


# Singleton
_connector: Optional[AsyncExnovaConnector] = None


def get_async_connector() -> AsyncExnovaConnector:
    """Obtener instancia singleton"""
    global _connector
    if _connector is None:
        _connector = AsyncExnovaConnector()
    return _connector
