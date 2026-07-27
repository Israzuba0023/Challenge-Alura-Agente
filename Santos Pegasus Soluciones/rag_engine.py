"""
Motor RAG e Busca Semântica Híbrida para o Agente Corporativo Santos Pegasus Soluciones.
"""

import os
import re
import math
from typing import List, Dict, Any, Tuple, Optional
from document_parsers import MultiFormatDocumentParser, DocumentChunk

try:
    import google.generativeai as genai
except ImportError:
    genai = None


class RAGEngine:
    def __init__(self, docs_dir: str, sample_dir: str):
        self.docs_dir = docs_dir
        self.sample_dir = sample_dir
        self.parser = MultiFormatDocumentParser()
        self.chunks: List[DocumentChunk] = []
        self.documents_meta: List[Dict[str, Any]] = []
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        
        if self.gemini_api_key and genai is not None:
            try:
                genai.configure(api_key=self.gemini_api_key)
            except Exception as e:
                print(f"[Warning] Failed to configure Gemini API: {e}")

        self.reload_knowledge_base()

    def reload_knowledge_base(self):
        """Varre e indexa todos os arquivos em Docs/ e sample_data/."""
        self.chunks = []
        self.documents_meta = []
        file_paths = []

        # Listar diretório Docs
        if os.path.exists(self.docs_dir):
            for fn in os.listdir(self.docs_dir):
                fp = os.path.join(self.docs_dir, fn)
                if os.path.isfile(fp):
                    file_paths.append(fp)

        # Listar diretório sample_data
        if os.path.exists(self.sample_dir):
            for fn in os.listdir(self.sample_dir):
                fp = os.path.join(self.sample_dir, fn)
                if os.path.isfile(fp):
                    file_paths.append(fp)

        for fp in file_paths:
            self._ingest_file(fp)

    def _ingest_file(self, file_path: str):
        fn = os.path.basename(file_path)
        parsed_chunks = self.parser.parse_file(file_path)
        if not parsed_chunks:
            return

        cat = parsed_chunks[0].category if parsed_chunks else "Geral"
        fmt = parsed_chunks[0].file_format if parsed_chunks else "Desconhecido"

        self.chunks.extend(parsed_chunks)
        self.documents_meta.append({
            "filename": fn,
            "category": cat,
            "format": fmt,
            "total_chunks": len(parsed_chunks),
            "size_bytes": os.path.getsize(file_path),
            "path": file_path
        })

    def get_indexed_documents(self) -> List[Dict[str, Any]]:
        return self.documents_meta

    def search_chunks(self, query: str, category_filter: Optional[str] = None, top_k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        if not self.chunks:
            return []

        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        scored_chunks: List[Tuple[DocumentChunk, float]] = []

        for chunk in self.chunks:
            if category_filter and category_filter.lower() != "todos":
                if category_filter.lower() not in chunk.category.lower():
                    continue

            content_terms = self._tokenize(chunk.content)
            if not content_terms:
                continue

            # TF-IDF / BM25 simplificado
            score = 0.0
            for term in query_terms:
                if term in content_terms:
                    tf = content_terms.count(term) / len(content_terms)
                    doc_freq = sum(1 for c in self.chunks if term in self._tokenize(c.content))
                    idf = math.log((len(self.chunks) + 1) / (doc_freq + 1)) + 1.0
                    score += tf * idf

            # Bônus para correspondência no título do documento ou metadados
            doc_name_terms = self._tokenize(chunk.document_name)
            for term in query_terms:
                if term in doc_name_terms:
                    score += 0.5

            if score > 0.001:
                scored_chunks.append((chunk, score))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]

    def generate_response(self, user_query: str, category_filter: Optional[str] = None) -> Dict[str, Any]:
        """Busca contexto e sintetiza resposta com citações explicativas."""
        results = self.search_chunks(user_query, category_filter=category_filter, top_k=5)

        citations = []
        context_blocks = []

        for idx, (chunk, score) in enumerate(results):
            cite_id = idx + 1
            citation_info = {
                "id": cite_id,
                "document_name": chunk.document_name,
                "category": chunk.category,
                "format": chunk.file_format,
                "page_number": chunk.page_number,
                "section": chunk.section or f"Chunk #{cite_id}",
                "snippet": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                "relevance_score": round(score, 3)
            }
            citations.append(citation_info)
            context_blocks.append(f"--- [FONTE #{cite_id}] Arquivo: {chunk.document_name} | Categoria: {chunk.category} | Pág: {chunk.page_number or 'N/A'} ---\n{chunk.content}")

        context_str = "\n\n".join(context_blocks)

        # Tentativa de chamada ao Gemini se houver chave API
        if self.gemini_api_key and genai is not None:
            try:
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = f"""Você é o Agente Inteligente Corporativo da empresa **Santos Pegasus Soluciones**.
Sua missão é responder à dúvida do colaborador com extrema precisão, tom profissional, didático e amigável.

DOCUMENTOS INTERNOS ENCONTRADOS NO CONTEXTO:
{context_str if context_str else "Nenhum documento específico encontrado."}

PERGUNTA DO COLABORADOR:
{user_query}

DIRETRIZES DE RESPOSTA:
1. Responda em Português do Brasil (PT-BR) de forma completa, estruturada (use listas, negritos e tópicos).
2. Sempre cite as fontes de informação indicando a tag da fonte entre colchetes, por exemplo [FONTE #1] ou [Guia Oficial de Back-end, pág. 3].
3. Se o documento contiver código ou procedimentos técnicos, apresente-os formatados em blocos de código markdown.
4. Se o contexto não contiver informações suficientes, responda com o que sabe e indique gentilmente onde a informação oficial pode ser consultada.
"""
                response = model.generate_content(prompt)
                if response and response.text:
                    return {
                        "answer": response.text,
                        "citations": citations,
                        "query": user_query,
                        "used_llm": "Gemini 1.5 Flash"
                    }
            except Exception as e:
                print(f"[Warning] LLM call failed, falling back to local synthesis: {e}")

        # Sintetizador Local Inteligente (sem depender de API externa)
        answer_markdown = self._synthesize_local_response(user_query, results, citations)
        return {
            "answer": answer_markdown,
            "citations": citations,
            "query": user_query,
            "used_llm": "Motor RAG Pegasus (Sintetizador Local)"
        }

    def _synthesize_local_response(self, query: str, results: List[Tuple[DocumentChunk, float]], citations: List[Dict[str, Any]]) -> str:
        if not results:
            return f"Olá! Não encontrei informações específicas nos documentos internos sobre **'{query}'**.\n\nSugiro verificar se a dúvida se encaixa em uma das categorias principais (Engenharia Back-end, Front-end, Arquitetura, Onboarding, Resiliência, RH ou Financeiro) ou realizar o upload do documento correspondente na Central de Documentos."

        top_chunk = results[0][0]
        lines = []
        lines.append(f"### Resposta Oficial — Santos Pegasus Soluciones\n")
        lines.append(f"Com base na consulta aos documentos corporativos no domínio **{top_chunk.category}**, identifiquei as seguintes diretrizes:\n")

        for idx, (chunk, score) in enumerate(results[:3]):
            lines.append(f"#### {idx+1}. Informações do documento `{chunk.document_name}` [{chunk.file_format}]")
            lines.append(f"*{chunk.content}*\n")
            lines.append(f"> **Referência:** Fonte #{idx+1} — Página {chunk.page_number or 1} | Categoria: {chunk.category}\n")

        lines.append("---\n")
        lines.append("### 📚 Citações e Fontes Consultadas:")
        for cite in citations:
            lines.append(f"- **[{cite['id']}] {cite['document_name']}** ({cite['format']}) — {cite['category']} | Página: {cite['page_number'] or 'N/A'}")

        return "\n".join(lines)

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r"\w+", text.lower())
        stopwords = {"de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "com", "não", "uma", "os", "no", "se", "na", "por", "mais", "as", "dos", "como", "mas", "ao", "ele", "das", "à", "seu", "sua", "ou", "quando", "muito", "nos", "já", "eu", "também", "só", "pelo", "pela", "até", "isso", "ela", "entre", "depois", "sem", "mesmo", "aos", "seus", "quem", "nas", "me", "esse", "eles", "você", "essa", "num", "nem", "suas", "meu", "às", "minha", "numa", "pelos", "elas", "qual", "nós", "lhe", "deles", "essas", "esses", "pelas", "este", "dele", "tu", "te", "vocês", "vos", "lhes", "meus", "minhas", "teu", "tua", "teus", "tuas", "nosso", "nossa", "nossos", "nossas", "dela", "delas", "esta", "estes", "estas", "aquele", "aquela", "aqueles", "aquelas", "isto", "aquilo", "estou", "está", "estamos", "estão", "estive", "esteve", "estivemos", "estiveram", "estava", "estávamos", "estavam", "estivera", "estivéramos", "esteja", "estejamos", "estejam", "estivesse", "estivéssemos", "estivessem", "estiver", "estivermos", "estiverem", "hei", "há", "havemos", "hão", "houve", "houvemos", "houveram", "houvera", "houvéramos", "haja", "hajamos", "hajam", "houvesse", "houvéssemos", "houvessem", "houver", "houvermos", "houverem", "houverei", "houverá", "houveremos", "houverão", "houveria", "houveríamos", "houveriam", "sou", "somos", "são", "era", "éramos", "eram", "fui", "foi", "fomos", "foram", "fora", "fôramos", "seja", "sejamos", "sejam", "fosse", "fôssemos", "fossem", "for", "formos", "forem", "serei", "será", "seremos", "serão", "seria", "seríamos", "seriam", "tenho", "tem", "temos", "têm", "tinha", "tínhamos", "tinham", "tive", "teve", "tivemos", "tiveram", "tivera", "tivéramos", "tenha", "tenhamos", "tenham", "tivesse", "tivéssemos", "tivessem", "tiver", "tivermos", "tiverem", "terei", "terá", "teremos", "terão", "teria", "teríamos", "teriam"}
        return [w for w in words if len(w) > 2 and w not in stopwords]
