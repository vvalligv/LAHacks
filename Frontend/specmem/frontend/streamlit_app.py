import os
from typing import Any

import requests
import streamlit as st


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

SAMPLE_MEMORY = {
    "project_id": "demo-project",
    "bug_title": "Login fails after token refresh",
    "description": "User gets logged out after refresh token expires.",
    "file_path": "auth/token.py",
    "module": "auth",
    "failed_fixes": ["Increased timeout"],
    "root_cause": "Async race condition during token refresh",
    "final_fix": "Refresh token before retrying protected request",
    "tags": ["auth", "async", "token"],
}


def api_get(path: str, params: dict[str, Any] | None = None) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    try:
        response = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=10)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as exc:
        return None, format_request_error(exc)
    except ValueError:
        return None, "Backend returned a non-JSON response."


def api_post(path: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    try:
        response = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=30)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as exc:
        return None, format_request_error(exc)
    except ValueError:
        return None, "Backend returned a non-JSON response."


def format_request_error(exc: requests.exceptions.RequestException) -> str:
    response = getattr(exc, "response", None)
    if response is None:
        return f"Could not reach backend at {BACKEND_URL}: {exc}"

    try:
        detail = response.json()
    except ValueError:
        detail = response.text

    return f"Backend error {response.status_code}: {detail}"


def split_lines(value: str) -> list[str]:
    return [item.strip() for item in value.replace(",", "\n").splitlines() if item.strip()]


def extract_memories(data: dict[str, Any] | list[Any] | None) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("memories", "items", "results", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def show_memory_card(memory: dict[str, Any]) -> None:
    title = memory.get("bug_title", "Untitled bug")
    module = memory.get("module") or "unknown module"
    file_path = memory.get("file_path") or "unknown file"

    with st.container(border=True):
        st.subheader(title)
        st.caption(f"{module} - {file_path}")
        st.write(memory.get("description", "No description provided."))

        failed_fixes = memory.get("failed_fixes") or []
        if failed_fixes:
            st.warning("Failed fixes: " + ", ".join(map(str, failed_fixes)))

        root_cause = memory.get("root_cause")
        final_fix = memory.get("final_fix")
        if root_cause:
            st.write(f"**Root cause:** {root_cause}")
        if final_fix:
            st.success(f"Final fix: {final_fix}")

        tags = memory.get("tags") or []
        if tags:
            st.caption("Tags: " + ", ".join(map(str, tags)))


def show_token_savings(token_savings: dict[str, Any] | None) -> None:
    if not token_savings:
        st.info("No token savings data returned.")
        return

    before = token_savings.get("before_tokens", "N/A")
    after = token_savings.get("after_tokens", "N/A")
    savings = token_savings.get("savings_percent", "N/A")

    col1, col2, col3 = st.columns(3)
    col1.metric("Before", before)
    col2.metric("After", after)
    col3.metric("Savings", f"{savings}%")


st.set_page_config(
    page_title="SpecMem — Memory-Powered Debugging Agent",
    layout="wide",
)

st.title("SpecMem — Memory-Powered Debugging Agent")
st.caption("A judge-facing dashboard that talks only to the FastAPI backend.")

with st.sidebar:
    st.header("Backend")
    st.code(BACKEND_URL)
    if st.button("Refresh Health"):
        st.session_state["health_refresh"] = True


st.header("A. Backend Health")
health_data, health_error = api_get("/health")
if health_error:
    st.error(health_error)
else:
    st.success("Backend is connected.")
    if health_data:
        st.json(health_data)


st.header("Demo Shortcut")
# st.write("Use this for the judge demo before running the debug query.")
if st.button("Load Sample Demo Memory", type="primary"):
    data, error = api_post("/memory", SAMPLE_MEMORY)
    if error:
        st.error(error)
    else:
        st.success("Sample demo memory saved for project `demo-project`.")
        st.json(data)


st.header("B. Add Bug Memory")
with st.form("add_memory_form"):
    col1, col2 = st.columns(2)
    with col1:
        project_id = st.text_input("project_id", value="demo-project")
        bug_title = st.text_input("bug_title")
        file_path = st.text_input("file_path")
        module = st.text_input("module")
    with col2:
        tags = st.text_area("tags", placeholder="auth, async, token")
        failed_fixes = st.text_area("failed_fixes", placeholder="One failed fix per line")

    description = st.text_area("description")
    root_cause = st.text_area("root_cause")
    final_fix = st.text_area("final_fix")

    save_memory = st.form_submit_button("Save Memory")

if save_memory:
    payload = {
        "project_id": project_id,
        "bug_title": bug_title,
        "description": description,
        "file_path": file_path,
        "module": module,
        "failed_fixes": split_lines(failed_fixes),
        "root_cause": root_cause,
        "final_fix": final_fix,
        "tags": split_lines(tags),
    }
    data, error = api_post("/memory", payload)
    if error:
        st.error(error)
    else:
        st.success("Bug memory saved.")
        st.json(data)


st.header("C. Debug New Bug")
with st.form("debug_form"):
    debug_project_id = st.text_input("project_id", value="demo-project", key="debug_project_id")
    debug_query = st.text_area("query", value="Login fails again after refresh")
    debug_module = st.text_input("module optional", value="auth")
    debug_file_path = st.text_input("file_path optional", value="auth/token.py")
    run_debug = st.form_submit_button("Debug with SpecMem")

if run_debug:
    payload = {
        "project_id": debug_project_id,
        "query": debug_query,
        "module": debug_module or None,
        "file_path": debug_file_path or None,
    }
    data, error = api_post("/debug", payload)
    if error:
        st.error(error)
    elif isinstance(data, dict):
        st.subheader("AI Answer")
        st.write(data.get("answer", "No answer returned."))

        warning = data.get("failed_fix_warning")
        if warning:
            st.warning(warning)

        st.subheader("Similar Bugs")
        similar_bugs = data.get("similar_bugs") or []
        if similar_bugs:
            for bug in similar_bugs:
                if isinstance(bug, dict):
                    show_memory_card(bug)
        else:
            st.info("No similar bugs returned.")

        st.subheader("Token Savings")
        show_token_savings(data.get("token_savings"))
    else:
        st.error("Unexpected response from backend.")


st.header("D. Check Proposed Fix")
with st.form("check_form"):
    check_project_id = st.text_input("project_id", value="demo-project", key="check_project_id")
    proposed_fix = st.text_area("proposed_fix", value="Increase timeout during token refresh")
    check_module = st.text_input("module optional", value="auth", key="check_module")
    run_check = st.form_submit_button("Check Fix")

if run_check:
    payload = {
        "project_id": check_project_id,
        "proposed_fix": proposed_fix,
        "module": check_module or None,
    }
    data, error = api_post("/check", payload)
    if error:
        st.error(error)
    elif isinstance(data, dict):
        warning = data.get("warning")
        if warning:
            st.warning(warning)
        else:
            st.success("No matching failed fix found.")

        matched_failed_fix = data.get("matched_failed_fix")
        if matched_failed_fix:
            st.subheader("Matched Failed Fix")
            st.json(matched_failed_fix)
    else:
        st.error("Unexpected response from backend.")


st.header("E. Memory Browser")
with st.form("memory_browser_form"):
    browser_project_id = st.text_input("project_id", value="demo-project", key="browser_project_id")
    load_memories = st.form_submit_button("Load Memories")

if load_memories:
    data, error = api_get("/memory", params={"project_id": browser_project_id})
    if error:
        st.error(error)
    else:
        memories = extract_memories(data)
        if not memories:
            st.info("No memories found for this project.")
        for memory in memories:
            show_memory_card(memory)
