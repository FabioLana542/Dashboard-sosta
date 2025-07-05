import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re
import locale

# --- CONFIGURAZIONE PAGINA STREAMLIT E LOCALIZZAZIONE---
st.set_page_config(
    page_title="Dashboard Incassi Parcheggi",
    page_icon="🚗",
    layout="wide"
)

try:
    locale.setlocale(locale.LC_ALL, 'it_IT.UTF-8')
except locale.Error:
    st.warning("Localizzazione italiana non trovata, potrebbero esserci problemi di formattazione. Verrà usata quella di default.")

SERVIZI_ORDER = ["Autorizzazioni", "Abbonamenti", "Parcometri", "Hub Sosta (App)", "Tap&Park"]
SERVIZI_FILENAME_MAP = {
    "Autorizzazioni": "Autorizzazioni", "Abbonamenti": "Abbonamenti",
    "Parcometro": "Parcometri", "ParkingHUB": "Hub Sosta (App)", "Tap&Park": "Tap&Park"
}

def format_europeo(valore, tipo='valuta'):
    if pd.isna(valore): return "N/A"
    try:
        if tipo == 'valuta': return locale.currency(valore, symbol=True, grouping=True)
        elif tipo == 'numero': return locale.format_string("%.0f", valore, grouping=True)
        return valore
    except (ValueError, TypeError): return valore

@st.cache_data
def load_and_process_data_from_reports(data_folder):
    if not os.path.exists(data_folder):
        st.error(f"Cartella dei dati non trovata: '{data_folder}'.")
        return None
    all_data = []
    report_pattern = re.compile(r'Riepilogo_(.+)_(?:Mensile)\.xlsx$', re.IGNORECASE)
    for filename in os.listdir(data_folder):
        if not filename.startswith('Riepilogo_'): continue
        match = report_pattern.search(filename)
        if not match: continue
        servizio_key, servizio_nome = match.group(1), SERVIZI_FILENAME_MAP.get(match.group(1), "Sconosciuto")
        if servizio_nome == "Sconosciuto": continue
        try:
            df = pd.read_excel(os.path.join(data_folder, filename))
            df['Servizio'] = servizio_nome
            all_data.append(df)
        except Exception as e:
            st.warning(f"Impossibile leggere il file '{filename}': {e}")
    if not all_data:
        st.error("Nessun file di riepilogo valido trovato.")
        return None
    dati_completi = pd.concat(all_data, ignore_index=True)
    dati_completi['DATA_ORA_INSERIMENTO'] = pd.to_datetime(dati_completi['Mese'] + '-01')
    dati_completi['Anno'] = dati_completi['DATA_ORA_INSERIMENTO'].dt.year
    dati_completi['Mese'] = dati_completi['DATA_ORA_INSERIMENTO'].dt.month
    dati_completi = dati_completi.rename(columns={'Numero Transazioni': 'Numero Titoli', 'Importo Totale': 'Importo Totale'})
    rettifiche = [
        {'Anno': 2024, 'Mese': 1, 'Servizio': 'Hub Sosta (App)', 'Importo Totale': 3130.5, 'Numero Titoli': 1, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-01-31')},
        {'Anno': 2024, 'Mese': 2, 'Servizio': 'Hub Sosta (App)', 'Importo Totale': 3130.5, 'Numero Titoli': 1, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-02-29')},
        {'Anno': 2024, 'Mese': 3, 'Servizio': 'Hub Sosta (App)', 'Importo Totale': 3130.5, 'Numero Titoli': 1, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-03-31')}
    ]
    dati_finali = pd.concat([dati_completi, pd.DataFrame(rettifiche)], ignore_index=True)
    dati_finali['Servizio'] = pd.Categorical(dati_finali['Servizio'], categories=SERVIZI_ORDER, ordered=True)
    return dati_finali

def display_analysis_for_year(df, year):
    df_anno = df[df['Anno'] == year].copy()
    if df_anno.empty:
        st.warning(f"Nessun dato disponibile per l'anno {year}.")
        return
    data_inizio, data_fine = df_anno['DATA_ORA_INSERIMENTO'].min(), df_anno['DATA_ORA_INSERIMENTO'].max()
    mesi_italiani = {m: pd.Timestamp(2000, m, 1).strftime('%B') for m in range(1, 13)}
    data_inizio_str = f"{data_inizio.day:02d} {mesi_italiani.get(data_inizio.month, '')}"
    data_fine_str = f"30 {mesi_italiani.get(data_fine.month, '')}" if year == 2024 and data_fine.month == 6 else f"{data_fine.day:02d} {mesi_italiani.get(data_fine.month, '')}"
    st.header(f"Riepilogo Dati Anno {year} (dal {data_inizio_str} al {data_fine_str})")
    incasso_totale, transazioni_totali = df_anno['Importo Totale'].sum(), df_anno['Numero Titoli'].sum()
    col1, col2 = st.columns(2)
    col1.metric("Incasso Totale Annuo", format_europeo(incasso_totale))
    col2.metric("Numero Titoli Totali", format_europeo(transazioni_totali, 'numero'))
    dati_per_servizio = df_anno.groupby('Servizio', observed=False)[['Importo Totale', 'Numero Titoli']].sum().reset_index()
    dati_per_servizio['Percentuale'] = (dati_per_servizio['Importo Totale'] / incasso_totale * 100) if incasso_totale > 0 else 0
    dati_per_servizio['Redditività Media'] = (dati_per_servizio['Importo Totale'] / dati_per_servizio['Numero Titoli'].replace(0, pd.NA)).fillna(0)
    st.subheader("Dettaglio per Tipologia di Servizio")
    riga_totale = pd.DataFrame({'Servizio': ['TOTALE'], 'Importo Totale': [incasso_totale], 'Numero Titoli': [transazioni_totali], 'Percentuale': [100.0], 'Redditività Media': [incasso_totale / transazioni_totali if transazioni_totali > 0 else 0]})
    tabella_visualizzata = pd.concat([dati_per_servizio, riga_totale], ignore_index=True)
    st.dataframe(tabella_visualizzata.style.format({'Importo Totale': lambda x: format_europeo(x), 'Numero Titoli': lambda x: format_europeo(x, 'numero'), 'Percentuale': '{:.2f}%', 'Redditività Media': lambda x: format_europeo(x)}).apply(lambda x: ['background-color: #D9E1F2; font-weight: bold'] * len(x) if x.name == len(tabella_visualizzata) - 1 else [''] * len(x), axis=1), use_container_width=True, hide_index=True)
    col1_graf, col2_graf = st.columns(2)
    with col1_graf:
        st.subheader("Composizione Incassi"); fig_pie = px.pie(dati_per_servizio, names='Servizio', values='Importo Totale', title=f'Distribuzione Incassi {year}', hole=0.3); fig_pie.update_traces(textposition='inside', textinfo='percent+label', sort=False); st.plotly_chart(fig_pie, use_container_width=True)
    with col2_graf:
        st.subheader("Confronto Servizi (per Incasso)"); fig_bar = px.bar(dati_per_servizio, x='Servizio', y='Importo Totale', title=f'Incassi per Servizio {year}', text_auto=False); fig_bar.update_traces(texttemplate=[format_europeo(val) for val in dati_per_servizio['Importo Totale']], textposition="outside"); st.plotly_chart(fig_bar, use_container_width=True)
    st.subheader("Andamento Temporale Mensile per Servizio")
    andamento_mensile = df_anno.pivot_table(values='Importo Totale', index='Mese', columns='Servizio', aggfunc='sum', observed=False).fillna(0)
    df_plot = andamento_mensile.reset_index().melt(id_vars='Mese', var_name='Servizio', value_name='Importo')
    nomi_mesi_map = {m: pd.Timestamp(2000, m, 1).strftime('%b') for m in range(1, 13)}
    df_plot['MeseStr'] = df_plot['Mese'].map(nomi_mesi_map)
    fig_line_dettaglio = px.line(df_plot, x='MeseStr', y='Importo', color='Servizio', title=f'Andamento Incassi Mensili per Servizio - {year}', markers=True, labels={"Importo": "Incasso (€)", "MeseStr": "Mese", "Servizio": "Servizio"})
    st.plotly_chart(fig_line_dettaglio, use_container_width=True)
    st.info("💡 Clicca sugli elementi nella legenda del grafico per nascondere o mostrare le linee.")

st.title("🚗 Dashboard Analisi Incassi Parcheggi"); st.markdown("Applicazione per il confronto degli incassi su base annuale e mensile.")
ANNO_1, ANNO_2, IMPORTO_RETTIFICA = 2024, 2025, -1350.84
full_data = load_and_process_data_from_reports("data_sources")
if full_data is None: st.stop()

df_feb_2024 = full_data[(full_data['Anno'] == 2024) & (full_data['Mese'] == 2)]
incassi_feb_2024 = df_feb_2024.groupby('Servizio', observed=False)['Importo Totale'].sum()
totale_incasso_feb_2024 = incassi_feb_2024.sum()
RETTIFICA_PROPORZIONALE_DF = pd.DataFrame()
if totale_incasso_feb_2024 > 0:
    proporzioni = incassi_feb_2024 / totale_incasso_feb_2024
    lista_rettifiche = [{'Anno': 2024, 'Mese': 2, 'Servizio': s, 'Importo Totale': IMPORTO_RETTIFICA * p, 'Numero Titoli': 0, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-02-29')} for s, p in proporzioni.items()]
    RETTIFICA_PROPORZIONALE_DF = pd.DataFrame(lista_rettifiche)
    RETTIFICA_PROPORZIONALE_DF['Servizio'] = pd.Categorical(RETTIFICA_PROPORZIONALE_DF['Servizio'], categories=SERVIZI_ORDER, ordered=True)

st.sidebar.title("Note e Cronistoria")
# (Codice sidebar omesso per brevità)
st.sidebar.markdown("---")
st.sidebar.subheader("Anno 2023")
st.sidebar.markdown("- **Fine Ottobre 2023**: Assunzione di Tombolini e Marinelli.\n- **18/10/2023**: Attivazione parcometri annuali.\n- **15/12/2023**: Attivazione ARU per abbonamenti.\n- **20/12/2023**: Licenziamento Marinelli.")
st.sidebar.markdown("---")
st.sidebar.subheader("Anno 2024")
st.sidebar.markdown(f"- **Rettifica Bisestile**: L'opzione sottrae un totale di **{format_europeo(abs(IMPORTO_RETTIFICA))}** dagli incassi di Febbraio 2024, distribuendoli proporzionalmente.")
st.sidebar.markdown("- **01/01/2024**: Assunzione Lancelotti.\n- **01/04/2024**: Attivazione ParkingHUB (MooneyGo).\n- **01/04/2024**: Inizio sanzionamento.\n- **01/04/2024**: **Rettifica Manuale**: Aggiunti € 3.130,50/mese per Gen-Mar a 'Hub Sosta (App)'.\n- **03/04/2024**: Attivazione parcometri estivi.\n- **27/04/2024**: Attivazione POS su parcometri.\n- **21/05/2024**: Attivazione EasyPark.\n- **01/06/2024**: Stop autorizzazioni da PL.")
st.sidebar.markdown("---")
st.sidebar.subheader("Anno 2025")
st.sidebar.markdown("- **07/04/2025**: Licenziamento Lancelotti.\n- **09/05/2025**: Assunzione Viti.")

tab_confronto, tab_anno1, tab_anno2 = st.tabs([f"📊 Confronto {ANNO_1} vs {ANNO_2}", f"🗓️ Dettaglio {ANNO_1}", f"🗓️ Dettaglio {ANNO_2}"])

with tab_confronto:
    st.header(f"Andamento Temporale e Confronto {ANNO_1} vs {ANNO_2} (dal 01 gennaio al 30 giugno)")
    adjust_main = st.checkbox(f"✅ Applica rettifica anno bisestile ({format_europeo(IMPORTO_RETTIFICA)})", key="leap_main")
    dati_calcolo = full_data.copy()
    if adjust_main and not RETTIFICA_PROPORZIONALE_DF.empty:
        dati_calcolo = pd.concat([dati_calcolo, RETTIFICA_PROPORZIONALE_DF], ignore_index=True)

    def colora_confronto_variazione(val):
        if pd.isna(val) or val == 0: return 'color: grey'
        return 'color: green' if val > 0 else 'color: red'
    
    def create_and_display_comparison_table(df, value_col, title, is_currency=True):
        st.subheader(title)
        pivot = df.pivot_table(values=value_col, index='Servizio', columns='Anno', aggfunc='sum', observed=False).fillna(0)
        pivot = pivot.reindex(columns=[ANNO_1, ANNO_2], fill_value=0)
        pivot['Variazione Assoluta'] = pivot[ANNO_2] - pivot[ANNO_1]
        pivot['Variazione %'] = (pivot['Variazione Assoluta'] / pivot[ANNO_1].replace(0, pd.NA)) * 100
        totali = pivot.sum()
        totali['Variazione %'] = (totali['Variazione Assoluta'] / totali[ANNO_1]) * 100 if totali[ANNO_1] != 0 else 0
        totali.name = 'TOTALE'
        pivot_con_totale = pd.concat([pivot, totali.to_frame().T])
        pivot_con_totale.columns = [str(c) for c in pivot_con_totale.columns]
        st.dataframe(pivot_con_totale.style.format({str(ANNO_1): lambda x: format_europeo(x, 'valuta' if is_currency else 'numero'), str(ANNO_2): lambda x: format_europeo(x, 'valuta' if is_currency else 'numero'), 'Variazione Assoluta': lambda x: f"{'+' if x >= 0 else ''}{format_europeo(x, 'valuta' if is_currency else 'numero')}", 'Variazione %': '{:+.2f}%'}).map(colora_confronto_variazione, subset=['Variazione %']).apply(lambda row: ['font-weight: bold; background-color: #D9E1F2'] * len(row) if row.name == 'TOTALE' else [''] * len(row), axis=1), use_container_width=True)

    create_and_display_comparison_table(dati_calcolo, 'Importo Totale', "Confronto Incassi per Servizio", is_currency=True)
    st.markdown("---")
    create_and_display_comparison_table(dati_calcolo, 'Numero Titoli', "Confronto Numero Titoli per Servizio", is_currency=False)
    
    st.markdown("---")
    st.subheader("Confronto Redditività Media per Servizio (€/Titolo)")
    pivot_importi = dati_calcolo.pivot_table(values='Importo Totale', index='Servizio', columns='Anno', aggfunc='sum', observed=False).fillna(0)
    pivot_titoli = dati_calcolo.pivot_table(values='Numero Titoli', index='Servizio', columns='Anno', aggfunc='sum', observed=False).fillna(0)
    redditivita = (pivot_importi / pivot_titoli.replace(0, pd.NA)).reindex(columns=[ANNO_1, ANNO_2]).fillna(0)
    redditivita['Variazione Assoluta'] = redditivita[ANNO_2] - redditivita[ANNO_1]
    redditivita['Variazione %'] = (redditivita['Variazione Assoluta'] / redditivita[ANNO_1].replace(0, pd.NA)) * 100
    tot_imp_1, tot_tit_1 = pivot_importi.get(ANNO_1, pd.Series(0)).sum(), pivot_titoli.get(ANNO_1, pd.Series(0)).sum()
    tot_imp_2, tot_tit_2 = pivot_importi.get(ANNO_2, pd.Series(0)).sum(), pivot_titoli.get(ANNO_2, pd.Series(0)).sum()
    redd_tot_1 = tot_imp_1 / tot_tit_1 if tot_tit_1 > 0 else 0
    redd_tot_2 = tot_imp_2 / tot_tit_2 if tot_tit_2 > 0 else 0
    riga_tot_redd = pd.DataFrame({'Variazione Assoluta': [redd_tot_2 - redd_tot_1], 'Variazione %': [(redd_tot_2 - redd_tot_1) / redd_tot_1 * 100 if redd_tot_1 > 0 else 0]}, index=['TOTALE'])
    riga_tot_redd[ANNO_1] = redd_tot_1
    riga_tot_redd[ANNO_2] = redd_tot_2
    redditivita_con_totale = pd.concat([redditivita, riga_tot_redd])
    redditivita_con_totale.columns = [str(c) for c in redditivita_con_totale.columns]
    st.dataframe(redditivita_con_totale.style.format({str(ANNO_1): lambda x: format_europeo(x), str(ANNO_2): lambda x: format_europeo(x), 'Variazione Assoluta': lambda x: f"{'+' if x >= 0 else ''}{format_europeo(x)}", 'Variazione %': '{:+.2f}%'}).map(colora_confronto_variazione, subset=['Variazione %']).apply(lambda row: ['font-weight: bold; background-color: #D9E1F2'] * len(row) if row.name == 'TOTALE' else [''] * len(row), axis=1), use_container_width=True)

    st.markdown("---")
    st.header("Analisi Dettagliata per Linea di Prodotto (Base Mensile)")
    
    col_metric, col_menu = st.columns([1, 1])
    with col_metric: metric_selezionata = st.radio("Scegli la metrica:", ('Incasso Totale', 'Numero Titoli'), key="radio_metric")
    with col_menu: servizio_selezionato = st.selectbox("Seleziona una vista:", options=['Tutti i Servizi', 'Sosta Occasionale (Aggregato)'] + SERVIZI_ORDER, key="filtro_servizio")
    
    value_col, y_label, is_curr = ('Importo Totale', 'Incasso Totale (€)', True) if metric_selezionata == 'Incasso Totale' else ('Numero Titoli', 'Numero Titoli', False)
    
    if servizio_selezionato == 'Tutti i Servizi': dati_filtrati = dati_calcolo.copy()
    elif servizio_selezionato == 'Sosta Occasionale (Aggregato)': dati_filtrati = dati_calcolo[dati_calcolo['Servizio'].isin(['Parcometri', 'Hub Sosta (App)', 'Tap&Park'])].copy()
    else: dati_filtrati = dati_calcolo[dati_calcolo['Servizio'] == servizio_selezionato].copy()
        
    pivot_confronto = dati_filtrati.pivot_table(values=value_col, index='Mese', columns='Anno', aggfunc='sum', observed=False).fillna(0).reindex(columns=[ANNO_1, ANNO_2], fill_value=0)
    nomi_mesi = {m: pd.Timestamp(2000, m, 1).strftime('%B') for m in range(1, 13)}
    pivot_confronto = pivot_confronto.loc[pivot_confronto.index.isin(nomi_mesi.keys())].copy()
    pivot_confronto.index = pivot_confronto.index.map(nomi_mesi)
    pivot_confronto['Variazione Assoluta'] = pivot_confronto[ANNO_2] - pivot_confronto[ANNO_1]
    pivot_confronto['Variazione %'] = (pivot_confronto['Variazione Assoluta'] / pivot_confronto[ANNO_1].replace(0, pd.NA)) * 100
    
    totali = pivot_confronto.sum()
    totali['Variazione %'] = (totali['Variazione Assoluta'] / totali[ANNO_1]) * 100 if totali[ANNO_1] != 0 else 0
    totali.name = 'TOTALE'
    pivot_confronto_con_totale = pd.concat([pivot_confronto, totali.to_frame().T])
    pivot_confronto_con_totale.columns = [str(c) for c in pivot_confronto_con_totale.columns]
    
    st.dataframe(pivot_confronto_con_totale.style.format({str(ANNO_1): lambda x: format_europeo(x, 'valuta' if is_curr else 'numero'), str(ANNO_2): lambda x: format_europeo(x, 'valuta' if is_curr else 'numero'), 'Variazione Assoluta': lambda x: f"{'+' if x >= 0 else ''}{format_europeo(x, 'valuta' if is_curr else 'numero')}", 'Variazione %': '{:+.2f}%'}).map(colora_confronto_variazione, subset=['Variazione %']).apply(lambda row: ['font-weight: bold; background-color: #D9E1F2'] * len(row) if row.name == 'TOTALE' else [''] * len(row), axis=1), use_container_width=True)

    df_plot_line = pivot_confronto[[ANNO_1, ANNO_2]].copy()
    fig_line = px.line(df_plot_line, title=f"Confronto Mensile {metric_selezionata} per: {servizio_selezionato}", markers=True, labels={"value": y_label, "index": "Mese", "variable": "Anno"})
    fig_line.update_layout(yaxis_title=y_label, xaxis_title="Mese")
    st.plotly_chart(fig_line, use_container_width=True)

with tab_anno1:
    display_analysis_for_year(full_data, ANNO_1)
with tab_anno2:
    display_analysis_for_year(full_data, ANNO_2)