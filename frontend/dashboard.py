import streamlit as st
import requests
import time
import pandas as pd
import json

# --- Configuração ---
API_URL = "http://127.0.0.1:8000"
st.set_page_config(page_title="AI Dev Studio", page_icon="⚡", layout="wide")

# --- CSS Moderno ---
st.markdown("""
<style>
    /* Sidebar */
    section[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #dee2e6; }
    .project-item { padding: 8px; border-radius: 5px; cursor: pointer; color: #333; }
    .project-item:hover { background-color: #e9ecef; }
    
    /* Logs e Árvore */
    .tree-node { font-size: 0.9em; margin-left: 10px; }
    .log-entry { font-family: 'Courier New', monospace; font-size: 0.8em; color: #444; margin-bottom: 4px; border-bottom: 1px solid #eee; }
    .log-timestamp { color: #888; font-size: 0.75em; margin-right: 8px; }
    
    /* Chat Area */
    .stChatMessage { background-color: transparent; }
    .stChatMessage.user { background-color: #f0f2f6; }
</style>
""", unsafe_allow_html=True)

# --- Estado ---
if "job_id" not in st.session_state: st.session_state["job_id"] = None
if "messages" not in st.session_state: st.session_state["messages"] = []
if "selected_node" not in st.session_state: st.session_state["selected_node"] = None
if "last_log_count" not in st.session_state: st.session_state["last_log_count"] = 0

# --- Helpers ---
def get_structure(job_id):
    try:
        res = requests.get(f"{API_URL}/project-structure/{job_id}")
        return res.json() if res.status_code == 200 else None
    except: return None

def get_status(job_id):
    try:
        res = requests.get(f"{API_URL}/status/{job_id}")
        return res.json() if res.status_code == 200 else None
    except: return None

# ==============================================================================
# SIDEBAR
# ==============================================================================
with st.sidebar:
    st.title("⚡ AI Dev Studio")
    
    # 1. New Project
    with st.expander("🆕 New Project", expanded=not st.session_state["job_id"]):
        new_idea = st.text_area("What are we building?", height=100, placeholder="E.g. A CRM with Python...")
        if st.button("Start Building", type="primary", use_container_width=True):
            if new_idea:
                try:
                    res = requests.post(f"{API_URL}/plan/start", json={"initial_requirements": new_idea})
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state["job_id"] = data["job_id"]
                        st.session_state["messages"] = [{"role": "user", "content": new_idea}]
                        st.session_state["last_log_count"] = 0
                        st.rerun()
                except Exception as e: st.error(f"Error: {e}")

    st.divider()

    # 2. Load Project
    col_load, col_btn = st.columns([3, 1])
    job_input = col_load.text_input("Project ID", placeholder="UUID...", label_visibility="collapsed")
    if col_btn.button("📂"):
        st.session_state["job_id"] = job_input
        st.rerun()

    st.divider()

    # 3. Project Tree
    if st.session_state["job_id"]:
        st.caption(f"ID: `{st.session_state['job_id'][:8]}...`")
        structure = get_structure(st.session_state["job_id"])
        
        if structure and structure.get("modules"):
            st.markdown("### 📂 Architecture")
            for module in structure.get("modules", []):
                with st.expander(f"📦 {module.get('name', 'Module')}"):
                    for cls in module.get("classes", []):
                        cls_name = cls.get('name', 'Class')
                        if st.button(f"📄 {cls_name}", key=cls_name):
                            st.session_state["selected_node"] = f"{module['name']}/{cls_name}"
                            st.session_state["messages"].append({
                                "role": "system", 
                                "content": f"Context switched to: **{cls_name}**"
                            })
                            st.rerun()
        else:
            st.info("Waiting for Architecture...")

# ==============================================================================
# MAIN CHAT AREA
# ==============================================================================

if not st.session_state["job_id"]:
    st.info("👈 Start a new project to begin.")
    st.stop()

# Header
if st.session_state["selected_node"]:
    st.caption(f"Editing Context: {st.session_state['selected_node']}")
else:
    st.caption("General Context")

# Render History
chat_container = st.container()
with chat_container:
    for msg in st.session_state["messages"]:
        if msg["role"] == "system":
            st.caption(msg["content"])
        else:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

# --- LIVE LOG STREAMING LOGIC ---
# Buscamos o status atual para saber se há novos logs para mostrar
status_data = get_status(st.session_state["job_id"])
current_logs = status_data.get("tasks", []) if status_data else []
total_logs = len(current_logs)
new_logs_count = total_logs - st.session_state["last_log_count"]

# Se houver logs novos ou se estivermos rodando, mostramos o container de status
is_running = status_data and status_data.get("status") in ["IN_PROGRESS", "EXECUTING", "PLANNING"]

if is_running or new_logs_count > 0:
    # Cria uma caixa de status que se parece com um terminal
    with st.status("🤖 Factory Activity", expanded=is_running) as status_box:
        # Renderiza apenas os logs mais recentes (ou todos se quiser)
        # Filtramos para mostrar steps e tasks
        recent_logs = current_logs[-20:] # Mostra os ultimos 20 para não travar
        
        for log in recent_logs:
            # Formata log baseado no tipo
            if log['task_name'] == "Agent Thinking...":
                st.markdown(f":brain: `{log['details'][:120]}...`")
            elif log['status'] == "SUCCESS":
                st.markdown(f"✅ **{log['task_name']}**: Completed")
            elif log['status'] == "FAILED":
                st.markdown(f"❌ **{log['task_name']}**: Failed")
            else:
                st.markdown(f"⚙️ {log['task_name']}")
        
        # Atualiza contagem
        st.session_state["last_log_count"] = total_logs

# Input Area
if prompt := st.chat_input("Instruções..."):
    # 1. Add User Message
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with chat_container:
        with st.chat_message("user"):
            st.markdown(prompt)

    # 2. Logic Handler
    if "approv" in prompt.lower() or "build" in prompt.lower():
        # APROVAÇÃO (Assíncrona - Inicia Factory)
        try:
            requests.post(f"{API_URL}/plan/approve/{st.session_state['job_id']}", json={})
            st.session_state["messages"].append({"role": "system", "content": "🚀 **Factory Started!** Watch the logs below."})
            st.rerun()
        except Exception as e: st.error(f"API Error: {e}")
        
    else:
        # CHAT (Síncrono - PM)
        # Mostramos um spinner diferente enquanto aguarda o PM
        with st.status("Product Manager is thinking...", expanded=True):
            try:
                res = requests.post(
                    f"{API_URL}/plan/chat/{st.session_state['job_id']}", 
                    json={"message": prompt}
                )
                if res.status_code == 200:
                    response = res.json()["response"]
                    st.session_state["messages"].append({"role": "assistant", "content": response})
                    st.rerun()
            except Exception as e:
                st.error(f"Chat Error: {e}")

# Auto-Refresh para "Streaming"
if is_running:
    time.sleep(2) # Polling de 2 segundos
    st.rerun()