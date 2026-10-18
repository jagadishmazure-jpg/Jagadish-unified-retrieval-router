"""Thin Streamlit demo for the unified retrieval router (lazy import)."""

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    raise SystemExit("pip install streamlit, then run: streamlit run demo/app.py") from None

from router import audit, demo_helpers, govern, router

st.title("Unified Retrieval Router")
st.caption("One question -> SQL and/or docs, with governance enforced at routing time.")

role = st.selectbox("Role", ["analyst", "support_lead", "hr_admin"])
question = st.text_input("Question", "How many open tickets do we have?")

if st.button("Ask"):
    log = audit.new_log()
    try:
        res = router.answer(question, role=role, log=log)
        st.markdown(demo_helpers.format_answer(res))
    except govern.AccessDenied as e:
        st.error(f"Denied: {e} (policy {e.policy_id})")

st.subheader("Try these")
for q, r in demo_helpers.sample_questions():
    if st.button(f"[{r}] {q}"):
        st.session_state["q"] = q
