"""
Servidor Backend REST API com FastAPI para a Santos Pegasus Soluciones.
"""

import os
import shutil
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from rag_engine import RAGEngine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "Docs")
SAMPLE_DIR = os.path.join(BASE_DIR, "sample_data")

os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(SAMPLE_DIR, exist_ok=True)

app = FastAPI(
    title="Santos Pegasus Soluciones - AI Knowledge Agent API",
    description="API Corporativa RAG Multi-Formato para suporte a colaboradores",
    version="2.0.0"
)

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar motor RAG
rag_engine = RAGEngine(docs_dir=DOCS_DIR, sample_dir=SAMPLE_DIR)

# Métricas de execução
METRICS = {
    "total_queries": 42,
    "start_time": time.time(),
    "uploads_count": 0
}


class ChatQueryRequest(BaseModel):
    query: str
    category: Optional[str] = "Todos"


@app.get("/api/health")
def get_health():
    docs = rag_engine.get_indexed_documents()
    return {
        "status": "online",
        "system": "Santos Pegasus Intelligence Agent",
        "indexed_documents_count": len(docs),
        "indexed_chunks_count": len(rag_engine.chunks),
        "version": "2.0.0",
        "oci_region": "sa-saopaulo-1 (Oracle Cloud Infrastructure)"
    }


@app.post("/api/chat")
def chat_endpoint(request: ChatQueryRequest):
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="A pergunta não pode estar vazia.")

    METRICS["total_queries"] += 1
    start_ts = time.time()
    
    result = rag_engine.generate_response(
        user_query=request.query,
        category_filter=request.category
    )
    
    elapsed_ms = round((time.time() - start_ts) * 1000, 2)
    result["response_time_ms"] = elapsed_ms
    return result


@app.get("/api/documents")
def get_documents():
    docs = rag_engine.get_indexed_documents()
    categories = sorted(list(set(d["category"] for d in docs))) if docs else []
    formats = sorted(list(set(d["format"] for d in docs))) if docs else []
    return {
        "documents": docs,
        "total_documents": len(docs),
        "total_chunks": len(rag_engine.chunks),
        "categories": ["Todos"] + categories,
        "supported_formats": ["PDF", "Word", "Excel", "PowerPoint", "Markdown", "CSV", "JSON", "HTML"]
    }


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")

    file_path = os.path.join(SAMPLE_DIR, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    rag_engine.reload_knowledge_base()
    METRICS["uploads_count"] += 1

    return {
        "message": f"Arquivo '{filename}' enviado e indexado com sucesso!",
        "filename": filename,
        "size_bytes": os.path.getsize(file_path),
        "indexed_chunks": len(rag_engine.chunks)
    }


@app.get("/api/metrics")
def get_metrics():
    uptime_seconds = int(time.time() - METRICS["start_time"])
    docs = rag_engine.get_indexed_documents()
    
    cat_counts = {}
    for d in docs:
        c = d["category"]
        cat_counts[c] = cat_counts.get(c, 0) + 1

    return {
        "total_queries": METRICS["total_queries"],
        "active_documents": len(docs),
        "indexed_chunks": len(rag_engine.chunks),
        "uploads_count": METRICS["uploads_count"],
        "uptime_seconds": uptime_seconds,
        "category_distribution": cat_counts,
        "supported_formats_count": 8
    }

# Servir arquivos estáticos do frontend (index.html, style.css, app.js) sem interferir nas rotas POST /api
@app.get("/", response_class=HTMLResponse)
def read_index():
    index_file = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse("<h1>Santos Pegasus Agent API Online</h1>")

@app.get("/style.css")
def get_style():
    css_file = os.path.join(BASE_DIR, "style.css")
    if os.path.exists(css_file):
        return FileResponse(css_file, media_type="text/css")
    raise HTTPException(status_code=404, detail="style.css não encontrado")

@app.get("/app.js")
def get_js():
    js_file = os.path.join(BASE_DIR, "app.js")
    if os.path.exists(js_file):
        return FileResponse(js_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js não encontrado")

