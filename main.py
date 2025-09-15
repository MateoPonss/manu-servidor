from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from elevenlabs.client import ElevenLabs
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv,dotenv_values
from utils.model import system_instruction_text
import os
from google.cloud import texttospeech

load_dotenv()

config = dotenv_values(".env")

class Question(BaseModel):
    robot_id: str
    voice_id:str
    history:list

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


@app.post("/generate-response")
def generate_response(item: Question):

    try:
        text_response = client_genai.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[item.history],
            config=types.GenerateContentConfig(system_instruction=system_instruction_text),
        
        ).text
    except Exception as e:
        return {"error": f"Gemini API error: {e}"}
    return {
        "text": text_response,
        "audio_url": f"/generate-audio?text={text_response}&voice_id={item.voice_id}"
    }


@app.get("/generate-audio")
def generate_audio(text: str = Query(..., min_length=1), voice_id: str = Query(..., min_length=1)):
    print(f"--- Intentando generar audio para Voice ID: '{voice_id}' ---")
    try:
        audio_stream = client_elevenlabs.text_to_speech.stream(
            text=text,
            voice_id=voice_id,
            output_format="mp3_44100_128",
            model_id="eleven_multilingual_v2",
        )

        # --- CÓDIGO DE DEPURACIÓN PARA EL STREAM ---
        print("--- Stream recibido de ElevenLabs. Verificando contenido... ---")
        
        # Consumimos el stream una vez para inspeccionar los datos
        chunks = list(audio_stream)
        
        if not chunks:
            # Caso 1: El stream está completamente vacío
            print("!!! ALERTA: El stream de ElevenLabs llegó VACÍO. No hay datos de audio. !!!")
            return {"error": "El stream de audio de ElevenLabs llegó vacío."}
        
        # Caso 2: Verificamos si el inicio del stream parece un error JSON en lugar de audio
        first_chunk_sample = chunks[0][:100] # Tomamos los primeros 100 bytes del primer chunk
        print(f"--- Stream recibido con {len(chunks)} chunks. Muestra del primer chunk: {first_chunk_sample} ---")

        if b'{"detail":' in first_chunk_sample:
            print(f"!!! ERROR: El stream parece contener un error JSON: {b''.join(chunks).decode()} !!!")
            return {"error": "ElevenLabs devolvió un error en el stream.", "details": b"".join(chunks).decode()}
        
        # Si todo parece correcto, necesitamos recrear el generador para enviarlo
        def stream_generator():
            for chunk in chunks:
                yield chunk

        print("--- Contenido del stream parece válido. Enviando al cliente... ---")
        return StreamingResponse(stream_generator(), media_type="audio/mpeg")
        # --- FIN DEL CÓDIGO DE DEPURACIÓN ---

    except Exception as e:
        print(f"!!! ElevenLabs API error: {e}. Intentando con Gemini Text-to-Speech... !!!")

        gemini_voices = {
            "ByVRQtaK1WDOvTmP1PKO": "Charon",
            "9rvdnhrYoXoUt4igKpBw": "Kore"
        }

        gemini_voice_name = gemini_voices.get(voice_id, "Charon") 

        try:
            # Instancia el cliente de Text-to-Speech
            client_texttospeech = texttospeech.TextToSpeechClient(client_genai)

            synthesis_input = texttospeech.SynthesisInput(text=text)

            voice = texttospeech.VoiceSelectionParams(
                language_code="es-ES",
                name=gemini_voice_name,
                ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.1,
                pitch=-1.5
            )

            audio_response = client_texttospeech.synthesize_speech(
                request={"input": synthesis_input, "voice": voice, "audio_config": audio_config}
            )

            # Envuelve el contenido de audio en un generador para el StreamingResponse
            def gemini_audio_stream_generator():
                yield audio_response.audio_content

            print("--- Audio generado con Gemini con éxito. Enviando al cliente... ---")
            return StreamingResponse(gemini_audio_stream_generator(), media_type="audio/mpeg")
        except Exception as gemini_e:
            print(f"!!! Fallo al generar audio con Gemini: {gemini_e} !!!")
            return {"error": f"ElevenLabs API error: {e}. Fallback to Gemini failed: {gemini_e}"}