# Documentação dos Endpoints de Chat 🔧

Resumo curto para integração do frontend hospedado externamente.

---

## Endpoints principais

### POST /plan/chat/{job_id} ✅
- Descrição: recebe a mensagem do usuário, salva no histórico do job e dispara um debate síncrono entre os agentes de planning. As respostas dos agentes são persistidas.
- Request JSON: `{ "message": "texto do usuário" }`
- Response 200:
```json
{
  "messages": [
    { "id": 1, "job_id": "...", "sender": "user", "role": "user", "message": "...", "timestamp": "..." },
    { "id": 2, "job_id": "...", "sender": "product_manager", "role": "agent", "message": "...", "timestamp": "..." }
  ],
  "latest": [
    { "role": "product_manager", "message": "..." },
    { "role": "architect", "message": "..." }
  ]
}
```

### GET /plan/chat/{job_id} ✅
- Descrição: retorna o histórico completo do chat (ordenado do mais antigo para o mais recente).
- Response 200:
```json
{ "messages": [ { "id":..., "job_id":"...", "sender":"...", "role":"...", "message":"...", "timestamp":"..." } ] }
```

### Endpoints auxiliares
- **POST /plan/start** — cria novo job e retorna `{ "job_id": "...", "status": "PLANNING" }`.
- **POST /plan/approve/{job_id}** — inicia pipeline em background: `{ "status": "Build Started" }`.
- **GET /status/{job_id}** — retorna logs e status: `{ "job_id": "...", "status": "...", "tasks": [...] }`.

---

## Observações importantes ⚠️
- CORS está habilitado (allow_origins="*"), portanto o frontend público pode acessar os endpoints diretamente.
- Recomenda-se criar o job primeiro via **POST /plan/start** antes de usar `/plan/chat/{job_id}`.
- Histórico de chat é persistido em `crew_state.db` na tabela `chat_messages` com campos: `id, job_id, sender, role, message, timestamp`.
- Autenticação: não há autenticação por padrão; considere adicionar se necessário para produção.
- Atualizações em tempo real: atualmente há polling via `GET /plan/chat/{job_id}`. Para push em tempo real, vale a pena implementar SSE ou WebSocket no backend.

---

## Exemplos de uso

### curl — enviar mensagem (POST)
```bash
curl -X POST "https://<BACKEND_HOST>/plan/chat/<JOB_ID>" \
  -H "Content-Type: application/json" \
  -d '{ "message": "Precisamos priorizar autenticação." }'
```

### curl — buscar histórico (GET)
```bash
curl "https://<BACKEND_HOST>/plan/chat/<JOB_ID>"
```

### Fetch (JS) — enviar mensagem
```js
fetch(`https://<BACKEND_HOST>/plan/chat/${jobId}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: 'Vamos priorizar API de login' })
}).then(r => r.json()).then(data => console.log(data))
```

### Axios (JS) — enviar mensagem
```js
axios.post(`https://<BACKEND_HOST>/plan/chat/${jobId}`, { message: 'Vamos priorizar API de login' })
  .then(res => console.log(res.data))
```

### Polling simples (atualizar a cada 3s)
```js
setInterval(() => {
  fetch(`https://<BACKEND_HOST>/plan/chat/${jobId}`).then(r => r.json()).then(updateUI)
}, 3000)
```

---

## Dicas rápidas 💡
- Substitua `<BACKEND_HOST>` pelo host público/URL do backend (ex.: `api.seudominio.com`).
- Para reduzir ruído no frontend, filtre mensagens com `role == 'agent'` ou aplique regras de exibição conforme necessário.
- Posso adicionar exemplos em TypeScript ou instruções para SSE/WebSocket caso precise de push em tempo real.

---

Arquivo gerado automaticamente para facilitar a integração do frontend externo.
