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
    print(voice_id)
    try:
        audio_stream = client_elevenlabs.text_to_speech.stream(
            text=text,
            voice_id=voice_id,
            output_format="mp3_44100_128",
            model_id="eleven_multilingual_v2",
        )
      
        return StreamingResponse(audio_stream, media_type="audio/mpeg")
    except Exception as e:
        return {"error": f"ElevenLabs API error: {e}"}

            