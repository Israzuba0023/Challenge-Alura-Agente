/**
 * Pegasus Intelligence Agent - Client Application Logic (SPA)
 * Santos Pegasus Soluciones
 */

document.addEventListener('DOMContentLoaded', () => {
    // Estado Global da Aplicação
    const state = {
        activeTab: 'chat-tab',
        categoryFilter: 'Todos',
        documents: [],
        citationsMap: {},
        metrics: {}
    };

    // Elementos do DOM
    const navItems = document.querySelectorAll('.nav-item');
    const tabContents = document.querySelectorAll('.tab-content');
    const categorySelect = document.getElementById('category-select');
    const chatMessages = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const queryInput = document.getElementById('query-input');
    const btnSend = document.getElementById('send-btn');
    const promptCards = document.querySelectorAll('.prompt-card');
    const btnReloadKb = document.getElementById('btn-reload-kb');

    // Upload & Drop Zone
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadStatus = document.getElementById('upload-status');
    const docsTableBody = document.getElementById('docs-table-body');

    // Modal
    const citationModal = document.getElementById('citation-modal');
    const modalBody = document.getElementById('modal-citation-body');
    const closeModalBtn = document.querySelector('.close-modal');

    // Inicialização
    initNavigation();
    initChat();
    initUpload();
    loadDocuments();
    loadMetrics();

    // 1. Navegação de Abas
    function initNavigation() {
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                const targetTab = item.getAttribute('data-tab');
                if (targetTab === state.activeTab) return;

                navItems.forEach(n => n.classList.remove('active'));
                tabContents.forEach(t => t.classList.remove('active'));

                item.classList.add('active');
                document.getElementById(targetTab).classList.add('active');
                state.activeTab = targetTab;

                // Atualizar dados de acordo com a aba ativada
                if (targetTab === 'docs-tab') loadDocuments();
                if (targetTab === 'metrics-tab') loadMetrics();
            });
        });

        categorySelect.addEventListener('change', (e) => {
            state.categoryFilter = e.target.value;
        });

        btnReloadKb.addEventListener('click', async () => {
            btnReloadKb.classList.add('fa-spin');
            await loadDocuments();
            await loadMetrics();
            setTimeout(() => btnReloadKb.classList.remove('fa-spin'), 600);
        });

        closeModalBtn.addEventListener('click', () => {
            citationModal.classList.remove('active');
        });

        citationModal.addEventListener('click', (e) => {
            if (e.target === citationModal) citationModal.classList.remove('active');
        });
    }

    // 2. Lógica do Chat
    function initChat() {
        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            handleSendQuery();
        });

        queryInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendQuery();
            }
        });

        promptCards.forEach(card => {
            card.addEventListener('click', () => {
                const prompt = card.getAttribute('data-prompt');
                queryInput.value = prompt;
                handleSendQuery();
            });
        });
    }

    async function handleSendQuery() {
        const query = queryInput.value.trim();
        if (!query) return;

        // Remover banner de boas-vindas na primeira mensagem
        const welcomeBanner = document.querySelector('.welcome-banner');
        if (welcomeBanner) welcomeBanner.style.display = 'none';

        // Renderizar mensagem do Usuário
        appendMessage('user', query);
        queryInput.value = '';
        btnSend.disabled = true;

        // Indicador de "Digitando..."
        const typingId = appendTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    category: state.categoryFilter
                })
            });

            const responseText = await response.text();
            let data;
            try {
                data = JSON.parse(responseText);
            } catch (e) {
                removeTypingIndicator(typingId);
                appendMessage('assistant', `⚠️ Erro do servidor (${response.status}): ${responseText || 'Resposta vazia.'}`);
                return;
            }

            removeTypingIndicator(typingId);

            if (response.ok) {
                appendMessage('assistant', data.answer, data.citations, data.used_llm, data.response_time_ms);
            } else {
                appendMessage('assistant', `⚠️ Erro ao consultar o agente: ${data.detail || 'Falha na resposta.'}`);
            }
        } catch (error) {
            removeTypingIndicator(typingId);
            appendMessage('assistant', `⚠️ Erro de conexão com o servidor FastAPI RAG: ${error.message}`);
        } finally {
            btnSend.disabled = false;
        }
    }

    function appendMessage(role, text, citations = [], llmName = '', latencyMs = null) {
        const messageRow = document.createElement('div');
        messageRow.className = `message-row ${role}`;

        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.innerHTML = role === 'user' ? '<i class="fa-solid fa-user"></i>' : '<i class="fa-solid fa-robot"></i>';

        const bubble = document.createElement('div');
        bubble.className = 'bubble';

        // Formatação em Markdown simples + código
        let formattedText = formatMarkdown(text);
        bubble.innerHTML = formattedText;

        // Adicionar Citações se existirem
        if (citations && citations.length > 0) {
            const citationsContainer = document.createElement('div');
            citationsContainer.className = 'citations-wrapper';
            
            let chipsHtml = '<div class="citations-header"><i class="fa-solid fa-bookmark"></i> Fontes Consultadas:</div>';
            citations.forEach(c => {
                const citeKey = `cite_${Date.now()}_${c.id}`;
                state.citationsMap[citeKey] = c;

                chipsHtml += `
                    <span class="citation-chip" onclick="window.openCitationModal('${citeKey}')">
                        <i class="fa-solid fa-file-lines"></i> [${c.id}] ${c.document_name} (${c.format})
                    </span>
                `;
            });
            citationsContainer.innerHTML = chipsHtml;
            bubble.appendChild(citationsContainer);
        }

        if (role === 'assistant' && latencyMs) {
            const footerMeta = document.createElement('div');
            footerMeta.style.cssText = 'font-size: 10px; color: #64748b; margin-top: 8px; text-align: right;';
            footerMeta.innerHTML = `<i class="fa-solid fa-bolt"></i> Resposta em ${latencyMs}ms • ${llmName}`;
            bubble.appendChild(footerMeta);
        }

        messageRow.appendChild(avatar);
        messageRow.appendChild(bubble);
        chatMessages.appendChild(messageRow);

        // Auto-scroll
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Highlighting de código se houver <pre><code>
        if (window.hljs) {
            bubble.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        }
    }

    function appendTypingIndicator() {
        const id = `typing_${Date.now()}`;
        const row = document.createElement('div');
        row.className = 'message-row assistant';
        row.id = id;

        row.innerHTML = `
            <div class="avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="bubble" style="display: flex; align-items: center; gap: 8px;">
                <span class="pulse-dot"></span>
                <span style="font-size: 13px; color: #94a3b8;">Consultando base vetorial e sintetizando resposta...</span>
            </div>
        `;
        chatMessages.appendChild(row);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return id;
    }

    function removeTypingIndicator(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    // Modal de Citação Global
    window.openCitationModal = (citeKey) => {
        const cite = state.citationsMap[citeKey];
        if (!cite) return;

        modalBody.innerHTML = `
            <div style="margin-bottom: 14px;">
                <h4 style="color: #00f2fe; font-size: 16px; margin-bottom: 4px;">${cite.document_name}</h4>
                <p style="font-size: 12px; color: #94a3b8;">
                    <strong>Formato:</strong> ${cite.format} | 
                    <strong>Categoria:</strong> ${cite.category} | 
                    <strong>Página/Seção:</strong> ${cite.page_number || cite.section || 'N/A'}
                </p>
            </div>
            <div style="background: rgba(0,0,0,0.4); border-radius: 8px; padding: 14px; border: 1px solid rgba(255,255,255,0.08); font-size: 13px; line-height: 1.6; color: #f8fafc;">
                <strong>Trecho Relevante Extraído:</strong><br><br>
                <em>"${cite.snippet}"</em>
            </div>
            <div style="margin-top: 14px; font-size: 11px; color: #64748b; text-align: right;">
                Relevância Vetorial: Score ${cite.relevance_score}
            </div>
        `;
        citationModal.classList.add('active');
    };

    // Formatação de Markdown simples
    function formatMarkdown(text) {
        if (!text) return '';
        let html = text
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/### (.*?)\n/g, '<h3>$1</h3>')
            .replace(/#### (.*?)\n/g, '<h4>$1</h4>')
            .replace(/ - (.*?)\n/g, '<li>$1</li>');

        html = html.replace(/\n\n/g, '<br><br>');
        return html;
    }

    // 3. Upload & Central de Documentos
    function initUpload() {
        dropZone.addEventListener('click', () => fileInput.click());

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#00f2fe';
            dropZone.style.background = 'rgba(0, 242, 254, 0.1)';
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.style.borderColor = 'rgba(99, 102, 241, 0.4)';
            dropZone.style.background = 'transparent';
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = 'rgba(99, 102, 241, 0.4)';
            dropZone.style.background = 'transparent';

            if (e.dataTransfer.files.length > 0) {
                uploadFile(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                uploadFile(e.target.files[0]);
            }
        });
    }

    async function uploadFile(file) {
        uploadStatus.innerHTML = `<span style="color: #00f2fe;"><i class="fa-solid fa-spinner fa-spin"></i> Indexando '${file.name}' na base vetorial RAG...</span>`;
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (response.ok) {
                uploadStatus.innerHTML = `<span style="color: #10b981;"><i class="fa-solid fa-circle-check"></i> ${data.message}</span>`;
                loadDocuments();
                loadMetrics();
            } else {
                uploadStatus.innerHTML = `<span style="color: #f43f5e;"><i class="fa-solid fa-circle-exclamation"></i> ${data.detail || 'Erro ao enviar arquivo.'}</span>`;
            }
        } catch (error) {
            uploadStatus.innerHTML = `<span style="color: #f43f5e;">Erro: ${error.message}</span>`;
        }
    }

    async function loadDocuments() {
        try {
            const res = await fetch('/api/documents');
            const data = await res.json();
            state.documents = data.documents || [];

            // Preencher tabela
            docsTableBody.innerHTML = '';
            state.documents.forEach(doc => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${doc.filename}</strong></td>
                    <td><span class="pill ${doc.format.toLowerCase()}">${doc.format}</span></td>
                    <td>${doc.category}</td>
                    <td>${doc.total_chunks} chunks</td>
                    <td>${(doc.size_bytes / 1024).toFixed(1)} KB</td>
                    <td><span class="badge success">Indexado</span></td>
                `;
                docsTableBody.appendChild(tr);
            });
        } catch (err) {
            console.error('Erro ao carregar documentos:', err);
        }
    }

    // 4. Dashboard & Métricas
    async function loadMetrics() {
        try {
            const res = await fetch('/api/metrics');
            const data = await res.json();

            document.getElementById('metric-queries').innerText = data.total_queries || 0;
            document.getElementById('metric-docs').innerText = data.active_documents || 0;
            document.getElementById('metric-chunks').innerText = data.indexed_chunks || 0;

            const distList = document.getElementById('category-distribution-list');
            distList.innerHTML = '';
            const cats = data.category_distribution || {};
            
            Object.keys(cats).forEach(c => {
                const li = document.createElement('li');
                li.innerHTML = `<span>${c}</span> <strong>${cats[c]} docs</strong>`;
                distList.appendChild(li);
            });
        } catch (err) {
            console.error('Erro ao carregar métricas:', err);
        }
    }
});
