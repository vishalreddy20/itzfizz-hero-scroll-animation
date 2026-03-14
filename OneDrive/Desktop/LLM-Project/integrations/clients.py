from __future__ import annotations

import google.generativeai as genai
import ollama
from groq import Groq
from sentence_transformers import SentenceTransformer

from integrations.config import CHROMA_PATH, GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY
from integrations.local_vector_store import LocalVectorStore

try:
    import chromadb  # type: ignore
except Exception:
    chromadb = None


def get_embedder() -> SentenceTransformer:
    return SentenceTransformer("all-MiniLM-L6-v2")


def get_chroma_client() -> object:
    if chromadb is None:
        return LocalVectorStore(CHROMA_PATH)
    return chromadb.PersistentClient(path=CHROMA_PATH)


def get_ollama() -> object:
    return ollama


def get_groq_client() -> Groq:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set in environment.")
    return Groq(api_key=GROQ_API_KEY)


def get_gemini_model() -> genai.GenerativeModel:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in environment.")
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        generation_config={
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    )
