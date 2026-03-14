from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./contract_db")
