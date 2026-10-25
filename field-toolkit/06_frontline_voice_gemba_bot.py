"""
06_frontline_voice_gemba_bot.py
========================================================================================
FRONTLINE VOICE RECONNAISSANCE BOT & WEBHOOK SERVER (WHISPER + TELEGRAM / WHATSAPP)
========================================================================================
Purpose: Enable field auditors and deployment strategists to send voice notes or text
from their smartphones (via Telegram or WhatsApp/Webhook) while walking the warehouse floor.
The engine transcribes audio on-the-fly using Faster-Whisper, pipes the text through
the Gemba Reconnaissance Knowledge Graph, and returns an executive diagnostic dossier
with quantified financial impact and on-site Red Flags within seconds.

Framework Integration: FDE Field Toolkit
Component: 06_frontline_voice_gemba_bot.py
Dependencies: aiohttp, faster-whisper, fastapi, uvicorn, pydantic
========================================================================================
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
import uvicorn

# Add directory to sys.path for direct imports
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

import importlib.util

spec = importlib.util.spec_from_file_location(
    "gemba_pipeline_module",
    str(current_dir / "05_supply_chain_gemba_recon_pipeline.py")
)
if spec and spec.loader:
    gemba_module = importlib.util.module_from_spec(spec)
    sys.modules["gemba_pipeline_module"] = gemba_module
    spec.loader.exec_module(gemba_module)
    FacilityParameters = gemba_module.FacilityParameters
    GembaReconPipeline = gemba_module.GembaReconPipeline
else:
    raise RuntimeError("Could not load 05_supply_chain_gemba_recon_pipeline.py")

# Ensure UTF-8 output on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("FrontlineVoiceBot")


# ======================================================================================
# 1. FASTER-WHISPER AUDIO TRANSCRIBER
# ======================================================================================

class AudioTranscriber:
    """
    Motor de transcripción rápida de audio utilizando Faster-Whisper.
    Optimizado para ejecución en CPU con cuantización int8 (sub-segundo).
    """

    def __init__(self, model_size: str = "tiny", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _get_model(self):
        if self._model is None:
            logger.info(f"Cargando modelo Faster-Whisper ({self.model_size}) en {self.device} [{self.compute_type}]...")
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            logger.info("Modelo Faster-Whisper cargado exitosamente.")
        return self._model

    def transcribe(self, audio_path: str, language: Optional[str] = "es") -> str:
        """Transcribe un archivo de audio (.ogg, .mp3, .wav, .m4a) a texto."""
        model = self._get_model()
        segments, info = model.transcribe(
            audio_path,
            beam_size=5,
            language=language,
            condition_on_previous_text=False
        )
        full_text = " ".join([segment.text for segment in segments]).strip()
        logger.info(f"Audio transcrito [{info.language} | conf: {round(info.language_probability, 2)}]: '{full_text}'")
        return full_text

    def transcribe_bytes(self, audio_bytes: bytes, file_suffix: str = ".ogg", language: str = "es") -> str:
        """Crea un archivo temporal seguro para transcribir streams de audio de Telegram/WhatsApp."""
        with tempfile.NamedTemporaryFile(suffix=file_suffix, delete=False) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(audio_bytes)

        try:
            return self.transcribe(tmp_path, language=language)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


# ======================================================================================
# 2. TELEGRAM BOT CLIENT (ZERO-DEPENDENCY ASYNC IMPLEMENTATION)
# ======================================================================================

class TelegramFrontlineBot:
    """
    Cliente ligero para Telegram Bot API con soporte para notas de voz y texto.
    No requiere librerías externas de terceros (usa solo aiohttp).
    """

    def __init__(self, token: str, pipeline: GembaReconPipeline, transcriber: AudioTranscriber):
        self.token = token
        self.api_base = f"https://api.telegram.org/bot{self.token}"
        self.file_base = f"https://api.telegram.org/file/bot{self.token}"
        self.pipeline = pipeline
        self.transcriber = transcriber
        self.is_running = False

    async def send_message(self, chat_id: int, text: str, parse_mode: str = "Markdown") -> bool:
        url = f"{self.api_base}/sendMessage"
        # Telegram tiene un límite de 4096 caracteres por mensaje
        chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
        async with aiohttp.ClientSession() as session:
            for chunk in chunks:
                payload = {
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True
                }
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        # Si falla por markdown malformado, reintentar en texto plano
                        payload.pop("parse_mode", None)
                        await session.post(url, json=payload)
        return True

    async def get_file_bytes(self, file_id: str) -> Optional[bytes]:
        url = f"{self.api_base}/getFile?file_id={file_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                file_path = data.get("result", {}).get("file_path")
                if not file_path:
                    return None

            download_url = f"{self.file_base}/{file_path}"
            async with session.get(download_url) as file_resp:
                if file_resp.status == 200:
                    return await file_resp.read()
        return None

    def _format_telegram_dossier(self, results: Dict[str, Any]) -> str:
        """Formatea un resumen visual de alta legibilidad para pantallas de smartphone."""
        findings = results["findings"]
        total_loss = results["estimated_annual_financial_drag_usd"]
        total_count = results["total_findings"]

        if total_count == 0:
            return (
                "🔍 *GEMBA RECON: Sin vulnerabilidades críticas identificadas.*\n\n"
                "La observación no coincidió con los modos de falla pre-mapeados. "
                "Intenta dar más detalles sobre equipos, zonas o retrasos específicos."
            )

        lines = [
            "🚨 *DOSSIER FORENSE OPERATIVO (GEMBA)*",
            f"📊 *Hallazgos detectados:* {total_count}",
            f"💰 *Arrastre financiero:* *${total_loss:,.0f} USD/año*\n",
            "─────────────────────────"
        ]

        for idx, item in enumerate(findings, 1):
            chk = item["diagnostic_check"]
            srv = item["service_offering"]
            severity_icon = "🔴" if item["severity_1_to_10"] >= 8 else ("🟡" if item["severity_1_to_10"] >= 6 else "🟢")

            lines.append(f"{severity_icon} *{idx}. {item['name']}*")
            lines.append(f"• *Impacto:* {item['empirical_impact']}")
            lines.append(f"• *Chequeo en Planta:* `{chk['name']}`")
            lines.append(f"• *Alerta Roja:* _{chk['red_flag_threshold']}_")
            lines.append(f"• *Solución:* *{srv['title']}* (ROI ~{srv['typical_roi_weeks']} sem)")
            lines.append("─────────────────────────")

        lines.append("💡 *Acción:* Ejecuta el muestreo de alerta roja en terreno antes de la reunión con el gerente de planta.")
        return "\n".join(lines)

    async def handle_update(self, update: Dict[str, Any]) -> None:
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        if not chat_id:
            return

        text = message.get("text", "")
        voice = message.get("voice") or message.get("audio")

        # Comandos básicos
        if text.startswith("/start"):
            welcome = (
                "👋 *Bienvenido al Frontline Gemba Reconnaissance Bot*\n\n"
                "🎙️ *Instrucciones:* Envía una nota de voz o un texto describiendo lo que ves en el almacén "
                "(ej. carritos trabados, camiones esperando en muelle, falta de pistolas RF).\n\n"
                "El motor analizará los síntomas y te responderá en segundos con los chequeos de alerta roja "
                "y el impacto financiero para plantear al cliente."
            )
            await self.send_message(chat_id, welcome)
            return

        observation_text = ""

        # Si es un mensaje de voz o audio
        if voice:
            file_id = voice.get("file_id")
            await self.send_message(chat_id, "🎧 *Transcribiendo nota de voz con Faster-Whisper...*")
            audio_bytes = await self.get_file_bytes(file_id)
            if not audio_bytes:
                await self.send_message(chat_id, "❌ Error al descargar el audio de Telegram.")
                return

            try:
                # Transcripción local
                loop = asyncio.get_running_loop()
                observation_text = await loop.run_in_executor(
                    None,
                    self.transcriber.transcribe_bytes,
                    audio_bytes,
                    ".ogg",
                    "es"
                )
            except Exception as e:
                logger.error(f"Error en transcripción: {e}")
                await self.send_message(chat_id, f"❌ Error en transcripción Whisper: {e}")
                return

            await self.send_message(chat_id, f"📝 *Transcripción:* *\"{observation_text}\"*")
        else:
            observation_text = text

        if not observation_text.strip():
            return

        # Procesamiento en el grafo de conocimiento
        results = self.pipeline.process_field_notes(observation_text)
        response_msg = self._format_telegram_dossier(results)
        await self.send_message(chat_id, response_msg)

    async def start_polling(self) -> None:
        """Inicia el ciclo de Long Polling asíncrono con Telegram."""
        self.is_running = True
        offset = 0
        logger.info("Bot de Telegram iniciado en modo Long Polling. Esperando notas de campo...")

        async with aiohttp.ClientSession() as session:
            while self.is_running:
                try:
                    url = f"{self.api_base}/getUpdates?offset={offset}&timeout=20"
                    async with session.get(url, timeout=30) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            updates = data.get("result", [])
                            for update in updates:
                                offset = update["update_id"] + 1
                                asyncio.create_task(self.handle_update(update))
                        elif resp.status == 401:
                            logger.error("Token de Telegram inválido (401 Unauthorized).")
                            self.is_running = False
                            break
                        else:
                            await asyncio.sleep(2)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"Error en polling de Telegram: {e}")
                    await asyncio.sleep(3)


# ======================================================================================
# 3. FASTAPI SERVER FOR WHATSAPP / WEBHOOK & REST API
# ======================================================================================

class TextReconRequest(BaseModel):
    note: str
    pickers: int = 50
    shifts: int = 2
    wage: float = 16.0


def create_app(pipeline: GembaReconPipeline, transcriber: AudioTranscriber) -> FastAPI:
    app = FastAPI(
        title="Frontline Gemba Reconnaissance API",
        description="Ingesta de audio y texto para diagnóstico y venta de servicios en supply chain.",
        version="1.0.0"
    )

    @app.get("/health")
    def health_check():
        return {"status": "healthy", "service": "Gemba Recon API"}

    @app.post("/api/recon/text")
    def process_text_endpoint(req: TextReconRequest):
        """Endpoint REST para procesar texto de observaciones de campo."""
        params = FacilityParameters(
            headcount_pickers=req.pickers,
            shifts_per_day=req.shifts,
            hourly_labor_cost_usd=req.wage
        )
        results = pipeline.process_field_notes(req.note, facility_params=params)
        return JSONResponse(content=results)

    @app.post("/api/recon/audio")
    async def process_audio_endpoint(
        file: UploadFile = File(...),
        pickers: int = Form(50),
        wage: float = Form(16.0)
    ):
        """Endpoint para subir archivos de voz (.ogg, .mp3, .wav) y obtener el diagnóstico."""
        audio_content = await file.read()
        suffix = Path(file.filename or "temp.ogg").suffix or ".ogg"

        loop = asyncio.get_running_loop()
        transcription = await loop.run_in_executor(
            None,
            transcriber.transcribe_bytes,
            audio_content,
            suffix,
            "es"
        )

        params = FacilityParameters(headcount_pickers=pickers, hourly_labor_cost_usd=wage)
        results = pipeline.process_field_notes(transcription, facility_params=params)
        results["transcription"] = transcription
        return JSONResponse(content=results)

    @app.post("/api/webhook/whatsapp")
    async def whatsapp_webhook(request: Request):
        """
        Webhook genérico para WhatsApp (Twilio format o Meta Cloud API).
        Permite enviar la respuesta directamente al teléfono del auditor.
        """
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type:
            # Twilio Form Data
            form_data = await request.form()
            body_text = form_data.get("Body", "")
            from_number = form_data.get("From", "")

            results = pipeline.process_field_notes(str(body_text))
            markdown_dossier = pipeline.generate_markdown_report(results)

            # Respuesta en formato TwiML
            twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{markdown_dossier[:1500]}</Message>
</Response>"""
            return PlainTextResponse(content=twiml_response, media_type="application/xml")
        else:
            return JSONResponse(content={"status": "received"})

    return app


# ======================================================================================
# 4. ENTRYPOINT Y GESTIÓN DE EJECUCIÓN
# ======================================================================================

async def main():
    parser = argparse.ArgumentParser(description="Frontline Voice Reconnaissance Bot")
    parser.add_argument("--telegram-token", type=str, default=os.getenv("TELEGRAM_BOT_TOKEN"), help="Token de Telegram de @BotFather")
    parser.add_argument("--server", action="store_true", help="Iniciar servidor FastAPI HTTP")
    parser.add_argument("--port", type=int, default=8000, help="Puerto para servidor HTTP (default: 8000)")
    parser.add_argument("--whisper-model", type=str, default="tiny", choices=["tiny", "base", "small"], help="Tamaño de modelo Whisper")
    parser.add_argument("--test-text", type=str, help="Probar una transcripción de prueba directamente")

    args = parser.parse_args()

    pipeline = GembaReconPipeline()
    transcriber = AudioTranscriber(model_size=args.whisper_model)

    if args.test_text:
        print("\n" + "="*80)
        print("TEST DE INGESTA DE TEXTO:")
        print("="*80)
        results = pipeline.process_field_notes(args.test_text)
        print(pipeline.generate_markdown_report(results))
        return

    # Si se pasa un token de Telegram, lanzar el bot
    if args.telegram_token:
        bot = TelegramFrontlineBot(args.telegram_token, pipeline, transcriber)
        logger.info("Iniciando servicio de Telegram Bot...")

        if args.server:
            # Correr FastAPI y Telegram concurrentemente
            app = create_app(pipeline, transcriber)
            config = uvicorn.Config(app=app, host="0.0.0.0", port=args.port, log_level="info")
            server = uvicorn.Server(config)
            await asyncio.gather(
                bot.start_polling(),
                server.serve()
            )
        else:
            await bot.start_polling()
    elif args.server:
        app = create_app(pipeline, transcriber)
        config = uvicorn.Config(app=app, host="0.0.0.0", port=args.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    else:
        print("\n" + "="*80)
        print("MODO DEMO LOCAL / ASISTENTE:")
        print("="*80)
        print("Para conectar a Telegram:")
        print("  python 06_frontline_voice_gemba_bot.py --telegram-token <TU_TOKEN_BOTFATHER>")
        print("\nPara iniciar la API REST / Webhook de WhatsApp:")
        print("  python 06_frontline_voice_gemba_bot.py --server --port 8000")
        print("\nEjecutando simulación de nota de voz procesada...")

        mock_voice_text = (
            "Ando revisando la zona de racks y vi dos puntales torcidos en la bahía 4 "
            "con protectores desprendidos. Además las baterías de los reach trucks están "
            "muriendo a las 3 horas de uso y los choferes pierden mucho tiempo cambiándolas."
        )
        print(f"\n🎙️ Simulación de audio recibido: \"{mock_voice_text}\"\n")
        results = pipeline.process_field_notes(mock_voice_text)
        print(pipeline.generate_markdown_report(results))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServicio detenido por el usuario.")
