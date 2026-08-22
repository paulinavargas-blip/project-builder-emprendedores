
import streamlit as st
import json
import re
import hashlib
import secrets
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from docx import Document
from docx.shared import Pt
from supabase import create_client

BASE = Path(__file__).parent
with open(BASE / "data" / "modulos.json", encoding="utf-8") as f:
    MODULES = json.load(f)

st.set_page_config(
    page_title="Project Builder | Desarrollo de Emprendedores",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {padding-top: 1rem; max-width: 1480px;}
.hero {
    padding: 1.4rem 1.6rem;
    border-radius: 18px;
    background: linear-gradient(135deg, #f6f7f9 0%, #ffffff 100%);
    border: 1px solid #e6e7e9;
    margin-bottom: 1rem;
}
.hero h1 {margin:0 0 .2rem 0;}
.muted {color:#666;}
.card {
    padding: .9rem 1rem;
    border: 1px solid #e1e3e6;
    border-radius: 14px;
    background: white;
    margin-bottom: .7rem;
}
.good {padding:.75rem 1rem;border-left:5px solid #777;background:#fafafa;}
</style>
""", unsafe_allow_html=True)

# ---------- Cloud connection ----------
def get_db():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_SERVICE_KEY"]
        return create_client(url, key)
    except Exception:
        st.error(
            "La aplicación aún no está conectada a la base de datos. "
            "La persona administradora debe configurar los secretos de Supabase."
        )
        st.stop()

db = get_db()

# ---------- Security helpers ----------
def normalize_team_code(value: str) -> str:
    value = value.strip().upper()
    return re.sub(r"[^A-Z0-9_-]", "", value)

def hash_pin(pin: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        bytes.fromhex(salt_hex),
        180_000
    ).hex()

def verify_pin(pin: str, salt_hex: str, expected_hash: str) -> bool:
    try:
        return secrets.compare_digest(hash_pin(pin, salt_hex), expected_hash)
    except Exception:
        return False

def utc_now():
    return datetime.now(timezone.utc).isoformat()

# ---------- Database helpers ----------
def fetch_project(team_code):
    result = (
        db.table("projects")
        .select("*")
        .eq("team_code", team_code)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None

def create_project(team_code, project_name, pin):
    salt = secrets.token_hex(16)
    record = {
        "team_code": team_code,
        "project_name": project_name.strip(),
        "pin_salt": salt,
        "pin_hash": hash_pin(pin, salt),
        "payload": {
            "equipo": team_code,
            "proyecto": project_name.strip(),
            "modulos": {}
        },
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    return db.table("projects").insert(record).execute()

def save_project(record_id, payload, project_name):
    (
        db.table("projects")
        .update({
            "payload": payload,
            "project_name": project_name,
            "updated_at": utc_now()
        })
        .eq("id", record_id)
        .execute()
    )

# ---------- Academic helpers ----------
def all_fields(module):
    return [f for section in module["sections"] for f in section["fields"]]

def module_pct(module, data):
    md = data.get("modulos", {}).get(module["id"], {})
    fields = all_fields(module)
    if not fields:
        return 0
    answered = sum(bool(str(md.get(f["clave"], "")).strip()) for f in fields)
    return round(answered / len(fields) * 100)

def global_pct(data):
    vals = [module_pct(m, data) for m in MODULES]
    return round(sum(vals)/len(vals)) if vals else 0

def consistency_alerts(data):
    mods = data.get("modulos", {})
    alerts = []
    fin = mods.get("finanzas", {})
    if mods.get("mercadotecnia", {}).get("presupuesto_mkt", "").strip() and not fin.get("presupuesto", "").strip():
        alerts.append("Mercadotecnia ya contiene presupuesto. Verifiquen su integración en el Plan Financiero.")
    if mods.get("operaciones", {}).get("proveedores", "").strip() and not fin.get("presupuesto", "").strip():
        alerts.append("Operaciones ya identifica proveedores/costos. Deben trasladarse al Modelo Financiero.")
    if mods.get("talento", {}).get("compensacion", "").strip() and not fin.get("presupuesto", "").strip():
        alerts.append("Talento ya define compensaciones. Nómina, prestaciones e incentivos deben aparecer en Finanzas.")
    if mods.get("legal", {}).get("costos_legales", "").strip() and not fin.get("presupuesto", "").strip():
        alerts.append("Legal ya identifica desembolsos. Esos costos deben incorporarse al Plan Financiero.")
    return alerts

def build_docx(data):
    doc = Document()
    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"].font.size = Pt(11)

    doc.add_heading("Proyecto Final – Plan de Negocios", 0)
    doc.add_paragraph("Desarrollo de Emprendedores")
    doc.add_paragraph(f"Equipo: {data.get('equipo','')}")
    doc.add_paragraph(f"Proyecto: {data.get('proyecto','')}")

    for m in MODULES:
        md = data.get("modulos", {}).get(m["id"], {})
        doc.add_page_break()
        doc.add_heading(f"{m['numero']} · {m['titulo']}", level=1)
        doc.add_paragraph(m["objetivo"])
        for section in m["sections"]:
            doc.add_heading(section["titulo"], level=2)
            for fld in section["fields"]:
                doc.add_heading(fld["etiqueta"], level=3)
                value = str(md.get(fld["clave"], "")).strip()
                doc.add_paragraph(value or "[Pendiente]")
        doc.add_heading("Lista de verificación", level=2)
        checks = md.get("_checks", {})
        for item in m["checklist"]:
            doc.add_paragraph(("✓ " if checks.get(item) else "☐ ") + item)

    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

def logout():
    for key in ["authenticated", "record_id", "team_code", "project_name", "project_data"]:
        st.session_state.pop(key, None)
    st.rerun()

# ---------- Login / Create project ----------
if not st.session_state.get("authenticated"):
    st.markdown("""
    <div class="hero">
      <h1>🚀 Project Builder</h1>
      <b>Desarrollo de Emprendedores · Plan de Negocios</b>
      <div class="muted">Acceso web por equipo. El avance queda guardado en línea.</div>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_create = st.tabs(["Entrar a mi proyecto", "Crear proyecto"])

    with tab_login:
        st.subheader("Acceso del equipo")
        code = normalize_team_code(st.text_input("Código de equipo", key="login_code"))
        pin = st.text_input("PIN del equipo", type="password", key="login_pin")
        if st.button("Entrar", type="primary", use_container_width=True):
            if not code or len(pin) < 4:
                st.error("Captura el código del equipo y un PIN válido.")
            else:
                row = fetch_project(code)
                if not row or not verify_pin(pin, row["pin_salt"], row["pin_hash"]):
                    st.error("Código o PIN incorrecto.")
                else:
                    payload = row.get("payload") or {}
                    payload.setdefault("equipo", code)
                    payload.setdefault("proyecto", row["project_name"])
                    payload.setdefault("modulos", {})
                    st.session_state.update({
                        "authenticated": True,
                        "record_id": row["id"],
                        "team_code": code,
                        "project_name": row["project_name"],
                        "project_data": payload,
                    })
                    st.rerun()

    with tab_create:
        st.subheader("Crear un proyecto nuevo")
        new_code = normalize_team_code(st.text_input(
            "Código único del equipo",
            placeholder="Ej. EQ01"
        ))
        project_name = st.text_input("Nombre del proyecto")
        pin1 = st.text_input("Crear PIN (mínimo 4 caracteres)", type="password")
        pin2 = st.text_input("Confirmar PIN", type="password")
        st.caption("El equipo deberá conservar su código y PIN para volver a entrar otro día.")

        if st.button("Crear proyecto", use_container_width=True):
            if not new_code or not project_name.strip():
                st.error("Completa código de equipo y nombre del proyecto.")
            elif len(pin1) < 4:
                st.error("El PIN debe tener al menos 4 caracteres.")
            elif pin1 != pin2:
                st.error("Los PIN no coinciden.")
            elif fetch_project(new_code):
                st.error("Ese código de equipo ya existe. Utiliza otro.")
            else:
                create_project(new_code, project_name, pin1)
                row = fetch_project(new_code)
                payload = row["payload"]
                st.session_state.update({
                    "authenticated": True,
                    "record_id": row["id"],
                    "team_code": new_code,
                    "project_name": project_name.strip(),
                    "project_data": payload,
                })
                st.rerun()
    st.stop()

# ---------- Main application ----------
data = st.session_state["project_data"]
data["equipo"] = st.session_state["team_code"]
data["proyecto"] = st.session_state["project_name"]
data.setdefault("modulos", {})

st.markdown(f"""
<div class="hero">
  <h1>🚀 Project Builder</h1>
  <b>{st.session_state['project_name']}</b><br>
  <span class="muted">Equipo {st.session_state['team_code']} · Desarrollo de Emprendedores</span>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("Proyecto")
    st.write(f"**Equipo:** {st.session_state['team_code']}")
    st.write(f"**Proyecto:** {st.session_state['project_name']}")

    overall = global_pct(data)
    st.metric("Avance global", f"{overall}%")
    st.progress(overall / 100)

    labels = [
        f"{m['numero']} · {m['titulo']} · {module_pct(m, data)}%"
        for m in MODULES
    ]
    selected_label = st.radio("Ruta del proyecto", labels)
    module = MODULES[labels.index(selected_label)]

    st.divider()
    if st.button("💾 Guardar avance", use_container_width=True):
        save_project(
            st.session_state["record_id"],
            data,
            st.session_state["project_name"]
        )
        st.success("Avance guardado en línea.")

    st.download_button(
        "📄 Descargar Plan de Negocios",
        data=build_docx(data),
        file_name=f"{st.session_state['team_code']}_Plan_de_Negocios.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True
    )

    if st.button("Cerrar sesión", use_container_width=True):
        logout()

tab_build, tab_coherence, tab_delivery = st.tabs(
    ["🧭 Construir", "🔗 Coherencia", "📋 Vista de entrega"]
)

with tab_build:
    st.header(f"{module['numero']} · {module['titulo']}")
    st.info("**Objetivo de aprendizaje:** " + module["objetivo"])

    with st.expander("♻️ Insumos que debes recuperar", expanded=True):
        for item in module["recupera"]:
            st.markdown(f"- {item}")

    md = data["modulos"].setdefault(module["id"], {})

    for section in module["sections"]:
        st.subheader(section["titulo"])
        with st.expander("Indicaciones", expanded=True):
            for instruction in section["instructions"]:
                st.markdown(f"- {instruction}")

        for fld in section["fields"]:
            md[fld["clave"]] = st.text_area(
                fld["etiqueta"],
                value=md.get(fld["clave"], ""),
                help=fld.get("ayuda", ""),
                height=150,
                key=f"{module['id']}__{fld['clave']}"
            )

    st.subheader("🤖 Uso responsable de IA")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Sí puede apoyar en:**")
        for item in module["ia_si"]:
            st.markdown(f"- {item}")
    with c2:
        st.markdown("**No debe utilizarse para:**")
        for item in module["ia_no"]:
            st.markdown(f"- {item}")

    st.subheader("Prompt de revisión")
    content = "\n".join(
        f"{f['etiqueta']}: {md.get(f['clave'], '')}"
        for f in all_fields(module)
    )
    prompt = f"""Actúa como asesor académico del curso Desarrollo de Emprendedores.
Revisa el módulo "{module['titulo']}" del proyecto "{st.session_state['project_name']}".
No escribas el entregable por el equipo y no inventes datos, fuentes, cifras, competidores, proveedores ni requisitos.

Evalúa:
1. Coherencia con el modelo de negocio.
2. Evidencia faltante.
3. Conexión con módulos previos.
4. Supuestos presentados como si fueran hechos.
5. Cinco preguntas concretas que el equipo debe responder para mejorar.

Contenido actual:
{content}"""
    st.code(prompt, language=None)

    st.subheader("✅ Checklist")
    checks = md.setdefault("_checks", {})
    for item in module["checklist"]:
        checks[item] = st.checkbox(
            item,
            value=checks.get(item, False),
            key=f"{module['id']}__check__{item}"
        )

    if st.button("Guardar este módulo", type="primary"):
        save_project(
            st.session_state["record_id"],
            data,
            st.session_state["project_name"]
        )
        st.success("Módulo guardado en línea.")

with tab_coherence:
    st.header("Coherencia transversal")
    st.write(
        "El Builder identifica conexiones básicas; la calidad académica y la validez "
        "de la evidencia siguen siendo responsabilidad del equipo."
    )
    st.markdown(
        "**Ruta de integración:** Evidencia → Mercado → Operación → Personas → "
        "Cumplimiento → Finanzas."
    )
    alerts = consistency_alerts(data)
    if alerts:
        for alert in alerts:
            st.warning(alert)
    else:
        st.success("No hay alertas básicas pendientes con la información capturada.")

    st.subheader("Avance por módulo")
    for mm in MODULES:
        val = module_pct(mm, data)
        st.write(f"**{mm['numero']} · {mm['titulo']}** — {val}%")
        st.progress(val / 100)

with tab_delivery:
    st.header("Vista de entrega")
    for mm in MODULES:
        val = module_pct(mm, data)
        with st.expander(f"{mm['numero']} · {mm['titulo']} — {val}%"):
            checks = data.get("modulos", {}).get(mm["id"], {}).get("_checks", {})
            for item in mm["checklist"]:
                st.write(("✅ " if checks.get(item) else "⬜ ") + item)
