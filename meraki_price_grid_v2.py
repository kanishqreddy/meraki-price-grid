"""
meraki_price_grid_v4.py
========================
Meraki Price Grid v4 — professional analytics dashboard with:
- Persistent authentication (stored in GitHub via API so accounts survive
  Streamlit Cloud restarts/redeploys — see SETUP NOTES below)
- 3 security questions per user for password reset
- Self-service "My Account" panel: any user can update their OWN username
  and password after re-verifying their 3 security answers
- Admin panel: create/delete users, change role, reset password, rename
- Extra filters: Brand, Manufacturer, Availability, sort options
- Polished, formal dashboard visuals with KPI highlights and discount table

============================================================
SETUP NOTES — READ BEFORE DEPLOYING
============================================================
Streamlit Community Cloud's filesystem is EPHEMERAL: any file your app
writes (like users.json) is WIPED whenever the app restarts, sleeps, or
redeploys. That means new users created through the Admin panel would
be lost on the next restart unless we store them somewhere permanent.

This version stores users.json inside your own GitHub repo using the
GitHub Contents API, so it persists exactly like your code and CSVs do.

To enable this, add the following to your Streamlit Cloud app's
"Secrets" (App settings -> Secrets):

    GITHUB_TOKEN = "ghp_yourPersonalAccessTokenHere"
    GITHUB_REPO = "yourusername/meraki-price-grid"
    GITHUB_USERS_PATH = "users.json"

How to get a GitHub token:
1. GitHub -> Settings -> Developer settings -> Personal access tokens
   -> Tokens (classic) -> Generate new token.
2. Give it "repo" scope (so it can read/write files in your repo).
3. Copy the token and paste it into Streamlit secrets as shown above.

If these secrets are NOT set, the app falls back to a local users.json
file — this works fine when running locally on your own PC, but on
Streamlit Cloud any accounts created will NOT survive a restart until
you add the secrets above.
============================================================

Usage:
    streamlit run meraki_price_grid_v4.py

Requires (same folder):
    buymeraki_all_categories_enriched.csv
    dragon_networks_products.csv
"""

import os
import json
import glob
import base64
import secrets
import string
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import bcrypt
import requests

USERS_FILE = "users.json"

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "lI$$aaWXoXGRMv"

SECURITY_QUESTIONS = [
    "What was the name of your first pet?",
    "What city were you born in?",
    "What is your mother's maiden name?",
    "What was the model of your first car?",
    "What elementary school did you attend?",
    "What was your childhood nickname?",
    "What is the name of your favourite teacher?",
    "What was the make of your first phone?",
]

NUM_SECURITY_QUESTIONS = 3


def _hash(value: str) -> str:
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt()).decode()


def _verify(value: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(value.encode(), hashed.encode())
    except Exception:
        return False


def _gen_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _github_configured():
    return all(k in st.secrets for k in ("GITHUB_TOKEN", "GITHUB_REPO", "GITHUB_USERS_PATH")) if hasattr(st, "secrets") else False


def _github_headers():
    return {
        "Authorization": f"token {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }


def _github_url():
    return f"https://api.github.com/repos/{st.secrets['GITHUB_REPO']}/contents/{st.secrets['GITHUB_USERS_PATH']}"


def _default_users():
    return {
        DEFAULT_ADMIN_USERNAME: {
            "password_hash": _hash(DEFAULT_ADMIN_PASSWORD),
            "role": "admin",
            "security": [],
        }
    }


def _load_users():
    if _github_configured():
        try:
            resp = requests.get(_github_url(), headers=_github_headers(), timeout=10)
            if resp.status_code == 200:
                content = base64.b64decode(resp.json()["content"]).decode()
                users = json.loads(content)
                for u in users.values():
                    u.setdefault("security", [])
                return users
            elif resp.status_code == 404:
                users = _default_users()
                _save_users(users)
                return users
        except Exception as e:
            st.warning(f"Could not reach GitHub for user storage ({e}). Using local fallback.")

    if not os.path.exists(USERS_FILE):
        users = _default_users()
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
        return users
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
    for u in users.values():
        u.setdefault("security", [])
    return users


def _save_users(users):
    if _github_configured():
        try:
            payload_content = base64.b64encode(json.dumps(users, indent=2).encode()).decode()
            get_resp = requests.get(_github_url(), headers=_github_headers(), timeout=10)
            sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None
            body = {
                "message": "Update users.json via Meraki Price Grid admin panel",
                "content": payload_content,
            }
            if sha:
                body["sha"] = sha
            put_resp = requests.put(_github_url(), headers=_github_headers(), json=body, timeout=10)
            if put_resp.status_code in (200, 201):
                return
            else:
                st.warning("GitHub save failed, falling back to local file (changes may not persist).")
        except Exception as e:
            st.warning(f"GitHub save error ({e}), falling back to local file.")

    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


st.set_page_config(
    page_title="Meraki Price Grid",
    page_icon="\u25c6",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
    --bg-main: #0f1115;
    --bg-panel: #161920;
    --bg-panel-2: #1c2029;
    --border-soft: #2a2e38;
    --text-primary: #eceef2;
    --text-secondary: #8b909c;
    --accent: #3ecfb2;
    --accent-dim: #23594c;
    --accent-glow: rgba(62,207,178,0.15);
    --warn: #e0a53e;
}

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
.stApp { background: var(--bg-main); color: var(--text-primary); }

h1, h2, h3 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.2px;
}
h1 {
    color: var(--text-primary) !important;
    font-size: 1.9rem;
    display: flex; align-items: center; gap: 10px;
}
h1::before {
    content: ""; display: inline-block; width: 8px; height: 8px;
    border-radius: 50%; background: var(--accent);
    box-shadow: 0 0 8px var(--accent-glow);
}
h2, h3 {
    color: var(--text-primary) !important;
    font-size: 1.05rem; font-weight: 600 !important;
    border-left: 2px solid var(--accent-dim); padding-left: 10px;
}

section[data-testid="stSidebar"] { background: var(--bg-panel); border-right: 1px solid var(--border-soft); }
section[data-testid="stSidebar"] h2 {
    border-left: none; padding-left: 0; border-bottom: 1px solid var(--border-soft);
    padding-bottom: 10px; text-transform: uppercase; letter-spacing: 0.8px;
    font-size: 0.8rem; color: var(--text-secondary) !important;
}

div[data-testid="stMetric"] {
    background: var(--bg-panel); border: 1px solid var(--border-soft);
    border-radius: 8px; padding: 16px 18px; position: relative; overflow: hidden;
}
div[data-testid="stMetric"]::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--accent), transparent); opacity: 0.6;
}
div[data-testid="stMetricValue"] {
    color: var(--text-primary) !important; font-family: 'IBM Plex Mono', monospace;
    font-weight: 500; font-size: 1.6rem !important;
}
div[data-testid="stMetricLabel"] {
    color: var(--text-secondary) !important; font-size: 0.72rem;
    letter-spacing: 0.6px; text-transform: uppercase;
}

.stDataFrame { border: 1px solid var(--border-soft); border-radius: 8px; }
hr { border-color: var(--border-soft) !important; }

.stButton>button, .stDownloadButton>button {
    background: var(--bg-panel-2); color: var(--text-primary);
    border: 1px solid var(--border-soft); border-radius: 6px;
    font-weight: 500; font-size: 0.85rem; transition: all 0.2s ease;
}
.stButton>button:hover, .stDownloadButton>button:hover { border-color: var(--accent); color: var(--accent); }

.subtle-divider {
    height: 1px; background: linear-gradient(90deg, var(--border-soft), transparent);
    margin: 16px 0 22px 0;
}
.status-box {
    background: var(--bg-panel); border: 1px solid var(--border-soft);
    border-radius: 8px; padding: 14px 18px; color: var(--text-secondary);
    font-family: 'IBM Plex Mono', monospace; font-size: 0.82rem;
    display: flex; align-items: center; justify-content: space-between;
}
.status-dot {
    display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: var(--accent); margin-right: 6px; box-shadow: 0 0 6px var(--accent-glow);
}
.storage-warning {
    background: rgba(224,165,62,0.08); border: 1px solid rgba(224,165,62,0.35);
    border-radius: 8px; padding: 10px 14px; color: var(--warn); font-size: 0.78rem;
    margin-bottom: 14px;
}
[data-testid="stExpander"] { border: 1px solid var(--border-soft); background: var(--bg-panel); border-radius: 8px; }
.stMultiSelect [data-baseweb="tag"] {
    background-color: var(--bg-panel-2) !important; border: 1px solid var(--accent-dim) !important;
    color: var(--text-primary) !important;
}
.login-card {
    max-width: 420px; margin: 50px auto 0 auto; background: var(--bg-panel);
    border: 1px solid var(--border-soft); border-radius: 10px; padding: 32px 28px;
}
</style>
""", unsafe_allow_html=True)

PLOT_TEMPLATE = go.layout.Template()
PLOT_TEMPLATE.layout = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(22,25,32,0.4)",
    font=dict(color="#eceef2", family="Inter"),
    colorway=["#3ecfb2", "#5a6072", "#7fe6d0", "#3a3f4b", "#23594c"],
    xaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.1)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.1)"),
)

if "users" not in st.session_state:
    st.session_state.users = _load_users()
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "current_role" not in st.session_state:
    st.session_state.current_role = None
if "auth_view" not in st.session_state:
    st.session_state.auth_view = "login"
if "reset_stage" not in st.session_state:
    st.session_state.reset_stage = "enter_username"
if "reset_username" not in st.session_state:
    st.session_state.reset_username = None
if "account_verified" not in st.session_state:
    st.session_state.account_verified = False


def login_view():
    st.markdown("### Sign In")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    c1, c2 = st.columns(2)
    if c1.button("Sign In", width="stretch"):
        users = st.session_state.users
        if username in users and _verify(password, users[username]["password_hash"]):
            st.session_state.authenticated = True
            st.session_state.current_user = username
            st.session_state.current_role = users[username]["role"]
            st.session_state.account_verified = False
            st.rerun()
        else:
            st.error("Invalid username or password.")
    if c2.button("Forgot Password?", width="stretch"):
        st.session_state.auth_view = "reset"
        st.session_state.reset_stage = "enter_username"
        st.rerun()


def reset_view():
    st.markdown("### Reset Password")
    users = st.session_state.users

    if st.session_state.reset_stage == "enter_username":
        uname = st.text_input("Username", key="reset_uname_input")
        if st.button("Continue", width="stretch"):
            if uname not in users:
                st.error("No such user.")
            elif len(users[uname].get("security", [])) < 1:
                st.error("This account has no security questions set. Contact your admin.")
            else:
                st.session_state.reset_username = uname
                st.session_state.reset_stage = "answer_questions"
                st.rerun()

    elif st.session_state.reset_stage == "answer_questions":
        uname = st.session_state.reset_username
        sec = users[uname]["security"]
        st.caption("Answer all questions to verify your identity.")
        answers = []
        for i, qa in enumerate(sec):
            st.info(qa["question"])
            answers.append(st.text_input("Your answer", key=f"reset_ans_{i}"))
        if st.button("Verify Answers", width="stretch"):
            all_correct = all(
                _verify(answers[i].strip().lower(), sec[i]["answer_hash"]) for i in range(len(sec))
            )
            if all_correct:
                st.session_state.reset_stage = "set_new_password"
                st.rerun()
            else:
                st.error("One or more answers are incorrect.")

    elif st.session_state.reset_stage == "set_new_password":
        uname = st.session_state.reset_username
        new_pw = st.text_input("New password", type="password", key="reset_new_pw")
        confirm_pw = st.text_input("Confirm new password", type="password", key="reset_confirm_pw")
        if st.button("Reset Password", width="stretch"):
            if len(new_pw) < 6:
                st.error("Password must be at least 6 characters.")
            elif new_pw != confirm_pw:
                st.error("Passwords do not match.")
            else:
                users[uname]["password_hash"] = _hash(new_pw)
                _save_users(users)
                st.success("Password reset successful. You can now sign in.")
                st.session_state.reset_stage = "enter_username"
                st.session_state.auth_view = "login"

    if st.button("Back to Sign In"):
        st.session_state.auth_view = "login"
        st.session_state.reset_stage = "enter_username"
        st.rerun()


def setup_security_questions_prompt():
    st.markdown("### Set Up Account Recovery")
    st.caption(f"Choose {NUM_SECURITY_QUESTIONS} different security questions so you can reset your password if you forget it.")
    chosen = []
    for i in range(NUM_SECURITY_QUESTIONS):
        available = [q for q in SECURITY_QUESTIONS if q not in chosen]
        q = st.selectbox(f"Security question {i+1}", available, key=f"setup_sq_{i}")
        a = st.text_input(f"Answer {i+1}", key=f"setup_sa_{i}")
        chosen.append(q)
        st.session_state[f"_pending_q_{i}"] = q
        st.session_state[f"_pending_a_{i}"] = a

    c1, c2 = st.columns(2)
    if c1.button("Save", width="stretch"):
        answers_filled = all(st.session_state.get(f"_pending_a_{i}", "").strip() for i in range(NUM_SECURITY_QUESTIONS))
        if not answers_filled:
            st.error("Please answer all questions.")
        else:
            users = st.session_state.users
            uname = st.session_state.current_user
            security = []
            for i in range(NUM_SECURITY_QUESTIONS):
                security.append({
                    "question": st.session_state[f"_pending_q_{i}"],
                    "answer_hash": _hash(st.session_state[f"_pending_a_{i}"].strip().lower()),
                })
            users[uname]["security"] = security
            _save_users(users)
            st.session_state.skip_security_setup = True
            st.rerun()
    if c2.button("Skip for now", width="stretch"):
        st.session_state.skip_security_setup = True
        st.rerun()


if not st.session_state.authenticated:
    st.markdown("# Meraki Price Grid")
    st.markdown(
        '<div class="status-box">'
        '<span><span class="status-dot"></span>Secure access required</span>'
        '<span style="color:#3ecfb2;">LOCKED</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    if not _github_configured():
        st.markdown(
            '<div class="storage-warning">'
            'Persistent account storage is not configured yet. New accounts created here '
            'will not survive an app restart until GitHub-based storage secrets are added. '
            'See the setup notes at the top of the source file.'
            '</div>',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    if st.session_state.auth_view == "login":
        login_view()
    else:
        reset_view()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

current_user_data = st.session_state.users.get(st.session_state.current_user, {})
if len(current_user_data.get("security", [])) < NUM_SECURITY_QUESTIONS and not st.session_state.get("skip_security_setup"):
    st.markdown("# Meraki Price Grid")
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    setup_security_questions_prompt()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


def _first_existing(patterns):
    for p in patterns:
        matches = glob.glob(p)
        if matches:
            return matches[0]
    return None


@st.cache_data
def load_data():
    buymeraki_path = _first_existing([
        "buymeraki_all_categories_enriched.csv", "buymeraki_all_categories.csv",
        "*buymeraki*enriched*.csv", "*buymeraki*.csv",
    ])
    dragon_path = _first_existing([
        "dragon_networks_products.csv", "*dragon*networks*.csv", "*dragon*.csv",
    ])

    frames = []
    file_mtimes = []

    if buymeraki_path and os.path.exists(buymeraki_path):
        bm = pd.read_csv(buymeraki_path)
        bm["Source"] = "BuyMeraki"
        frames.append(bm)
        file_mtimes.append(os.path.getmtime(buymeraki_path))

    if dragon_path and os.path.exists(dragon_path):
        dn = pd.read_csv(dragon_path)
        dn["Source"] = "Dragon Networks"
        frames.append(dn)
        file_mtimes.append(os.path.getmtime(dragon_path))

    if not frames:
        return pd.DataFrame(), False, None

    combined = pd.concat(frames, ignore_index=True, sort=False)

    for col in ["MSRP (Inc. GST)", "Price (Inc. GST)", "MSRP (Ex. GST)", "Price (Ex. GST)", "Discount %"]:
        if col not in combined.columns:
            combined[col] = np.nan
        combined[col] = pd.to_numeric(combined[col], errors="coerce")

    for col in ["Category", "Brand", "Manufacturer", "SKU", "MPN", "Availability", "Title", "Product URL"]:
        if col not in combined.columns:
            combined[col] = None

    if "On Sale/Discount" not in combined.columns:
        combined["On Sale/Discount"] = False
    combined["On Sale/Discount"] = combined["On Sale/Discount"].fillna(False).astype(bool)

    combined["Brand"] = combined["Brand"].fillna("Meraki")
    combined["Category"] = combined["Category"].fillna("Uncategorised")
    combined["Manufacturer"] = combined["Manufacturer"].fillna("Unknown")
    combined["Availability"] = combined["Availability"].fillna("Unknown")
    combined = combined.dropna(subset=["Title"])

    last_updated = datetime.fromtimestamp(max(file_mtimes)) if file_mtimes else None
    return combined, True, last_updated


df, data_found, last_updated = load_data()

st.markdown("# Meraki Price Grid")
last_updated_str = last_updated.strftime("%d %b %Y, %H:%M") if last_updated else "Unknown"
st.markdown(
    '<div class="status-box">'
    '<span><span class="status-dot"></span>Combined intel feed &mdash; BuyMeraki.com.au + Dragon-Networks.com.au</span>'
    f'<span style="color:#3ecfb2;">LIVE &middot; Data last updated {last_updated_str}</span>'
    "</div>",
    unsafe_allow_html=True,
)
st.write("")

with st.sidebar:
    st.markdown(f"**Signed in as:** {st.session_state.current_user} ({st.session_state.current_role})")
    if st.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.session_state.current_role = None
        st.session_state.pop("skip_security_setup", None)
        st.session_state.account_verified = False
        st.rerun()

    with st.expander("My Account"):
        st.caption("Update your own username or password. You must re-answer your security questions first.")
        my_data = st.session_state.users[st.session_state.current_user]

        if not st.session_state.account_verified:
            answers = []
            for i, qa in enumerate(my_data.get("security", [])):
                st.write(qa["question"])
                answers.append(st.text_input("Answer", key=f"myacct_ans_{i}"))
            if st.button("Verify Identity"):
                sec = my_data.get("security", [])
                if len(sec) == 0:
                    st.session_state.account_verified = True
                    st.rerun()
                else:
                    ok = all(_verify(answers[i].strip().lower(), sec[i]["answer_hash"]) for i in range(len(sec)))
                    if ok:
                        st.session_state.account_verified = True
                        st.rerun()
                    else:
                        st.error("One or more answers are incorrect.")
        else:
            st.success("Identity verified for this session.")
            new_uname = st.text_input("New username (optional)", key="myacct_new_uname")
            new_pw = st.text_input("New password (optional)", type="password", key="myacct_new_pw")
            if st.button("Save Account Changes"):
                users = st.session_state.users
                current = st.session_state.current_user
                changed = False
                if new_uname and new_uname != current:
                    if new_uname in users:
                        st.error("That username is already taken.")
                    else:
                        users[new_uname] = users.pop(current)
                        st.session_state.current_user = new_uname
                        current = new_uname
                        changed = True
                if new_pw:
                    if len(new_pw) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        users[current]["password_hash"] = _hash(new_pw)
                        changed = True
                if changed:
                    _save_users(users)
                    st.success("Account updated successfully.")

    st.markdown('<div class="subtle-divider"></div>', unsafe_allow_html=True)

if st.session_state.current_role == "admin":
    with st.sidebar.expander("Admin: Manage Users"):
        st.markdown("**Create new user**")
        new_username = st.text_input("New username", key="new_username")
        auto_pw = st.checkbox("Auto-generate password", value=True)
        if auto_pw:
            new_password = _gen_password()
            st.text_input("Generated password", value=new_password, disabled=True, key="gen_pw_display")
        else:
            new_password = st.text_input("New password", type="password", key="new_password")
        new_role = st.selectbox("Role", ["viewer", "admin"], key="new_role")
        if st.button("Create User"):
            if not new_username or not new_password:
                st.warning("Username and password are required.")
            elif new_username in st.session_state.users:
                st.warning("That username already exists.")
            else:
                st.session_state.users[new_username] = {
                    "password_hash": _hash(new_password),
                    "role": new_role,
                    "security": [],
                }
                _save_users(st.session_state.users)
                st.success(f"User '{new_username}' created. Password: {new_password}")

        st.markdown('<div class="subtle-divider"></div>', unsafe_allow_html=True)
        st.markdown("**Manage existing users**")
        usernames = list(st.session_state.users.keys())
        selected_user = st.selectbox("Select user", usernames, key="manage_select_user")

        if selected_user:
            udata = st.session_state.users[selected_user]
            st.caption(f"Current role: {udata['role']} | Security questions set: {len(udata.get('security', []))}")

            new_role_for_user = st.selectbox(
                "Change role", ["viewer", "admin"],
                index=["viewer", "admin"].index(udata["role"]),
                key=f"role_{selected_user}",
            )
            if st.button("Update Role", key=f"update_role_{selected_user}"):
                st.session_state.users[selected_user]["role"] = new_role_for_user
                _save_users(st.session_state.users)
                st.success("Role updated.")

            rename_to = st.text_input("Rename username to", key=f"rename_{selected_user}")
            if st.button("Update Username", key=f"update_username_{selected_user}"):
                if not rename_to:
                    st.warning("Enter a new username.")
                elif rename_to in st.session_state.users:
                    st.warning("That username is already taken.")
                else:
                    st.session_state.users[rename_to] = st.session_state.users.pop(selected_user)
                    _save_users(st.session_state.users)
                    if st.session_state.current_user == selected_user:
                        st.session_state.current_user = rename_to
                    st.success(f"Username updated to '{rename_to}'.")
                    st.rerun()

            reset_pw_auto = st.checkbox("Auto-generate reset password", value=True, key=f"resetauto_{selected_user}")
            if reset_pw_auto:
                reset_pw_value = _gen_password()
                st.text_input("New generated password", value=reset_pw_value, disabled=True, key=f"resetpwdisp_{selected_user}")
            else:
                reset_pw_value = st.text_input("Set specific password", type="password", key=f"resetpwmanual_{selected_user}")
            if st.button("Reset Password", key=f"resetpwbtn_{selected_user}"):
                if not reset_pw_value:
                    st.warning("Enter or generate a password.")
                else:
                    st.session_state.users[selected_user]["password_hash"] = _hash(reset_pw_value)
                    _save_users(st.session_state.users)
                    st.success(f"Password reset. New password: {reset_pw_value}")

            if selected_user != st.session_state.current_user:
                if st.button("Delete User", key=f"delete_{selected_user}"):
                    del st.session_state.users[selected_user]
                    _save_users(st.session_state.users)
                    st.success(f"User '{selected_user}' deleted.")
                    st.rerun()
    st.sidebar.markdown('<div class="subtle-divider"></div>', unsafe_allow_html=True)

if not data_found:
    st.error(
        "No scraped data found. Run `buymeraki_scraper.py` and "
        "`dragon_networks_scraper.py` first, and keep this app in the same folder "
        "as the CSVs they produce (`buymeraki_all_categories_enriched.csv` and "
        "`dragon_networks_products.csv`)."
    )
    st.stop()

st.sidebar.markdown("## Filters")

sources = sorted(df["Source"].dropna().unique().tolist())
sel_sources = st.sidebar.multiselect("Source", sources, default=sources)

categories = sorted(df["Category"].dropna().unique().tolist())
sel_categories = st.sidebar.multiselect("Category", categories, default=[])

brands = sorted(df["Brand"].dropna().unique().tolist())
sel_brands = st.sidebar.multiselect("Brand", brands, default=[])

manufacturers = sorted(df["Manufacturer"].dropna().unique().tolist())
sel_manufacturers = st.sidebar.multiselect("Manufacturer", manufacturers, default=[])

availabilities = sorted(df["Availability"].dropna().unique().tolist())
sel_availability = st.sidebar.multiselect("Availability", availabilities, default=[])

search_term = st.sidebar.text_input("Search title / SKU", "")
sale_only = st.sidebar.checkbox("On sale only", value=False)

price_col = "Price (Inc. GST)" if df["Price (Inc. GST)"].notna().any() else "Price (Ex. GST)"
valid_prices = df[price_col].dropna()
if not valid_prices.empty:
    p_min, p_max = float(valid_prices.min()), float(valid_prices.max())
    sel_price = st.sidebar.slider("Price range (AUD)", p_min, p_max, (p_min, p_max))
else:
    sel_price = (0.0, 0.0)

sort_option = st.sidebar.selectbox(
    "Sort product grid by",
    ["Price (High to Low)", "Price (Low to High)", "Title (A-Z)", "Discount % (High to Low)"],
)

filtered = df.copy()
if sel_sources:
    filtered = filtered[filtered["Source"].isin(sel_sources)]
if sel_categories:
    filtered = filtered[filtered["Category"].isin(sel_categories)]
if sel_brands:
    filtered = filtered[filtered["Brand"].isin(sel_brands)]
if sel_manufacturers:
    filtered = filtered[filtered["Manufacturer"].isin(sel_manufacturers)]
if sel_availability:
    filtered = filtered[filtered["Availability"].isin(sel_availability)]
if search_term:
    term = search_term.lower()
    mask = (
        filtered["Title"].astype(str).str.lower().str.contains(term, na=False)
        | filtered["SKU"].astype(str).str.lower().str.contains(term, na=False)
        | filtered["MPN"].astype(str).str.lower().str.contains(term, na=False)
    )
    filtered = filtered[mask]
if sale_only:
    filtered = filtered[filtered["On Sale/Discount"]]
if valid_prices.any():
    filtered = filtered[
        filtered[price_col].isna()
        | filtered[price_col].between(sel_price[0], sel_price[1])
    ]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total SKUs", f"{len(filtered):,}")
c2.metric("On Sale", f"{int(filtered['On Sale/Discount'].sum()):,}")
avg_price = filtered[price_col].mean()
c3.metric("Avg Price", f"${avg_price:,.2f}" if pd.notna(avg_price) else "\u2014")
avg_discount = filtered.loc[filtered["On Sale/Discount"], "Discount %"].mean()
c4.metric("Avg Discount", f"{avg_discount:,.1f}%" if pd.notna(avg_discount) else "\u2014")
c5.metric("Sources Live", f"{filtered['Source'].nunique()}")

st.markdown('<div class="subtle-divider"></div>', unsafe_allow_html=True)

col_a, col_b = st.columns([1.3, 1])

with col_a:
    st.markdown("### Avg Price by Category")
    cat_avg = (
        filtered.dropna(subset=[price_col])
        .groupby("Category")[price_col]
        .mean()
        .sort_values(ascending=False)
        .head(15)
        .reset_index()
    )
    if not cat_avg.empty:
        fig = px.bar(cat_avg, x=price_col, y="Category", orientation="h", template=PLOT_TEMPLATE)
        fig.update_traces(marker_line_width=0)
        fig.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No priced items in current filter.")

with col_b:
    st.markdown("### Source Split")
    src_counts = filtered["Source"].value_counts().reset_index()
    src_counts.columns = ["Source", "Count"]
    if not src_counts.empty:
        fig2 = px.pie(src_counts, names="Source", values="Count", hole=0.6, template=PLOT_TEMPLATE)
        fig2.update_traces(textfont_color="#eceef2", marker=dict(line=dict(color="#0f1115", width=2)))
        fig2.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10), legend=dict(font=dict(color="#eceef2")))
        st.plotly_chart(fig2, width="stretch")

st.markdown("### Price Distribution")
price_data = filtered.dropna(subset=[price_col])
if not price_data.empty:
    fig3 = px.histogram(price_data, x=price_col, nbins=40, template=PLOT_TEMPLATE,
                         color="Source", barmode="overlay", opacity=0.85)
    fig3.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig3, width="stretch")

st.markdown('<div class="subtle-divider"></div>', unsafe_allow_html=True)

st.markdown("### Top Discounted Products")
top_discounts = (
    filtered[filtered["On Sale/Discount"]]
    .dropna(subset=["Discount %"])
    .sort_values("Discount %", ascending=False)
    .head(10)
)
if not top_discounts.empty:
    st.dataframe(
        top_discounts[["Source", "Title", "Category", price_col, "Discount %"]],
        width="stretch",
    )
else:
    st.info("No discounted items in current filter.")

st.markdown('<div class="subtle-divider"></div>', unsafe_allow_html=True)

st.markdown("### Cross-Source Match: Same SKU, Different Vendor")
if {"SKU", "MPN"}.issubset(filtered.columns):
    key_series = filtered["SKU"].fillna(filtered["MPN"]).astype(str).str.upper().str.strip()
    tmp = filtered.assign(_key=key_series)
    tmp = tmp[tmp["_key"].notna() & (tmp["_key"] != "NAN") & (tmp["_key"] != "")]

    pivot = tmp.groupby(["_key", "Source"])[price_col].min().unstack("Source")
    pivot = pivot.dropna(how="all")
    matched = pivot.dropna(thresh=2) if pivot.shape[1] > 1 else pd.DataFrame()

    if not matched.empty:
        matched = matched.copy()
        matched["Cheapest"] = matched.idxmin(axis=1)
        matched["Price Gap ($)"] = matched.drop(columns="Cheapest").max(axis=1) - matched.drop(columns="Cheapest").min(axis=1)
        matched = matched.sort_values("Price Gap ($)", ascending=False)
        st.dataframe(matched.reset_index().rename(columns={"_key": "SKU / Model"}), width="stretch")
    else:
        st.info("No overlapping SKUs found between sources in the current filter.")
else:
    st.info("SKU/MPN columns not available for cross-matching.")

st.markdown('<div class="subtle-divider"></div>', unsafe_allow_html=True)

st.markdown("### Product Grid")
display_cols = [c for c in [
    "Source", "Category", "Title", "Brand", "SKU", "MPN", "Manufacturer",
    "Availability", "MSRP (Inc. GST)", "Price (Inc. GST)", "Price (Ex. GST)",
    "On Sale/Discount", "Discount %", "Product URL",
] if c in filtered.columns]

grid = filtered[display_cols].copy()
if sort_option == "Price (High to Low)":
    grid = grid.sort_values(price_col, ascending=False, na_position="last")
elif sort_option == "Price (Low to High)":
    grid = grid.sort_values(price_col, ascending=True, na_position="last")
elif sort_option == "Title (A-Z)":
    grid = grid.sort_values("Title", ascending=True, na_position="last")
elif sort_option == "Discount % (High to Low)":
    grid = grid.sort_values("Discount %", ascending=False, na_position="last")

st.dataframe(grid, width="stretch", height=480)

st.download_button(
    "Export Filtered Data (.csv)",
    data=grid.to_csv(index=False).encode("utf-8"),
    file_name="meraki_combined_filtered.csv",
    mime="text/csv",
)

st.markdown('<div class="subtle-divider"></div>', unsafe_allow_html=True)
st.caption(f"Meraki Price Grid \u2014 data last updated {last_updated_str}. Re-run the scrapers to refresh.")
