import streamlit as st
import requests
import time
import pandas as pd

API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Factory Dashboard",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏭 AI Software Factory Dashboard")

# --- Sidebar ---
with st.sidebar:
    st.header("🚀 Control Center")

    if st.button("New Project", type="primary"):
        try:
            response = requests.post(f"{API_URL}/plan/start", json={})
            if response.status_code == 200:
                data = response.json()
                st.session_state["job_id"] = data["job_id"]
                st.session_state["status"] = "PLANNING"
                st.success(f"Started Job: {data['job_id']}")
                st.rerun()
            else:
                st.error(f"Failed to start: {response.text}")
        except Exception as e:
            st.error(f"Connection Error: {e}")

    st.divider()

    job_id_input = st.text_input("Load Job ID", value=st.session_state.get("job_id", ""))
    if st.button("Load"):
        if job_id_input:
            st.session_state["job_id"] = job_id_input
            st.rerun()

    if "job_id" in st.session_state:
        st.info(f"**Active Job ID:**\n`{st.session_state['job_id']}`")
        st.write(f"**Status:** {st.session_state.get('status', 'UNKNOWN')}")

# --- Main Logic ---

if "job_id" not in st.session_state:
    st.warning("👈 Start a New Project or Load an Existing Job ID to begin.")
    st.stop()

job_id = st.session_state["job_id"]

tab1, tab2 = st.tabs(["🧠 Planner Agent (Discovery)", "🏭 Factory Floor (Build Monitor)"])

# --- Tab 1: Planner Agent ---
with tab1:
    st.subheader("Interactive Planning Phase")

    # Check status first to see if we are still planning
    try:
        status_res = requests.get(f"{API_URL}/status/{job_id}")
        if status_res.status_code == 200:
            status_data = status_res.json()
            st.session_state["status"] = status_data["status"]
    except:
        pass

    # Chat Interface
    # Load history if available
    # Note: The API /plan/chat returns history on POST, but we might want to just fetch current state.
    # Currently app.py doesn't have a GET /chat history endpoint, but we can rely on local session state
    # or the fact that /plan/chat response includes history.
    # Ideally we should have fetched history.
    # For now, let's store chat history in session state.

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if st.session_state.get("status") == "PLANNING":
        if prompt := st.chat_input("Describe your software requirements..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Product Manager is thinking..."):
                    try:
                        res = requests.post(f"{API_URL}/plan/chat/{job_id}", json={"message": prompt})
                        if res.status_code == 200:
                            data = res.json()
                            response_text = data["response"]
                            st.markdown(response_text)
                            st.session_state.messages.append({"role": "assistant", "content": response_text})
                            # Update full history from server just in case
                            # st.session_state.messages = data["history"]
                        else:
                            st.error("Failed to send message.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        st.divider()
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("✅ APPROVE PLAN", type="primary", use_container_width=True):
                with st.spinner("Approving and starting build..."):
                    try:
                        res = requests.post(f"{API_URL}/plan/approve/{job_id}", json={})
                        if res.status_code == 200:
                            st.success("Plan Approved! Factory started.")
                            st.session_state["status"] = "IN_PROGRESS"
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Approval failed: {res.text}")
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        st.info("Plan approved. Factory is executing.")

# --- Tab 2: Factory Floor ---
with tab2:
    st.subheader("Live Build Monitor")

    if st.session_state.get("status") == "PLANNING":
        st.info("Waiting for plan approval...")
    else:
        placeholder = st.empty()

        # Auto-refresh loop
        # In Streamlit, a simple way to 'poll' is using st.empty and rerun,
        # but rerun refreshes the whole page which resets chat input.
        # Better to use a container that updates if we are in a 'while' loop,
        # but Streamlit runs script top-to-bottom.
        # Standard pattern: use st.rerun() with a sleep at the end if we want continuous updates,
        # but that blocks interaction in Tab 1.
        # We will just fetch once per render and provide a manual refresh or
        # rely on st.fragment (if available in newer streamlit) or just button.
        # User requested "Auto-Refresh: Use st.empty() or a loop to poll ... every 2 seconds".
        # A blocking loop prevents Sidebar interaction.
        # We will implement a loop that breaks if user interacts?
        # Actually, st.autorefresh is a custom component.
        # We will use a simple button for manual refresh + auto refresh logic if 'active'.

        # Simple polling loop within the container for visual effect if 'status' is running

        refresh = st.checkbox("Auto-Refresh Log", value=True)

        if refresh:
            time.sleep(2)
            st.rerun()

        try:
            status_res = requests.get(f"{API_URL}/status/{job_id}")
            if status_res.status_code == 200:
                status_data = status_res.json()
                current_status = status_data["status"]
                tasks = status_data["tasks"]

                # Status Badge
                color = "blue"
                if current_status == "SUCCESS": color = "green"
                elif current_status == "FAILED": color = "red"

                st.markdown(f"### Status: :{color}[{current_status}]")

                # Task Log
                if tasks:
                    df = pd.DataFrame(tasks)
                    st.dataframe(
                        df[["timestamp", "task_name", "status", "version", "details"]],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.write("No tasks logged yet.")

                # Artifacts
                if current_status == "SUCCESS":
                    st.success("Build Complete!")
                    st.write(f"**Artifacts Location:** `output/{job_id}/`")
                    # Ideally allow download zip, but path display is requested.

            else:
                st.error("Could not fetch status.")
        except Exception as e:
            st.error(f"Connection Error: {e}")
