"""DevHelper-AI Streamlit UI: upload ZIP, inspect, run agent on it."""
import atexit
import os
import shutil
import tempfile
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
from agent_core import run_agent
from context_utils import build_context_summary, build_project_tree
from zip_utils import ZipError, create_project_zip, detect_project_root, safe_extract_zip

st.set_page_config(page_title="DevHelper-AI", layout="wide")
st.title("DevHelper-AI")
st.markdown("> Upload your project and describe the coding problem.")

def _cleanup(path: str):
    try:
        if path and os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

if "work_dir" not in st.session_state:
    st.session_state.work_dir = tempfile.mkdtemp(prefix="devhelper-")
    atexit.register(_cleanup, st.session_state.work_dir)
if "project_root" not in st.session_state:
    st.session_state.project_root = None
if "extracted_files" not in st.session_state:
    st.session_state.extracted_files = []
if "zip_name" not in st.session_state:
    st.session_state.zip_name = None
if "last_result" not in st.session_state:
    st.session_state.last_result = None

api_key_present = bool(os.environ.get("GEMINI_API_KEY"))
with st.sidebar:
    st.header("Environment")
    if api_key_present:
        st.success("GEMINI_API_KEY is configured.")
    else:
        st.error("GEMINI_API_KEY is missing. Add it to .env.")
    if st.session_state.project_root:
        st.caption(f"Project root: {st.session_state.project_root}")
    if st.button("Clear uploaded project"):
        _cleanup(st.session_state.work_dir)
        st.session_state.work_dir = tempfile.mkdtemp(prefix="devhelper-")
        st.session_state.project_root = None
        st.session_state.extracted_files = []
        st.session_state.zip_name = None
        st.session_state.last_result = None
        st.rerun()

uploaded = st.file_uploader("Upload a project ZIP file", type=["zip"])
if uploaded is not None:
    if st.session_state.zip_name != uploaded.name:
        _cleanup(st.session_state.work_dir)
        st.session_state.work_dir = tempfile.mkdtemp(prefix="devhelper-")
        try:
            zip_bytes = uploaded.getvalue()
            extracted = safe_extract_zip(zip_bytes, st.session_state.work_dir)
            root = detect_project_root(st.session_state.work_dir)
            st.session_state.project_root = root
            st.session_state.extracted_files = extracted
            st.session_state.zip_name = uploaded.name
            st.session_state.last_result = None
        except ZipError as e:
            st.error(f"Could not use that ZIP file: {e}")
        except Exception:
            st.error("Extraction failed. Please check the file and try again.")

if st.session_state.project_root:
    st.success(f"Extracted '{st.session_state.zip_name}' OK.")
    with st.expander("Project structure", expanded=True):
        try:
            tree = build_project_tree(st.session_state.project_root)
            st.text("\n".join(tree))
        except OSError:
            st.error("Could not list project files.")
    with st.expander("Project context summary"):
        try:
            st.text(build_context_summary(st.session_state.project_root))
        except OSError:
            st.error("Could not summarize project files.")
else:
    st.info("No project uploaded yet. Upload a .zip file to begin.")

st.subheader("Coding / debugging request")
user_request = st.text_area("Describe what you want the agent to do", height=120)
analyze = st.button("Analyze / Fix", type="primary")

if analyze:
    if not st.session_state.project_root:
        st.error("Please upload a project ZIP file first.")
    elif not user_request.strip():
        st.error("Please enter a coding request.")
    elif not api_key_present:
        st.error("GEMINI_API_KEY is not configured.")
    else:
        root = st.session_state.project_root
        status = st.status("Agent working...", expanded=True)
        result = None
        try:
            result = run_agent(
                user_request.strip(),
                working_directory=root,
                on_event=lambda ev: status.write(ev.message),
            )
        except RuntimeError as e:
            status.update(label="Agent failed", state="error")
            st.error(f"Configuration error: {e}")
        except Exception as e:
            status.update(label="Agent failed", state="error")
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                st.error("Gemini rate limit reached. Wait a minute and retry.")
            elif "API_KEY" in msg or "INVALID_ARGUMENT" in msg:
                st.error("Gemini rejected the request. Check your API key.")
            else:
                st.error(f"Agent error: {msg[:500]}")
        if result is not None:
            status.update(label="Agent finished", state="complete")
            st.session_state.last_result = result
            st.subheader("AI analysis")
            st.markdown(result.final_text or "_No text returned._")
            st.caption(f"Iterations: {result.iterations_used}")
            if result.hit_max_iterations:
                st.warning("Hit iteration limit before final answer.")
            st.subheader("Changed files")
            if result.writes:
                for w in result.writes:
                    st.success(f"{w['file_path']}: {w['result']}")
            else:
                st.info("No files were modified by this run.")
            with st.expander("Agent activity log"):
                for ev in result.events:
                    st.text(f"[{ev.kind}] {ev.message}")

# Download the (possibly fixed) project. Rendered outside the Analyze block
# so it survives subsequent Streamlit reruns via session_state.
if st.session_state.project_root:
    st.subheader("Download project")
    base = (st.session_state.zip_name or "project").rsplit(".", 1)[0]
    changed = bool(
        st.session_state.last_result and st.session_state.last_result.writes
    )
    if changed:
        st.caption(
            f"Agent modified {len(st.session_state.last_result.writes)} "
            "file(s) — the download includes those fixes."
        )
    else:
        st.caption("Download the current project files as a ZIP.")
    try:
        zip_bytes = create_project_zip(st.session_state.project_root)
        st.download_button(
            label="Download project ZIP",
            data=zip_bytes,
            file_name=f"{base}-fixed.zip" if changed else f"{base}.zip",
            mime="application/zip",
        )
    except ZipError as e:
        st.error(f"Could not build download: {e}")
    except Exception:
        st.error("Could not build the project download.")

