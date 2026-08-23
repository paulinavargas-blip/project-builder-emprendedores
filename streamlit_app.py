import streamlit as st
import json, re, hashlib, secrets, string
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from docx import Document
from docx.shared import Pt
from supabase import create_client

BASE = Path(__file__).parent
with open(BASE / "modulos.json", encoding="utf-8") as f:
    MODULES = json.load(f)

st.set_page_config(page_title="Project Builder | Desarrollo de Emprendedores", page_icon="🚀", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1rem;max-width:1500px}.hero{padding:1.3rem 1.5rem;border-radius:18px;background:#f7f8fa;border:1px solid #e4e6e9;margin-bottom:1rem}.hero h1{margin:0 0 .2rem 0}.muted{color:#666}.role{display:inline-block;padding:.2rem .55rem;border-radius:14px;background:#eceff2;margin-right:.3rem;font-size:.8rem}
</style>
""", unsafe_allow_html=True)

def utc_now(): return datetime.now(timezone.utc).isoformat()
def get_db():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"])
    except Exception:
        st.error("La aplicación aún no está conectada con Supabase."); st.stop()
db=get_db()

def hash_secret(value,salt_hex):
    return hashlib.pbkdf2_hmac("sha256",value.encode(),bytes.fromhex(salt_hex),180000).hex()
def verify_secret(value,salt_hex,expected):
    try: return secrets.compare_digest(hash_secret(value,salt_hex),expected)
    except Exception: return False
def new_salt(): return secrets.token_hex(16)
def random_password(n=10):
    alphabet=string.ascii_letters+string.digits+"!@#$"
    return "".join(secrets.choice(alphabet) for _ in range(n))
def normalize_code(v): return re.sub(r"[^A-Z0-9_-]","",v.strip().upper())

def rows(table,**equals):
    q=db.table(table).select("*")
    for k,v in equals.items(): q=q.eq(k,v)
    return q.execute().data or []
def one(table,**equals):
    r=rows(table,**equals); return r[0] if r else None

def ensure_initial_admin():
    if rows("app_users"): return
    try:
        email=st.secrets["INITIAL_ADMIN_EMAIL"].strip().lower()
        password=st.secrets["INITIAL_ADMIN_PASSWORD"]
        name=st.secrets.get("INITIAL_ADMIN_NAME","Administradora")
    except Exception: return
    salt=new_salt()
    db.table("app_users").insert({"name":name,"email":email,"password_salt":salt,"password_hash":hash_secret(password,salt),"is_admin":True,"is_teacher":True,"is_active":True,"created_at":utc_now(),"updated_at":utc_now()}).execute()
ensure_initial_admin()

def staff_login(email,password):
    u=one("app_users",email=email.strip().lower(),is_active=True)
    return u if u and verify_secret(password,u["password_salt"],u["password_hash"]) else None
def team_login(code,pin):
    t=one("teams",team_code=normalize_code(code),is_active=True)
    return t if t and verify_secret(pin,t["pin_salt"],t["pin_hash"]) else None

def all_fields(m): return [f for s in m["sections"] for f in s["fields"]]
def module_pct(m,payload):
    md=payload.get("modulos",{}).get(m["id"],{}); fs=all_fields(m)
    return round(100*sum(bool(str(md.get(f["clave"],"")).strip()) for f in fs)/len(fs)) if fs else 0
def global_pct(payload): return round(sum(module_pct(m,payload) for m in MODULES)/len(MODULES)) if MODULES else 0

def consistency_alerts(payload):
    mods=payload.get("modulos",{}); fin=mods.get("finanzas",{}); a=[]
    if mods.get("mercadotecnia",{}).get("presupuesto_mkt","").strip() and not fin.get("presupuesto","").strip(): a.append("Mercadotecnia ya tiene presupuesto; debe integrarse en Finanzas.")
    if mods.get("operaciones",{}).get("proveedores","").strip() and not fin.get("presupuesto","").strip(): a.append("Operaciones ya identifica proveedores/costos; deben integrarse en Finanzas.")
    if mods.get("talento",{}).get("compensacion","").strip() and not fin.get("presupuesto","").strip(): a.append("Talento ya define compensaciones; deben integrarse en Finanzas.")
    if mods.get("legal",{}).get("costos_legales","").strip() and not fin.get("presupuesto","").strip(): a.append("Legal ya identifica costos; deben integrarse en Finanzas.")
    return a

def build_docx(payload,team,project):
    doc=Document(); doc.styles["Normal"].font.name="Arial"; doc.styles["Normal"].font.size=Pt(11)
    doc.add_heading("Proyecto Final – Plan de Negocios",0); doc.add_paragraph("Desarrollo de Emprendedores"); doc.add_paragraph(f"Equipo: {team}\nProyecto: {project}")
    for m in MODULES:
        md=payload.get("modulos",{}).get(m["id"],{}); doc.add_page_break(); doc.add_heading(f"{m['numero']} · {m['titulo']}",1); doc.add_paragraph(m["objetivo"])
        for s in m["sections"]:
            doc.add_heading(s["titulo"],2)
            for fld in s["fields"]:
                doc.add_heading(fld["etiqueta"],3); doc.add_paragraph(str(md.get(fld["clave"],"")).strip() or "[Pendiente]")
        doc.add_heading("Lista de verificación",2); checks=md.get("_checks",{})
        for c in m["checklist"]: doc.add_paragraph(("✓ " if checks.get(c) else "☐ ")+c)
    bio=BytesIO(); doc.save(bio); bio.seek(0); return bio

def save_project(project_id,payload): db.table("projects").update({"payload":payload,"updated_at":utc_now()}).eq("id",project_id).execute()
def logout():
    for k in list(st.session_state.keys()):
        if k.startswith("auth_") or k=="current_view": st.session_state.pop(k,None)
    st.rerun()

def create_teacher(name,email):
    email=email.strip().lower()
    if one("app_users",email=email): return None,"Ese correo ya existe."
    temp=random_password(); salt=new_salt()
    db.table("app_users").insert({"name":name.strip(),"email":email,"password_salt":salt,"password_hash":hash_secret(temp,salt),"is_admin":False,"is_teacher":True,"is_active":True,"created_at":utc_now(),"updated_at":utc_now()}).execute()
    return temp,None

def reset_staff_password(uid):
    temp=random_password(); salt=new_salt(); db.table("app_users").update({"password_salt":salt,"password_hash":hash_secret(temp,salt),"updated_at":utc_now()}).eq("id",uid).execute(); return temp

def create_group(name,teacher_id,period):
    return db.table("groups").insert({"name":name.strip(),"teacher_id":teacher_id,"period":period.strip(),"is_active":True,"created_at":utc_now()}).execute()

def create_team(group_id,team_code,team_name,project_name,pin):
    code=normalize_code(team_code)
    if one("teams",team_code=code): return "Ese código de equipo ya existe."
    salt=new_salt(); tres=db.table("teams").insert({"group_id":group_id,"team_code":code,"team_name":team_name.strip(),"pin_salt":salt,"pin_hash":hash_secret(pin,salt),"is_active":True,"created_at":utc_now(),"updated_at":utc_now()}).execute(); team=tres.data[0]
    db.table("projects").insert({"team_id":team["id"],"project_name":project_name.strip(),"payload":{"modulos":{}},"created_at":utc_now(),"updated_at":utc_now()}).execute(); return None

def reset_team_pin(team_id):
    pin="".join(secrets.choice(string.digits) for _ in range(6)); salt=new_salt(); db.table("teams").update({"pin_salt":salt,"pin_hash":hash_secret(pin,salt),"updated_at":utc_now()}).eq("id",team_id).execute(); return pin

# LOGIN
if not st.session_state.get("auth_type"):
    st.markdown('<div class="hero"><h1>🚀 Project Builder</h1><b>Desarrollo de Emprendedores · Plan de Negocios</b><div class="muted">Una sola plataforma para profesores, grupos y equipos.</div></div>',unsafe_allow_html=True)
    t1,t2=st.tabs(["Profesor / Administrador","Equipo"])
    with t1:
        st.subheader("Acceso docente"); email=st.text_input("Correo"); pw=st.text_input("Contraseña",type="password")
        if st.button("Entrar como docente",type="primary",use_container_width=True):
            u=staff_login(email,pw)
            if not u: st.error("Correo o contraseña incorrectos.")
            else: st.session_state.auth_type="staff"; st.session_state.auth_user=u; st.session_state.current_view="Mis grupos"; st.rerun()
    with t2:
        st.subheader("Acceso del equipo"); code=st.text_input("Código de equipo",key="team_code"); pin=st.text_input("PIN",type="password",key="team_pin")
        if st.button("Entrar al proyecto",use_container_width=True):
            team=team_login(code,pin)
            if not team: st.error("Código o PIN incorrecto.")
            else:
                project=one("projects",team_id=team["id"])
                if not project: st.error("El equipo todavía no tiene proyecto asignado.")
                else: st.session_state.auth_type="team"; st.session_state.auth_team=team; st.session_state.auth_project=project; st.rerun()
    st.stop()

# STAFF
if st.session_state.auth_type=="staff":
    user=st.session_state.auth_user
    st.markdown(f'<div class="hero"><h1>🚀 Project Builder</h1><b>{user["name"]}</b><br><span class="role">{"Administradora" if user["is_admin"] else ""}</span><span class="role">{"Profesora" if user["is_teacher"] else ""}</span></div>',unsafe_allow_html=True)
    with st.sidebar:
        options=[]
        if user["is_teacher"]: options.append("Mis grupos")
        if user["is_admin"]: options.append("Panel administrador")
        view=st.radio("Vista",options,index=options.index(st.session_state.get("current_view",options[0])) if st.session_state.get("current_view") in options else 0); st.session_state.current_view=view
        st.divider()
        if st.button("Cerrar sesión",use_container_width=True): logout()

    if view=="Panel administrador":
        st.header("Panel Administrador"); teachers=[u for u in rows("app_users") if u.get("is_teacher")]; groups=rows("groups"); teams=rows("teams"); projects=rows("projects")
        a,b,c,d=st.columns(4); a.metric("Profesores",len(teachers)); b.metric("Grupos",len(groups)); c.metric("Equipos",len(teams)); d.metric("Proyectos",len(projects))
        A,B,C=st.tabs(["Profesores","Grupos","Seguimiento general"])
        with A:
            st.subheader("Crear profesor")
            with st.form("new_teacher"):
                name=st.text_input("Nombre"); email=st.text_input("Correo"); submit=st.form_submit_button("Crear profesor")
            if submit:
                temp,err=create_teacher(name,email)
                if err: st.error(err)
                elif not name.strip() or not email.strip(): st.error("Completa nombre y correo.")
                else: st.success(f"Profesor creado. Contraseña temporal: {temp}"); st.warning("Cópiala y entrégala de forma privada.")
            for t in teachers:
                with st.expander(f"{t['name']} · {t['email']}"):
                    st.write(f"Administradora: {'Sí' if t['is_admin'] else 'No'} · Profesora: {'Sí' if t['is_teacher'] else 'No'}")
                    if t["id"]!=user["id"] and st.button("Restablecer contraseña",key=f"rst_{t['id']}"):
                        st.success(f"Nueva contraseña temporal: {reset_staff_password(t['id'])}")
        with B:
            st.subheader("Crear grupo"); opts={f"{t['name']} · {t['email']}":t["id"] for t in teachers}
            if opts:
                with st.form("new_group"):
                    gname=st.text_input("Nombre del grupo"); period=st.text_input("Periodo",placeholder="2026-2"); label=st.selectbox("Profesor responsable",list(opts)); gs=st.form_submit_button("Crear grupo")
                if gs:
                    if not gname.strip(): st.error("Escribe el nombre del grupo.")
                    else: create_group(gname,opts[label],period); st.success("Grupo creado."); st.rerun()
            for g in rows("groups"):
                t=one("app_users",id=g["teacher_id"]); st.write(f"**{g['name']}** · {g.get('period','')} · {t['name'] if t else 'Sin profesor'}")
        with C:
            st.subheader("Avance de todos los proyectos"); gb={g["id"]:g for g in groups}; tb={t["id"]:t for t in teachers}; teammap={t["id"]:t for t in teams}
            for p in projects:
                tm=teammap.get(p["team_id"]); g=gb.get(tm["group_id"]) if tm else None; tr=tb.get(g["teacher_id"]) if g else None; v=global_pct(p.get("payload") or {"modulos":{}})
                st.write(f"**{p['project_name']}** · {tm['team_code'] if tm else ''} · {g['name'] if g else ''} · {tr['name'] if tr else ''} · **{v}%** · {p.get('updated_at','')}"); st.progress(v/100)

    else:
        st.header("Mis grupos"); mygroups=rows("groups",teacher_id=user["id"])
        if not mygroups: st.info("Aún no tienes grupos asignados.")
        for g in mygroups:
            with st.expander(f"{g['name']} · {g.get('period','')}",expanded=True):
                st.subheader("Crear equipo")
                with st.form(f"team_{g['id']}"):
                    x,y=st.columns(2); code=x.text_input("Código único",key=f"code_{g['id']}"); tname=y.text_input("Nombre del equipo",key=f"tn_{g['id']}"); pname=st.text_input("Nombre del proyecto",key=f"pn_{g['id']}"); pin=st.text_input("PIN inicial",key=f"pin_{g['id']}"); sub=st.form_submit_button("Crear equipo y proyecto")
                if sub:
                    if not code.strip() or not tname.strip() or not pname.strip() or len(pin)<4: st.error("Completa todos los datos y usa PIN de al menos 4 caracteres.")
                    else:
                        err=create_team(g["id"],code,tname,pname,pin)
                        if err: st.error(err)
                        else: st.success("Equipo creado."); st.rerun()
                for tm in rows("teams",group_id=g["id"]):
                    p=one("projects",team_id=tm["id"]); payload=(p or {}).get("payload") or {"modulos":{}}; v=global_pct(payload); c1,c2,c3=st.columns([3,2,1]); c1.write(f"**{tm['team_code']} · {tm['team_name']}**"); c1.caption(p["project_name"] if p else "Sin proyecto"); c2.progress(v/100); c2.caption(f"{v}% · {(p or {}).get('updated_at','')}")
                    if c3.button("Nuevo PIN",key=f"pinreset_{tm['id']}"): st.success(f"Nuevo PIN: {reset_team_pin(tm['id'])}")
        st.stop()

# TEAM AREA
team=st.session_state.auth_team; project=st.session_state.auth_project; payload=project.get("payload") or {"modulos":{}}; payload.setdefault("modulos",{})
group=one("groups",id=team["group_id"]); teacher=one("app_users",id=group["teacher_id"]) if group else None
st.markdown(f'<div class="hero"><h1>🚀 Project Builder</h1><b>{project["project_name"]}</b><br><span class="muted">{team["team_code"]} · {team["team_name"]} · {group["name"] if group else ""} · {teacher["name"] if teacher else ""}</span></div>',unsafe_allow_html=True)
with st.sidebar:
    overall=global_pct(payload); st.metric("Avance global",f"{overall}%"); st.progress(overall/100); labels=[f"{m['numero']} · {m['titulo']} · {module_pct(m,payload)}%" for m in MODULES]; selected=st.radio("Ruta del proyecto",labels); module=MODULES[labels.index(selected)]; st.divider()
    if st.button("💾 Guardar avance",use_container_width=True): save_project(project["id"],payload); st.success("Guardado en línea.")
    st.download_button("📄 Descargar Plan de Negocios",build_docx(payload,team["team_code"],project["project_name"]),file_name=f"{team['team_code']}_Plan_de_Negocios.docx",mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",use_container_width=True)
    if st.button("Cerrar sesión",use_container_width=True): logout()

t1,t2,t3=st.tabs(["🧭 Construir","🔗 Coherencia","📋 Vista de entrega"])
with t1:
    st.header(f"{module['numero']} · {module['titulo']}"); st.info("**Objetivo:** "+module["objetivo"])
    with st.expander("♻️ Insumos que debes recuperar",expanded=True):
        for x in module["recupera"]: st.markdown(f"- {x}")
    md=payload["modulos"].setdefault(module["id"],{})
    for s in module["sections"]:
        st.subheader(s["titulo"])
        with st.expander("Indicaciones",expanded=True):
            for x in s["instructions"]: st.markdown(f"- {x}")
        for f in s["fields"]:
            md[f["clave"]]=st.text_area(f["etiqueta"],md.get(f["clave"],""),help=f.get("ayuda",""),height=145,key=f"{module['id']}__{f['clave']}")
    st.subheader("🤖 Uso responsable de IA"); a,b=st.columns(2)
    with a:
        st.markdown("**Sí puede apoyar en:**")
        for x in module["ia_si"]: st.markdown(f"- {x}")
    with b:
        st.markdown("**No debe utilizarse para:**")
        for x in module["ia_no"]: st.markdown(f"- {x}")
    st.subheader("Prompt de revisión"); content="\n".join(f"{f['etiqueta']}: {md.get(f['clave'],'')}" for f in all_fields(module)); st.code(f'''Actúa como asesor académico del curso Desarrollo de Emprendedores.\nRevisa el módulo "{module['titulo']}" del proyecto "{project['project_name']}".\nNo escribas el entregable por el equipo ni inventes datos, fuentes, cifras, competidores, proveedores o requisitos.\n1. Identifica inconsistencias.\n2. Señala evidencia faltante.\n3. Revisa conexión con módulos previos.\n4. Distingue dato comprobado, supuesto e hipótesis.\n5. Formula cinco preguntas concretas para mejorar.\n\nContenido:\n{content}''',language=None)
    st.subheader("✅ Checklist"); checks=md.setdefault("_checks",{})
    for c in module["checklist"]: checks[c]=st.checkbox(c,checks.get(c,False),key=f"{module['id']}__c__{c}")
    if st.button("Guardar este módulo",type="primary"): save_project(project["id"],payload); st.success("Módulo guardado.")
with t2:
    st.header("Coherencia transversal"); alerts=consistency_alerts(payload)
    if alerts:
        for a in alerts: st.warning(a)
    else: st.success("No hay alertas básicas pendientes.")
    for m in MODULES:
        v=module_pct(m,payload); st.write(f"**{m['numero']} · {m['titulo']}** — {v}%"); st.progress(v/100)
with t3:
    st.header("Vista de entrega")
    for m in MODULES:
        v=module_pct(m,payload)
        with st.expander(f"{m['numero']} · {m['titulo']} — {v}%"):
            ch=payload.get("modulos",{}).get(m["id"],{}).get("_checks",{})
            for c in m["checklist"]: st.write(("✅ " if ch.get(c) else "⬜ ")+c)
