import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re
from streamlit_gspread import GSpreadConnection

# --- CONFIGURAZIONE PAGINA STREAMLIT ---
st.set_page_config(
    page_title="Dashboard Incassi Parcheggi",
    page_icon="🚗",
    layout="wide"
)

# --- FUNZIONI HELPER E COSTANTI ---
def format_europeo(valore, tipo='valuta'):
    if pd.isna(valore): return "N/A"
    try:
        if tipo == 'valuta': return f"€ {valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        elif tipo == 'numero': return f"{valore:,.0f}".replace(",", ".")
        return valore
    except (ValueError, TypeError): return valore

# --- GESTIONE NOTE CON GOOGLE SHEETS ---

# Stabilisce la connessione a Google Sheets usando i Secrets di Streamlit
# st.connection si occupa di tutto in modo sicuro e automatico.
conn = st.connection("gspread", type=GSpreadConnection)

# URL del tuo Google Sheet (da inserire nei secrets se vuoi tenerlo privato,
# altrimenti puoi metterlo direttamente qui se il foglio è accessibile)
# Per semplicità lo mettiamo qui, ma per massima sicurezza andrebbe in st.secrets
# Esempio: GOOGLE_SHEET_URL = st.secrets["connections"]["gspread"]["spreadsheet"]
NOME_FOGLIO_NOTE = "DashboardAppNotes" 

@st.cache_data(ttl=3600) # Cache per 1 ora per non sovraccaricare le API
def get_worksheet():
    """Ottiene il worksheet. Messo in cache per performance."""
    return conn.connect(spreadsheet=NOME_FOGLIO_NOTE).worksheet("notes")

def load_notes_from_gsheet():
    """Carica le note da Google Sheets e le restituisce come dizionario."""
    try:
        ws = get_worksheet()
        df_notes = conn.read(worksheet=ws, usecols=[0, 1, 2], header=0)
        df_notes = df_notes.dropna(how="all") # Rimuove righe completamente vuote
        
        notes_dict = {}
        for _, row in df_notes.iterrows():
            table_key = row["table_key"]
            row_index = row["row_index"]
            note_text = row.get("note_text", "") # Usa .get per sicurezza
            
            if pd.isna(table_key) or pd.isna(row_index): continue

            if table_key not in notes_dict:
                notes_dict[table_key] = {}
            
            notes_dict[table_key][str(row_index)] = str(note_text) if not pd.isna(note_text) else ""
            
        st.sidebar.info("Note caricate da Google Sheets.")
        return notes_dict
    except Exception as e:
        st.error(f"Impossibile caricare le note da Google Sheets: {e}")
        return {}

def save_notes_to_gsheet(notes_dict):
    """Salva il dizionario di note su Google Sheets, sovrascrivendo i dati esistenti."""
    all_notes = []
    for table_key, notes in notes_dict.items():
        for row_index, text in notes.items():
            if text:
                all_notes.append([table_key, str(row_index), text])
    
    if not all_notes:
        st.sidebar.info("Nessuna nota da salvare.")
        return

    try:
        df_to_save = pd.DataFrame(all_notes, columns=["table_key", "row_index", "note_text"])
        ws = get_worksheet()
        ws.clear() # Pulisce il foglio
        conn.update(worksheet=ws, data=df_to_save) # Scrive i nuovi dati
        st.sidebar.success("Note salvate con successo su Google Sheets!")
        st.cache_data.clear() # Pulisce la cache per ricaricare i dati aggiornati
    except Exception as e:
        st.sidebar.error(f"Errore durante il salvataggio su Google Sheets: {e}")


# --- INIZIALIZZAZIONE SESSION STATE ---
if 'notes' not in st.session_state:
    st.session_state.notes = load_notes_from_gsheet()

SERVIZI_ORDER = ["Autorizzazioni", "Abbonamenti", "Parcometri", "Hub Sosta (App)", "Tap&Park (ricariche)"]
SERVIZI_FILENAME_MAP = {
    "Autorizzazioni": "Autorizzazioni", "Abbonamenti": "Abbonamenti",
    "Parcometro": "Parcometri", "ParkingHUB": "Hub Sosta (App)", "Tap&Park": "Tap&Park (ricariche)"
}

# --- 1. FUNZIONE DI CARICAMENTO E PROCESSING DATI ---
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
    dati_completi['DATA_ORA_INSERIMENTO'] = pd.to_datetime(dati_completi['Mese'].astype(str) + '-01')
    dati_completi['Anno'] = dati_completi['DATA_ORA_INSERIMENTO'].dt.year
    dati_completi['Mese'] = dati_completi['DATA_ORA_INSERIMENTO'].dt.month
    dati_completi = dati_completi.rename(columns={'Numero Transazioni': 'Numero Titoli'})
    rettifiche = [
        {'Anno': 2024, 'Mese': 1, 'Servizio': 'Hub Sosta (App)', 'Importo Totale': 3130.5, 'Numero Titoli': 1, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-01-31')},
        {'Anno': 2024, 'Mese': 2, 'Servizio': 'Hub Sosta (App)', 'Importo Totale': 3130.5, 'Numero Titoli': 1, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-02-29')},
        {'Anno': 2024, 'Mese': 3, 'Servizio': 'Hub Sosta (App)', 'Importo Totale': 3130.5, 'Numero Titoli': 1, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-03-31')}
    ]
    dati_finali = pd.concat([dati_completi, pd.DataFrame(rettifiche)], ignore_index=True)
    dati_finali['Servizio'] = pd.Categorical(dati_finali['Servizio'], categories=SERVIZI_ORDER, ordered=True)
    return dati_finali

# --- 2. FUNZIONE PER VISUALIZZARE L'ANALISI DI UN ANNO ---
def display_analysis_for_year(df, year):
    # ... (questa funzione rimane identica)
    df_anno = df[df['Anno'] == year].copy()
    if df_anno.empty:
        st.warning(f"Nessun dato disponibile per l'anno {year}.")
        return
    data_inizio, data_fine = df_anno['DATA_ORA_INSERIMENTO'].min(), df_anno['DATA_ORA_INSERIMENTO'].max()
    mesi_italiani = {m: pd.Timestamp(2000, m, 1).strftime('%B') for m in range(1, 13)}
    data_inizio_str, data_fine_str = f"{data_inizio.day:02d} {mesi_italiani.get(data_inizio.month, '')}", f"30 {mesi_italiani.get(data_fine.month, '')}" if year == 2024 and data_fine.month == 6 else f"{data_fine.day:02d} {mesi_italiani.get(data_fine.month, '')}"
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
    col1_graf, col2_graf = st.columns(2);
    with col1_graf: st.subheader("Composizione Incassi"); fig_pie = px.pie(dati_per_servizio, names='Servizio', values='Importo Totale', title=f'Distribuzione Incassi {year}', hole=0.3); fig_pie.update_traces(textposition='inside', textinfo='percent+label', sort=False); st.plotly_chart(fig_pie, use_container_width=True)
    with col2_graf: st.subheader("Confronto Servizi (per Incasso)"); fig_bar = px.bar(dati_per_servizio, x='Servizio', y='Importo Totale', title=f'Incassi per Servizio {year}', text_auto=False); fig_bar.update_traces(texttemplate=[format_europeo(val) for val in dati_per_servizio['Importo Totale']], textposition="outside"); st.plotly_chart(fig_bar, use_container_width=True)
    st.subheader("Andamento Temporale Mensile per Servizio"); andamento_mensile = df_anno.pivot_table(values='Importo Totale', index='Mese', columns='Servizio', aggfunc='sum', observed=False).fillna(0); df_plot = andamento_mensile.reset_index().melt(id_vars='Mese', var_name='Servizio', value_name='Importo'); nomi_mesi_map = {m: pd.Timestamp(2000, m, 1).strftime('%b') for m in range(1, 13)}; df_plot['MeseStr'] = df_plot['Mese'].map(nomi_mesi_map); fig_line_dettaglio = px.line(df_plot, x='MeseStr', y='Importo', color='Servizio', title=f'Andamento Incassi Mensili per Servizio - {year}', markers=True, labels={"Importo": "Incasso (€)", "MeseStr": "Mese", "Servizio": "Servizio"}); st.plotly_chart(fig_line_dettaglio, use_container_width=True); st.info("💡 Clicca sugli elementi nella legenda del grafico per nascondere o mostrare le linee.")


# --- 3. CORPO PRINCIPALE DELL'APPLICAZIONE ---
st.title("🚗 Dashboard Analisi Incassi Parcheggi"); st.markdown("Applicazione per il confronto degli incassi su base annuale e mensile.")
ANNO_1, ANNO_2, IMPORTO_RETTIFICA = 2024, 2025, -1350.84
full_data = load_and_process_data_from_reports("data_sources")
if full_data is None: st.stop()

df_feb_2024 = full_data[(full_data['Anno'] == 2024) & (full_data['Mese'] == 2)]
incassi_feb_2024 = df_feb_2024.groupby('Servizio', observed=False)['Importo Totale'].sum()
RETTIFICA_PROPORZIONALE_DF = pd.DataFrame()
if not incassi_feb_2024.empty and incassi_feb_2024.sum() > 0:
    proporzioni = incassi_feb_2024 / incassi_feb_2024.sum()
    lista_rettifiche = [{'Anno': 2024, 'Mese': 2, 'Servizio': s, 'Importo Totale': IMPORTO_RETTIFICA * p, 'Numero Titoli': 0, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-02-29')} for s, p in proporzioni.items()]
    RETTIFICA_PROPORZIONALE_DF = pd.DataFrame(lista_rettifiche)
    RETTIFICA_PROPORZIONALE_DF['Servizio'] = pd.Categorical(RETTIFICA_PROPORZIONALE_DF['Servizio'], categories=SERVIZI_ORDER, ordered=True)

# --- SIDEBAR ---
st.sidebar.title("Azioni e Note")
if st.sidebar.button("💾 Salva Tutte le Note", use_container_width=True):
    save_notes_to_gsheet(st.session_state.notes)
st.sidebar.markdown("---")
st.sidebar.title("Cronistoria")
# ... (la cronistoria rimane identica)
st.sidebar.subheader("Anno 2023"); st.sidebar.markdown("- **Fine Ottobre 2023**: Assunzione di Tombolini e Marinelli.\n- **18/10/2023**: Attivazione parcometri annuali.\n- **15/12/2023**: Attivazione ARU per abbonamenti.\n- **20/12/2023**: Licenziamento Marinelli.")
st.sidebar.markdown("---"); st.sidebar.subheader("Anno 2024"); st.sidebar.markdown(f"- **Rettifica Bisestile**: L'opzione sottrae un totale di **{format_europeo(abs(IMPORTO_RETTIFICA))}** dagli incassi di Febbraio 2024."); st.sidebar.markdown("- **01/01/2024**: Assunzione Lancelotti.\n- **01/04/2024**: Attivazione ParkingHUB (MooneyGo).\n- **01/04/2024**: Inizio sanzionamento.\n- **01/04/2024**: **Rettifica Manuale**: Aggiunti € 3.130,50/mese per Gen-Mar a 'Hub Sosta (App)'.\n- **03/04/2024**: Attivazione parcometri estivi.\n- **27/04/2024**: Attivazione POS su parcometri.\n- **21/05/2024**: Attivazione EasyPark.\n- **01/06/2024**: Stop autorizzazioni da PL.")
st.sidebar.markdown("---"); st.sidebar.subheader("Anno 2025"); st.sidebar.markdown("- **07/04/2025**: Licenziamento Lancelotti.\n- **09/05/2025**: Assunzione Viti.")


tab_confronto, tab_anno1, tab_anno2 = st.tabs([f"📊 Confronto {ANNO_1} vs {ANNO_2}", f"🗓️ Dettaglio {ANNO_1}", f"🗓️ Dettaglio {ANNO_2}"])

with tab_confronto:
    # Il resto del codice della tab confronto rimane IDENTICO
    # Utilizza le stesse funzioni che ora leggono e scrivono da/su session_state
    # La logica di visualizzazione non deve cambiare.
    st.header(f"Andamento Temporale e Confronto {ANNO_1} vs {ANNO_2} (dal 01 gennaio al 30 giugno)")
    def colora_confronto_variazione(val):
        if pd.isna(val) or val == 0: return 'color: grey'
        return 'color: green' if val > 0 else 'color: red'

    # --- FUNZIONE GENERALE PER TABELLE CON NOTE ---
    def create_comparison_table_with_notes(df_data, value_col, title, table_key, is_currency=True):
        st.markdown(f"**{title}**")
        
        pivot = df_data.pivot_table(values=value_col, index='Servizio', columns='Anno', aggfunc='sum', observed=False).fillna(0).reindex(columns=[ANNO_1, ANNO_2], fill_value=0)
        pivot['Variazione Assoluta'] = pivot[ANNO_2] - pivot[ANNO_1]
        pivot['Variazione %'] = (pivot['Variazione Assoluta'] / pivot[ANNO_1].replace(0, pd.NA)) * 100
        totali = pivot.sum()
        totali['Variazione %'] = (totali['Variazione Assoluta'] / totali[ANNO_1]) * 100 if totali[ANNO_1] != 0 else 0
        totali.name = 'TOTALE'
        pivot_con_totale = pd.concat([pivot, totali.to_frame().T])
        pivot_con_totale.columns = [str(c) for c in pivot_con_totale.columns]
        
        st.session_state.notes.setdefault(table_key, {})
        pivot_con_totale['Note'] = pivot_con_totale.index.map(lambda x: st.session_state.notes[table_key].get(str(x), "")).fillna("")
        
        formatters = {str(ANNO_1): lambda x: format_europeo(x, 'valuta' if is_currency else 'numero'), str(ANNO_2): lambda x: format_europeo(x, 'valuta' if is_currency else 'numero'), 'Variazione Assoluta': lambda x: f"{'+' if x >= 0 else ''}{format_europeo(x, 'valuta' if is_currency else 'numero')}", 'Variazione %': '{:+.2f}%', 'Note': '{}'}
        
        styler = pivot_con_totale.style.format(formatters)\
            .map(colora_confronto_variazione, subset=['Variazione %'])\
            .apply(lambda row: ['font-weight: bold; background-color: #D9E1F2'] * len(row) if row.name == 'TOTALE' else [''] * len(row), axis=1)\
            .set_properties(subset=['Note'], **{'white-space': 'pre-wrap', 'text-align': 'left', 'min-width': '250px'})\
            .set_table_styles([dict(selector="th", props=[("text-align", "center")]), dict(selector="td", props=[('text-align', 'center')])])

        st.markdown(styler.to_html(escape=False), unsafe_allow_html=True)

        with st.expander(f"Modifica note per la tabella '{title}'"):
            for idx in pivot_con_totale.index:
                st.session_state.notes[table_key][str(idx)] = st.text_area(f"Nota per **{idx}**:", value=st.session_state.notes[table_key].get(str(idx), ""), key=f"{table_key}_{idx}")

    # --- Sezione Tabelle Incassi e Titoli ---
    st.subheader("Confronto Aggregato per Servizio")
    adjust_servizi = st.checkbox(f"✅ Applica rettifica anno bisestile ({format_europeo(IMPORTO_RETTIFICA)})", key="leap_servizi")
    dati_servizi = full_data.copy()
    if adjust_servizi and not RETTIFICA_PROPORZIONALE_DF.empty:
        dati_servizi = pd.concat([dati_servizi, RETTIFICA_PROPORZIONALE_DF], ignore_index=True)
    
    create_comparison_table_with_notes(dati_servizi, 'Importo Totale', "Incassi", "notes_incassi", is_currency=True)
    create_comparison_table_with_notes(dati_servizi, 'Numero Titoli', "Numero Titoli", "notes_titoli", is_currency=False)
    
    # --- Sezione Tabella Redditività ---
    st.markdown("---")
    st.subheader("Confronto Redditività Media per Servizio (€/Titolo)")
    adjust_redditivita = st.checkbox(f"✅ Applica rettifica anno bisestile ({format_europeo(IMPORTO_RETTIFICA)})", key="leap_redditivita")
    dati_redditivita_calc = full_data.copy()
    if adjust_redditivita and not RETTIFICA_PROPORZIONALE_DF.empty:
        dati_redditivita_calc = pd.concat([dati_redditivita_calc, RETTIFICA_PROPORZIONALE_DF], ignore_index=True)
    
    pivot_importi = dati_redditivita_calc.pivot_table(values='Importo Totale', index='Servizio', columns='Anno', aggfunc='sum', observed=False).fillna(0)
    pivot_titoli = dati_redditivita_calc.pivot_table(values='Numero Titoli', index='Servizio', columns='Anno', aggfunc='sum', observed=False).fillna(0)
    redditivita = (pivot_importi / pivot_titoli.replace(0, pd.NA)).reindex(columns=[ANNO_1, ANNO_2]).fillna(0)
    redditivita['Variazione Assoluta'] = redditivita[ANNO_2] - redditivita[ANNO_1]
    redditivita['Variazione %'] = (redditivita['Variazione Assoluta'] / redditivita[ANNO_1].replace(0, pd.NA)) * 100
    tot_imp_1, tot_tit_1 = pivot_importi.get(ANNO_1, pd.Series(0)).sum(), pivot_titoli.get(ANNO_1, pd.Series(0)).sum()
    tot_imp_2, tot_tit_2 = pivot_importi.get(ANNO_2, pd.Series(0)).sum(), pivot_titoli.get(ANNO_2, pd.Series(0)).sum()
    redd_tot_1, redd_tot_2 = (tot_imp_1 / tot_tit_1 if tot_tit_1 > 0 else 0), (tot_imp_2 / tot_tit_2 if tot_tit_2 > 0 else 0)
    riga_totale_redd = pd.DataFrame({'Variazione Assoluta': [redd_tot_2 - redd_tot_1], 'Variazione %': [(redd_tot_2 - redd_tot_1) / redd_tot_1 * 100 if redd_tot_1 > 0 else 0]}, index=['TOTALE'])
    riga_totale_redd[ANNO_1], riga_totale_redd[ANNO_2] = redd_tot_1, redd_tot_2
    redditivita_con_totale = pd.concat([redditivita, riga_totale_redd])
    redditivita_con_totale.columns = [str(c) for c in redditivita_con_totale.columns]
    
    table_key_redd = "notes_redditivita"
    st.session_state.notes.setdefault(table_key_redd, {})
    redditivita_con_totale['Note'] = redditivita_con_totale.index.map(lambda x: st.session_state.notes[table_key_redd].get(str(x), "")).fillna("")
    formatters_redd = {str(ANNO_1): lambda x: format_europeo(x), str(ANNO_2): lambda x: format_europeo(x), 'Variazione Assoluta': lambda x: f"{'+' if x >= 0 else ''}{format_europeo(x)}", 'Variazione %': '{:+.2f}%', 'Note': '{}'}

    styler_redd = redditivita_con_totale.style.format(formatters_redd)\
        .map(colora_confronto_variazione, subset=['Variazione %'])\
        .apply(lambda row: ['font-weight: bold; background-color: #D9E1F2'] * len(row) if row.name == 'TOTALE' else [''] * len(row), axis=1)\
        .set_properties(subset=['Note'], **{'white-space': 'pre-wrap', 'text-align': 'left', 'min-width': '250px'})\
        .set_table_styles([dict(selector="th", props=[("text-align", "center")]), dict(selector="td", props=[('text-align', 'center')])])

    st.markdown(styler_redd.to_html(escape=False), unsafe_allow_html=True)

    with st.expander("Modifica note per la tabella 'Redditività Media'"):
        for idx in redditivita_con_totale.index:
            st.session_state.notes[table_key_redd][str(idx)] = st.text_area(f"Nota per **{idx}**:", value=st.session_state.notes[table_key_redd].get(str(idx), ""), key=f"{table_key_redd}_{idx}")

    # --- Sezione Analisi Mensile ---
    st.markdown("---")
    st.header("Analisi Dettagliata per Linea di Prodotto (Base Mensile)")
    adjust_mensile = st.checkbox(f"✅ Applica rettifica anno bisestile ({format_europeo(IMPORTO_RETTIFICA)})", key="leap_mensile")
    dati_mensili = full_data.copy()
    if adjust_mensile and not RETTIFICA_PROPORZIONALE_DF.empty:
        dati_mensili = pd.concat([dati_mensili, RETTIFICA_PROPORZIONALE_DF], ignore_index=True)
        
    col_metric, col_menu = st.columns([1, 1]);
    with col_metric: metric_selezionata = st.radio("Scegli la metrica:", ('Incasso Totale', 'Numero Titoli'), key="radio_metric")
    with col_menu: servizio_selezionato = st.selectbox("Seleziona una vista:", options=['Tutti i Servizi', 'Sosta Occasionale (Aggregato)'] + SERVIZI_ORDER, key="filtro_servizio")
    
    value_col, y_label, is_curr = ('Importo Totale', 'Incasso Totale (€)', True) if metric_selezionata == 'Incasso Totale' else ('Numero Titoli', 'Numero Titoli', False)
    
    if servizio_selezionato == 'Tutti i Servizi': dati_filtrati = dati_mensili.copy()
    elif servizio_selezionato == 'Sosta Occasionale (Aggregato)': dati_filtrati = dati_mensili[dati_mensili['Servizio'].isin(['Parcometri', 'Hub Sosta (App)', 'Tap&Park (ricariche)'])].copy()
    else: dati_filtrati = dati_mensili[dati_mensili['Servizio'] == servizio_selezionato].copy()
        
    pivot_confronto = dati_filtrati.pivot_table(values=value_col, index='Mese', columns='Anno', aggfunc='sum', observed=False).fillna(0).reindex(columns=[ANNO_1, ANNO_2], fill_value=0)
    nomi_mesi = {m: pd.Timestamp(2000, m, 1).strftime('%B') for m in range(1, 13)};
    pivot_confronto = pivot_confronto.loc[pivot_confronto.index.isin(nomi_mesi.keys())].copy();
    pivot_confronto.index = pivot_confronto.index.map(nomi_mesi)
    pivot_confronto['Variazione Assoluta'] = pivot_confronto[ANNO_2] - pivot_confronto[ANNO_1]
    pivot_confronto['Variazione %'] = (pivot_confronto['Variazione Assoluta'] / pivot_confronto[ANNO_1].replace(0, pd.NA)) * 100
    totali = pivot_confronto.sum();
    totali['Variazione %'] = (totali['Variazione Assoluta'] / totali[ANNO_1]) * 100 if totali[ANNO_1] != 0 else 0
    totali.name = 'TOTALE'
    pivot_confronto_con_totale = pd.concat([pivot_confronto, totali.to_frame().T]);
    pivot_confronto_con_totale.columns = [str(c) for c in pivot_confronto_con_totale.columns]
    
    table_key_mensile = f"notes_mensile_{servizio_selezionato.replace(' ', '_')}_{metric_selezionata.replace(' ', '_')}"
    st.session_state.notes.setdefault(table_key_mensile, {})
    pivot_confronto_con_totale['Note'] = pivot_confronto_con_totale.index.map(lambda x: st.session_state.notes[table_key_mensile].get(str(x), "")).fillna("")

    formatters_mensile = { str(ANNO_1): lambda x: format_europeo(x, 'valuta' if is_curr else 'numero'), str(ANNO_2): lambda x: format_europeo(x, 'valuta' if is_curr else 'numero'), 'Variazione Assoluta': lambda x: f"{'+' if x >= 0 else ''}{format_europeo(x, 'valuta' if is_curr else 'numero')}", 'Variazione %': '{:+.2f}%', 'Note': '{}'}
    
    styler_mensile = pivot_confronto_con_totale.style.format(formatters_mensile)\
        .map(colora_confronto_variazione, subset=['Variazione %'])\
        .apply(lambda row: ['font-weight: bold; background-color: #D9E1F2'] * len(row) if row.name == 'TOTALE' else [''] * len(row), axis=1)\
        .set_properties(subset=['Note'], **{'white-space': 'pre-wrap', 'text-align': 'left', 'min-width': '250px'})\
        .set_table_styles([dict(selector="th", props=[("text-align", "center")]), dict(selector="td", props=[('text-align', 'center')])])

    st.markdown(styler_mensile.to_html(escape=False), unsafe_allow_html=True)

    with st.expander("Modifica note per la tabella 'Analisi Mensile'"):
        for idx in pivot_confronto_con_totale.index:
            st.session_state.notes[table_key_mensile][str(idx)] = st.text_area(f"Nota per **{idx}**:", value=st.session_state.notes[table_key_mensile].get(str(idx), ""), key=f"{table_key_mensile}_{idx}")

    df_plot_line = pivot_confronto[[ANNO_1, ANNO_2]].copy()
    df_plot_line.columns = [str(c) for c in df_plot_line.columns]
    fig_line = px.line(df_plot_line, title=f"Confronto Mensile {metric_selezionata} per: {servizio_selezionato}", markers=True, labels={"value": y_label, "index": "Mese", "variable": "Anno"})
    fig_line.update_layout(yaxis_title=y_label, xaxis_title="Mese")
    st.plotly_chart(fig_line, use_container_width=True)


with tab_anno1:
    display_analysis_for_year(full_data, ANNO_1)
with tab_anno2:
    display_analysis_for_year(full_data, ANNO_2)
