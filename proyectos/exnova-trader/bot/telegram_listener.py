"""
Telegram Signal Listener
Escucha señales de trading de grupos/canales de Telegram usando Telethon
"""

import asyncio
import os
from typing import Callable, Optional
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from core.signal_parser import SignalParser

class TelegramListener:
    """
    Cliente de Telegram que escucha señales de trading
    
    Usa Telethon (MTProto) para conectarse como usuario y escuchar mensajes
    de grupos/canales sin necesidad de ser administrador
    """
    
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        session_name: str = "trading_session",
        signal_callback: Optional[Callable] = None
    ):
        """
        Args:
            api_id: API ID de Telegram (obtener en my.telegram.org)
            api_hash: API Hash de Telegram
            phone: Número de teléfono (formato internacional: +573001234567)
            session_name: Nombre del archivo de sesión
            signal_callback: Función a llamar cuando se detecta una señal
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_name = session_name
        self.signal_callback = signal_callback
        
        # Parser de señales
        self.parser = SignalParser()
        
        # Cliente de Telegram
        self.client = TelegramClient(session_name, api_id, api_hash)
        
        # Estadísticas
        self.messages_received = 0
        self.signals_detected = 0
        self.signals_executed = 0
        
        # Estado
        self.is_running = False
        self.monitored_chats = []
    
    async def start(self):
        """Inicia el cliente de Telegram"""
        print("🔌 Conectando a Telegram...")
        
        await self.client.start(phone=self.phone)
        
        # Verificar si está conectado
        if await self.client.is_user_authorized():
            me = await self.client.get_me()
            print(f"✅ Conectado como: {me.first_name} (@{me.username})")
            self.is_running = True
        else:
            print("❌ No se pudo autorizar. Verifica tus credenciales.")
            raise Exception("No autorizado en Telegram")
    
    async def add_chat_to_monitor(self, chat_identifier: str):
        """
        Agrega un chat/canal para monitorear
        
        Args:
            chat_identifier: Puede ser:
                - Username del canal: @nombre_canal
                - ID del chat: -1001234567890
                - Nombre del grupo
        """
        try:
            entity = await self.client.get_entity(chat_identifier)
            self.monitored_chats.append(entity.id)
            print(f"✅ Monitoreando: {entity.title} (ID: {entity.id})")
            return True
        except Exception as e:
            print(f"❌ Error agregando chat {chat_identifier}: {e}")
            return False
    
    def set_signal_callback(self, callback: Callable):
        """Establece la función callback para señales detectadas"""
        self.signal_callback = callback
    
    async def handle_new_message(self, event):
        """
        Maneja nuevos mensajes recibidos
        
        Args:
            event: Evento de nuevo mensaje de Telethon
        """
        try:
            self.messages_received += 1
            
            # Obtener texto del mensaje
            message_text = event.message.message
            
            # Información del chat
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', 'Privado')
            
            # Solo procesar si es de un chat monitoreado
            if self.monitored_chats and event.chat_id not in self.monitored_chats:
                return
            
            # Parsear señal
            signal = self.parser.parse(message_text)
            
            if signal:
                self.signals_detected += 1
                
                print(f"\n{'='*60}")
                print(f"🎯 SEÑAL DETECTADA #{self.signals_detected}")
                print(f"{'='*60}")
                print(f"📱 Chat: {chat_title}")
                print(f"💬 Mensaje: {message_text}")
                print(f"📊 Asset: {signal['asset']}")
                print(f"📈 Dirección: {signal['direction'].upper()}")
                print(f"⏱️  Expiración: {signal['expiration']} min")
                print(f"🕐 Hora: {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'='*60}\n")
                
                # Ejecutar callback si está configurado
                if self.signal_callback:
                    try:
                        # Llamar callback (puede ser sync o async)
                        if asyncio.iscoroutinefunction(self.signal_callback):
                            await self.signal_callback(signal)
                        else:
                            self.signal_callback(signal)
                        
                        self.signals_executed += 1
                        print(f"✅ Señal ejecutada correctamente\n")
                    except Exception as e:
                        print(f"❌ Error ejecutando señal: {e}\n")
        
        except Exception as e:
            print(f"⚠️ Error procesando mensaje: {e}")
    
    async def listen(self, chat_identifiers: list = None):
        """
        Inicia la escucha de mensajes. Se asegura de estar conectado primero.
        """
        if not self.client.is_connected():
            print("⚠️ Cliente desconectado. Iniciando conexión...")
            await self.start()

        # Agregar chats a monitorear
        if chat_identifiers:
            if isinstance(chat_identifiers, str):
                # Si llega como string único (ej: "@EDINSON358"), convertir a lista
                chat_identifiers = [c.strip() for c in chat_identifiers.split(',')]
                
            for chat_id in chat_identifiers:
                await self.add_chat_to_monitor(chat_id)
        else:
            print("⚠️ Monitoreando TODOS los chats (puede generar muchas notificaciones)")
        
        # Registrar handler de mensajes
        @self.client.on(events.NewMessage())
        async def message_handler(event):
            await self.handle_new_message(event)
        
        print(f"\n{'='*60}")
        print("🎧 ESCUCHANDO SEÑALES DE TELEGRAM")
        print(f"{'='*60}")
        print(f"📱 Chats monitoreados: {len(self.monitored_chats) if self.monitored_chats else 'TODOS'}")
        print(f"🤖 Parser listo para detectar señales")
        print(f"{'='*60}\n")
        
        # Mantener el cliente corriendo
        await self.client.run_until_disconnected()
    
    async def stop(self):
        """Detiene el listener"""
        print("\n🛑 Deteniendo Telegram Listener...")
        self.is_running = False
        await self.client.disconnect()
        print("✅ Desconectado de Telegram")
    
    def get_stats(self) -> dict:
        """Retorna estadísticas del listener"""
        return {
            'messages_received': self.messages_received,
            'signals_detected': self.signals_detected,
            'signals_executed': self.signals_executed,
            'is_running': self.is_running,
            'monitored_chats': len(self.monitored_chats)
        }


# Ejemplo de uso
async def example_callback(signal: dict):
    """Función de ejemplo que se ejecuta cuando se detecta una señal"""
    print(f"🚀 EJECUTANDO TRADE:")
    print(f"   {signal['direction'].upper()} en {signal['asset']}")
    print(f"   Expiración: {signal['expiration']} min")
    # Aquí iría la lógica para ejecutar en el broker


async def main():
    """Ejemplo de uso del TelegramListener"""
    
    # Configuración (DEBES OBTENER ESTOS VALORES EN my.telegram.org)
    API_ID = int(os.getenv('TELEGRAM_API_ID', '0'))
    API_HASH = os.getenv('TELEGRAM_API_HASH', '')
    PHONE = os.getenv('TELEGRAM_PHONE', '')
    
    if API_ID == 0 or not API_HASH or not PHONE:
        print("❌ ERROR: Debes configurar las variables de entorno:")
        print("   TELEGRAM_API_ID")
        print("   TELEGRAM_API_HASH")
        print("   TELEGRAM_PHONE")
        print("\nObtén tus credenciales en: https://my.telegram.org")
        return
    
    # Crear listener
    listener = TelegramListener(
        api_id=API_ID,
        api_hash=API_HASH,
        phone=PHONE,
        signal_callback=example_callback
    )
    
    try:
        # Iniciar
        await listener.start()
        
        # Escuchar (puedes especificar chats específicos)
        # await listener.listen(['@nombre_canal', '-1001234567890'])
        
        # O escuchar todos los chats
        await listener.listen()
    
    except KeyboardInterrupt:
        print("\n⚠️ Interrumpido por usuario")
    finally:
        await listener.stop()


if __name__ == "__main__":
    asyncio.run(main())
