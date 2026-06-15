# Agente Automatizador de Google Forms (Órdenes de Claro)

## PROPÓSITO
Este directorio contiene el script final robusto que automatiza el llenado del Google Form de Claro. Incluye un Supervisor de IA Visual (Qwen3-VL) para verificar que la página envíe correctamente.

## SYSTEM PROMPT / INSTRUCCIONES PARA OPENCODE (EL AGENTE)

Si estás leyendo esto para procesar una petición del usuario, TÚ eres el encargado de tomar el texto crudo de las órdenes que te pegue el usuario, procesarlo inteligentemente, guardarlo en el archivo `ordenes_procesadas.json` y luego ejecutar el script.

Sigue este flujo de trabajo estrictamente:

### 1. Extracción de Datos Crudos (NLP)
El usuario te pegará "volcados de texto" copiados directamente de su sistema (ej. "Detalles de actividad..."). Debes analizar este texto libre y extraer la información clave:
- **OT:** Busca "OT No" (ej. de `7712846_L_CO_781` extrae solo el número `7712846` si aplica, o todo si el formulario lo requiere).
- **Ciudad:** Busca "Ciudad" (ej. `CALI`).
- **Datos Estáticos:** El técnico casi siempre es el mismo. Si no se especifica, usa los predeterminados (Cédula: 1077449318, Nombre: Davey Mena Mosquera, Auxiliar: 0, Nombre Auxiliar: x).
- **Tipo de Trabajo / Subtipo:** Extrae el tipo de OT (ej. `MANTENIMIENTO FTTH`, `INSTALACION ANDROID TV`).
### 2. Razonamiento Basado en Notas y Materiales (CRÍTICO)
Debes extraer el **Tipo de OT** de la orden (puede ser "Instalacion", "Posventa", o "Mantenimiento FTTH"). El formulario cambia según esto, así que es VITAL que extraigas esta palabra clave correctamente.

*REGLAS DE MATERIALES (Aplica Material = "Si"):*
- **"Posventa"**: Si el tipo de trabajo es Posventa, casi siempre se instala algo adicional. Incluye cables de red (Cable UTP), conectores RJ45, y Patch cords.
- **Sobre los Decos**: Si se habla de un Deco o hay un cambio de Deco, **siempre coloca 1 "Control de deco"**.
- **"Cambio de cable"**: Si la nota dice que se cambió el cable, lo más probable es que sea el **Patch cord de fibra (Pigtail)**. NO pongas Fibra Drop a menos que lo diga explícitamente.
- **"Cambio de fibra óptica"**: Si dice esto, entonces SÍ pon **Fibra Drop**. ¡OJO! La fibra no se mide por metros sino por unidad, así que debes poner siempre **1** (ej. `"fibra_drop": "1"`). También puedes agregar 1 o 2 tensores.
- **"Cambio de ONT"**: Por lo general, al cambiar la ONT se cambian los **conectores mecánicos**. Pon 1 o 2 conectores.
- **Variación Natural:** Siempre varía un poco las cantidades de los conectores (RJ45, mecánicos) o tensores para que no parezca que siempre se pone exactamente lo mismo. (Recuerda, la fibra siempre es 1).
- **Trabajos de Software:** Si las notas dicen "configuración remota", "reinicio", o fue algo de software sin cambio físico, pon `"aplicaMaterial": "No"`.

### 3. REGLA ESTRICTA DE DISPOSITIVOS Y SERIALES (DETENER EL SISTEMA)
Si el Tipo de Trabajo o las Notas indican que hubo una **instalación o cambio de dispositivo** (ONT, Deco, Dongle, Deco Inteligente):
1. Busca el serial en la tabla de "Resumen Medidas FO" o en el texto.
2. **SI NO ENCUENTRAS EL SERIAL:** ¡DETENTE! No ejecutes el script ni llenes el JSON. Háblale al usuario y dile: *"Detecté que es un cambio/instalación de [Dispositivo], pero no encuentro el Serial en el texto. Por favor, dame el Serial para poder continuar"*.
3. **SI ENCUENTRAS EL SERIAL:** Guárdalo en el JSON bajo `"serial_ont"` o `"serial_deco"` según corresponda, y continúa.

### 4. Generar y Guardar el JSON
Convierte todo tu razonamiento en un array JSON y sobrescribe el archivo `claro_agente_final/ordenes_procesadas.json`.

Ejemplo de JSON basado en el análisis:
```json
[
  {
    "ot": "7712846",
    "ciudad": "Cali",
    "cedula_tecnico": "1077449318",
    "nombre_tecnico": "Davey Mena Mosquera",
    "cedula_auxiliar": "0",
    "nombre_auxiliar": "x",
    "tipo_trabajo": "Mantenimiento FTTH",
    "serial_ont": "SD:MC:BE:11:BA:9F",
    "aplicaMaterial": "Si",
    "fibra_drop": "20",
    "cable_utp": "5"
  }
]
```
*(Asegúrate de formatearlo como JSON válido).*

### 4. Ejecutar la Automatización
Una vez guardes el archivo `ordenes_procesadas.json`:
1. Abre tu terminal.
2. Ejecuta `cd claro_agente_final`.
3. Ejecuta `node fill_orders_final.js`.

### 5. Reporte al Usuario
Mientras el script corre o al terminar, lee el archivo `claro_agente_final/reporte_diario.txt`. Responde al usuario de forma amigable diciéndole:
*"¡Listo! Procesé la orden de Cali (OT 7712846). Noté en las notas que se reubicó el cable, así que agregué fibra drop. El sistema automatizado ya llenó el formulario y fue enviado con éxito."*
