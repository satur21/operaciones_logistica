
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Operaciones vs Logística", layout="wide")
st.title("Dashboard Comparativo: Operaciones vs Logística")
st.caption("Identifica desequilibrios entre lo que se produce y lo que se mueve.")

# Sidebar uploads
st.sidebar.header("Datos")
prod_file = st.sidebar.file_uploader("Production CSV", type=["csv"])
log_file  = st.sidebar.file_uploader("Logistics CSV", type=["csv"])
inv_file  = st.sidebar.file_uploader("Inventory CSV", type=["csv"])

@st.cache_data
def load_defaults():
    prod = pd.read_csv("sample_data/production.csv", parse_dates=["date"])
    log  = pd.read_csv("sample_data/logistics.csv", parse_dates=["date"])
    inv  = pd.read_csv("sample_data/inventory.csv", parse_dates=["week_ending"])
    return prod, log, inv

if prod_file and log_file and inv_file:
    prod = pd.read_csv(prod_file, parse_dates=["date"])
    log  = pd.read_csv(log_file, parse_dates=["date"])
    inv  = pd.read_csv(inv_file, parse_dates=["week_ending"])
else:
    st.sidebar.info("Usando datos de ejemplo (sample_data/*)")
    prod, log, inv = load_defaults()

# Filters
min_d = max(prod["date"].min(), log["date"].min())
max_d = min(prod["date"].max(), log["date"].max())
date_range = st.slider("Rango de fechas", min_value=min_d.to_pydatetime(),
                       max_value=max_d.to_pydatetime(),
                       value=(min_d.to_pydatetime(), max_d.to_pydatetime()))
prod_f = prod[(prod["date"]>=pd.Timestamp(date_range[0])) & (prod["date"]<=pd.Timestamp(date_range[1]))]
log_f  = log[(log["date"]>=pd.Timestamp(date_range[0])) & (log["date"]<=pd.Timestamp(date_range[1]))]

# KPIs
total_produced = int(prod_f["produced_qty"].sum())
total_delivered = int(log_f["delivered_qty"].sum())
demand = int(prod_f["orders"].sum())
on_time = round(log_f["on_time_rate"].mean()*100, 1) if len(log_f)>0 else 0.0
cpu = round((log_f["transport_cost"].sum() / max(total_delivered,1)), 2)

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Producido", f"{total_produced:,}")
c2.metric("Entregado", f"{total_delivered:,}")
c3.metric("Demanda (órdenes)", f"{demand:,}")
c4.metric("Puntualidad media", f"{on_time}%")
c5.metric("Coste/Unidad entregada", f"{cpu}")

imbalance = (total_produced - total_delivered) / max(total_produced,1)
if imbalance > 0.15:
    st.warning("🔶 Producido muy por encima de lo entregado (posible acumulación de inventario).")
elif imbalance < -0.15:
    st.warning("🔶 Entregado por encima de lo producido (posible rotura o retraso en producción).")
else:
    st.success("✅ Producción y entregas relativamente equilibradas.")

# Side-by-side charts
st.subheader("Comparativa por categorías")
l1, l2 = st.columns(2)
with l1:
    by_sku = prod_f.groupby("sku", as_index=False)["produced_qty"].sum()
    fig = px.bar(by_sku, x="sku", y="produced_qty", title="Producción por SKU", text_auto=True)
    st.plotly_chart(fig, use_container_width=True)
with l2:
    by_route = log_f.groupby("route", as_index=False)["delivered_qty"].sum()
    fig = px.bar(by_route, x="route", y="delivered_qty", title="Entregas por Ruta", text_auto=True)
    st.plotly_chart(fig, use_container_width=True)

t1, t2 = st.columns(2)
with t1:
    prod_trend = prod_f.groupby("date", as_index=False)["produced_qty"].sum()
    st.plotly_chart(px.line(prod_trend, x="date", y="produced_qty", title="Tendencia Producción"), use_container_width=True)
with t2:
    del_trend = log_f.groupby("date", as_index=False)["delivered_qty"].sum()
    st.plotly_chart(px.line(del_trend, x="date", y="delivered_qty", title="Tendencia Entregas"), use_container_width=True)

# Sankey: Planta -> Almacén -> Clientes (por SKU)
st.subheader("Flujo de Inventario (Sankey)")
latest = inv.sort_values("week_ending").groupby("sku").tail(1)

labels = []
sources = []
targets = []
values  = []

for _, r in latest.iterrows():
    s_label = f"Planta {r['sku']}"
    t_label = f"Almacén {r['sku']}"
    for lab in (s_label, t_label):
        if lab not in labels: labels.append(lab)
    s = labels.index(s_label); t = labels.index(t_label)
    sources.append(s); targets.append(t); values.append(max(int(r["plant_inventory"]),1))

if "Clientes" not in labels: labels.append("Clientes")
client_idx = labels.index("Clientes")
for _, r in latest.iterrows():
    t_label = f"Almacén {r['sku']}"
    t = labels.index(t_label)
    est = prod_f[prod_f['sku']==r['sku']]["orders"].sum()
    if est == 0: est = r["warehouse_inventory"] * 0.8
    sources.append(t); targets.append(client_idx); values.append(max(int(est),1))

fig_s = go.Figure(go.Sankey(node=dict(label=labels, pad=20, thickness=15),
                             link=dict(source=sources, target=targets, value=values)))
fig_s.update_layout(title_text="Planta → Almacén → Clientes", font_size=12)
st.plotly_chart(fig_s, use_container_width=True)

st.caption("Ajusta el rango temporal para identificar periodos con desbalance.")
