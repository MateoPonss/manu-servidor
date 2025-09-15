from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from elevenlabs.client import ElevenLabs
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.cloud import texttospeech
from dotenv import load_dotenv, dotenv_values
from utils.model import system_instruction_text
import os
import wave
import io

load_dotenv()

config = dotenv_values(".env")

class Question(BaseModel):
    robot_id: str
    voice_id: str
    history: list

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

client_elevenlabs = ElevenLabs(api_key=ELEVENLABS_API_KEY)
client_genai = genai.Client(api_key=GEMINI_API_KEY)
client_gemini_tts = texttospeech.TextToSpeechClient()


# Variable global para manejar el proveedor de voz y los IDs de voz de Gemini
voice_provider = "elevenlabs"
gemini_voices = {
    "ByVRQtaK1WDOvTmP1PKO": "es-ES-Neural2-A", # Masculina (reemplazado por voz Neural2 de es-ES)
    "9rvdnhrYoXoUt4igKpBw": "es-ES-Neural2-B", # Femenina (reemplazado por voz Neural2 de es-ES)
}

def generate_gemini_audio(text: str, voice_id: str):
    """Genera audio usando la API de Google Cloud Text-to-Speech."""
    try:
        voice = texttospeech.VoiceSelectionParams(
            language_code="es-ES",
            name=gemini_voices.get(voice_id),
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
        )
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        response = client_gemini_tts.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        
        return StreamingResponse(io.BytesIO(response.audio_content), media_type="audio/mpeg")
    except Exception as e:
        print(f"!!! EXCEPCIÓN CON GEMINI TTS CAPTURADA: {e} !!!")
        raise HTTPException(status_code=500, detail=f"Gemini TTS API error: {e}")

@app.post("/generate-response")
def generate_response(item: Question):

    try:
        text_response = client_genai.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[item.history],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction_text,
                max_output_tokens=256,
            ),
        ).text
    except Exception as e:
        return {"error": f"Gemini API error: {e}"}
    return {
        "text": text_response,
        "audio_url": f"/generate-audio?text={text_response}&voice_id={item.voice_id}"
    }


@app.get("/generate-audio")
def generate_audio(text: str = Query(..., min_length=1), voice_id: str = Query(..., min_length=1)):
    global voice_provider
    
    if voice_provider == "elevenlabs":
        print(f"--- Intentando generar audio con ElevenLabs para Voice ID: '{voice_id}' ---")
        try:
            audio_stream = client_elevenlabs.text_to_speech.stream(
                text=text,
                voice_id=voice_id,
                output_format="mp3_44100_128",
                model_id="eleven_multilingual_v2",
            )
            print("--- Stream de ElevenLabs parece válido. Enviando al cliente... ---")
            return StreamingResponse(audio_stream, media_type="audio/mpeg")
        except Exception as e:
            print(f"!!! EXCEPCIÓN CON ELEVENLABS CAPTURADA: {e} !!!")
            print("!!! CAMBIANDO A GEMINI TTS PARA EL RESTO DE LA SESIÓN !!!")
            voice_provider = "gemini"
            # Si falla ElevenLabs, intentamos inmediatamente con Gemini
            return generate_gemini_audio(text, voice_id)
            
    elif voice_provider == "gemini":
        print(f"--- Usando Gemini TTS para Voice ID: '{voice_id}' ---")
        return generate_gemini_audio(text, voice_id)