import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAZIONE PAGINA STREAMLIT ---
st.set_page_config(
    page_title="Dashboard Incassi Parcheggi",
    page_icon="🚗",
    layout="wide"
)

# Definizione dell'ordine standard dei servizi
SERVIZI_ORDER = ["Autorizzazioni", "Abbonamenti", "Parcometri", "Hub Sosta (App)", "Tap&Park"]

# --- 1. FUNZIONE DI CARICAMENTO E PROCESSING DATI ---
@st.cache_data
def load_and_process_data(excel_path):
    if not os.path.exists(excel_path):
        st.error(f"File di dati non trovato: '{excel_path}'.")
        return None
    try:
        xls = pd.ExcelFile(excel_path)
    except Exception as e:
        st.error(f"Impossibile leggere il file Excel: {e}")
        return None
    
    SERVIZI_MAP = {"AUTORIZZAZIONI 1SEM": "Autorizzazioni", "ABBONAMENTI 1SEM": "Abbonamenti", "HUB_SOSTA 1SEM": "Hub Sosta (App)", "PARCOMETRI 1SEM": "Parcometri", "TAP&PARK 1SEM": "Tap&Park"}
    lista_df = []
    for sheet_name in xls.sheet_names:
        try:
            df = xls.parse(sheet_name)
            df.columns = [col.strip() for col in df.columns]
            parts = sheet_name.split('_')
            anno_str = parts[0]
            servizio_key_str = sheet_name.replace(f"{anno_str}_", "", 1)
            anno = int(anno_str)
            servizio_nome = SERVIZI_MAP.get(servizio_key_str, "Sconosciuto")
            if servizio_nome == "Sconosciuto": continue
            df['DATA_ORA_INSERIMENTO'] = pd.to_datetime(df['DATA_ORA_INSERIMENTO'])
            if 'Hub Sosta' in servizio_nome:
                df['EasyPark'] = pd.to_numeric(df['EasyPark'], errors='coerce').fillna(0)
                df['MyCicero'] = pd.to_numeric(df['MyCicero'], errors='coerce').fillna(0)
                df['Importo Totale'] = df['EasyPark'] + df['MyCicero']
            else:
                importo_col_name = next((col for col in df.columns if 'Importo' in col), None)
                if importo_col_name:
                    df['Importo Totale'] = pd.to_numeric(df[importo_col_name], errors='coerce').fillna(0)
                else:
                    df['Importo Totale'] = pd.to_numeric(df.iloc[:, 2], errors='coerce').fillna(0)
            df['Anno'] = anno
            df['Mese'] = df['DATA_ORA_INSERIMENTO'].dt.month
            df['Servizio'] = servizio_nome
            lista_df.append(df[['Anno', 'Mese', 'Servizio', 'Importo Totale', 'DATA_ORA_INSERIMENTO']])
        except Exception as e:
            st.error(f"Errore durante l'elaborazione del foglio '{sheet_name}': {e}")
    if not lista_df: return None
    dati_completi = pd.concat(lista_df, ignore_index=True)
    rettifiche = [
        {'Anno': 2024, 'Mese': 1, 'Servizio': 'Hub Sosta (App)', 'Importo Totale': 3130.5, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-01-31')},
        {'Anno': 2024, 'Mese': 2, 'Servizio': 'Hub Sosta (App)', 'Importo Totale': 3130.5, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-02-29')},
        {'Anno': 2024, 'Mese': 3, 'Servizio': 'Hub Sosta (App)', 'Importo Totale': 3130.5, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-03-31')}
    ]
    df_rettifiche = pd.DataFrame(rettifiche)
    dati_finali = pd.concat([dati_completi, df_rettifiche], ignore_index=True)
    dati_finali['Servizio'] = pd.Categorical(dati_finali['Servizio'], categories=SERVIZI_ORDER, ordered=True)
    return dati_finali

# --- 2. FUNZIONE PER VISUALIZZARE L'ANALISI DI UN ANNO ---
def display_analysis_for_year(df, year):
    df_anno = df[df['Anno'] == year].copy()
    if df_anno.empty:
        st.warning(f"Nessun dato disponibile per l'anno {year}.")
        return
    data_inizio = df_anno['DATA_ORA_INSERIMENTO'].min()
    data_fine = df_anno['DATA_ORA_INSERIMENTO'].max()
    mesi_italiani = {1: 'gennaio', 2: 'febbraio', 3: 'marzo', 4: 'aprile', 5: 'maggio', 6: 'giugno'}
    data_inizio_str = f"{data_inizio.day:02d} {mesi_italiani.get(data_inizio.month, '')}"
    data_fine_str = f"{data_fine.day:02d} {mesi_italiani.get(data_fine.month, '')}"
    st.header(f"Riepilogo Incassi Anno {year} (dal {data_inizio_str} al {data_fine_str})")
    incasso_totale = df_anno['Importo Totale'].sum()
    transazioni_totali = len(df_anno)
    col1, col2 = st.columns(2)
    col1.metric("Incasso Totale Annuo", f"€ {incasso_totale:,.2f}")
    col2.metric("Numero Transazioni", f"{transazioni_totali:,}")
    
    incassi_per_servizio = df_anno.groupby('Servizio', observed=False)['Importo Totale'].sum().reset_index()

    st.subheader("Dettaglio Incassi per Tipologia di Servizio")
    incassi_per_servizio['Percentuale'] = (incassi_per_servizio['Importo Totale'] / incasso_totale * 100) if incasso_totale > 0 else 0
    riga_totale = pd.DataFrame({'Servizio': ['TOTALE'], 'Importo Totale': [incasso_totale], 'Percentuale': [100.0]})
    tabella_visualizzata = pd.concat([incassi_per_servizio, riga_totale], ignore_index=True)
    st.dataframe(tabella_visualizzata.style.format({'Importo Totale': '€ {:,.2f}', 'Percentuale': '{:.2f}%'}).apply(lambda x: ['background-color: #D9E1F2; font-weight: bold'] * len(x) if x.name == len(tabella_visualizzata) - 1 else [''] * len(x), axis=1), use_container_width=True, hide_index=True)
    
    col1_graf, col2_graf = st.columns(2)
    with col1_graf:
        st.subheader("Composizione Incassi")
        fig_pie = px.pie(incassi_per_servizio, names='Servizio', values='Importo Totale', title=f'Distribuzione Incassi {year}', hole=0.3)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label', sort=False)
        st.plotly_chart(fig_pie, use_container_width=True, key=f"pie_chart_{year}")
    with col2_graf:
        st.subheader("Confronto Servizi")
        fig_bar = px.bar(incassi_per_servizio, x='Servizio', y='Importo Totale', title=f'Incassi per Servizio {year}', text_auto='.2s', custom_data=['Percentuale'])
        fig_bar.update_traces(textangle=0, textposition="outside", hovertemplate='<b>%{x}</b><br>Incasso: €%{y:,.2f}<br>Percentuale sul totale: %{customdata[0]:.2f}%<extra></extra>')
        st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_chart_{year}")
    
    st.subheader("Andamento Temporale Mensile per Servizio")
    andamento_mensile_dettaglio = df_anno.pivot_table(values='Importo Totale', index='Mese', columns='Servizio', aggfunc='sum', observed=False).fillna(0)
    andamento_mensile_dettaglio['Totale'] = andamento_mensile_dettaglio.sum(axis=1)
    df_plot = andamento_mensile_dettaglio.reset_index().melt(id_vars='Mese', var_name='Servizio', value_name='Importo')
    df_plot = pd.merge(df_plot, andamento_mensile_dettaglio[['Totale']], on='Mese', how='left')
    df_plot['Percentuale sul mese'] = (df_plot['Importo'] / df_plot['Totale'].replace(0, pd.NA) * 100).fillna(0)
    nomi_mesi_map = {1: 'Gen', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mag', 6: 'Giu'}
    df_plot['MeseStr'] = df_plot['Mese'].map(nomi_mesi_map)
    fig_line_dettaglio = px.line(df_plot, x='MeseStr', y='Importo', color='Servizio', title=f'Andamento Incassi Mensili per Servizio - {year}', markers=True, custom_data=['Percentuale sul mese'], labels={"Importo": "Incasso (€)", "MeseStr": "Mese", "Servizio": "Servizio"})
    fig_line_dettaglio.update_layout(yaxis_title="Incasso Totale (€)", xaxis_title="Mese")
    fig_line_dettaglio.update_traces(hovertemplate='Incasso: €%{y:,.2f}<br>Percentuale sul mese: %{customdata[0]:.2f}%<extra></extra>')
    st.plotly_chart(fig_line_dettaglio, use_container_width=True, key=f"line_dettaglio_{year}")
    st.info("💡 Clicca sugli elementi nella legenda del grafico per nascondere o mostrare le linee.")

# --- 3. CORPO PRINCIPALE DELL'APPLICAZIONE ---
st.title("🚗 Dashboard Analisi Incassi Parcheggi")
st.markdown("Applicazione per il confronto degli incassi su base annuale e mensile.")

ANNO_1, ANNO_2 = 2024, 2025
IMPORTO_RETTIFICA = -1350.84

script_dir = os.path.dirname(os.path.abspath(__file__))
excel_file_path = os.path.join(script_dir, "data", "Dati_Incassi_Completo.xlsx")
full_data = load_and_process_data(excel_file_path)

RETTIFICA_PROPORZIONALE_DF = pd.DataFrame()
if full_data is not None:
    df_feb_2024 = full_data[(full_data['Anno'] == 2024) & (full_data['Mese'] == 2)]
    incassi_feb_2024 = df_feb_2024.groupby('Servizio', observed=False)['Importo Totale'].sum()
    totale_incasso_feb_2024 = incassi_feb_2024.sum()
    if totale_incasso_feb_2024 > 0:
        proporzioni = incassi_feb_2024 / totale_incasso_feb_2024
        lista_rettifiche = []
        for servizio, proporzione in proporzioni.items():
            importo_da_sottrarre = IMPORTO_RETTIFICA * proporzione
            lista_rettifiche.append({'Anno': 2024, 'Mese': 2, 'Servizio': servizio, 'Importo Totale': importo_da_sottrarre, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-02-29')})
        RETTIFICA_PROPORZIONALE_DF = pd.DataFrame(lista_rettifiche)
        RETTIFICA_PROPORZIONALE_DF['Servizio'] = pd.Categorical(RETTIFICA_PROPORZIONALE_DF['Servizio'], categories=SERVIZI_ORDER, ordered=True)

if full_data is None:
    st.stop()

### MODIFICA: Ripristino di tutte le note nella sidebar ###
st.sidebar.title("Note e Cronistoria")
st.sidebar.markdown("---")
st.sidebar.subheader("Anno 2023")
st.sidebar.markdown("""
- **Fine Ottobre 2023**: Assunzione di Tombolini e Marinelli.
- **18/10/2023**: Attivazione parcometri annuali.
- **15/12/2023**: Attivazione ARU per abbonamenti.
- **20/12/2023**: Licenziamento Marinelli.
""")
st.sidebar.markdown("---")
st.sidebar.subheader("Anno 2024")
st.sidebar.markdown(f"- **Rettifica Bisestile**: L'opzione sottrae un totale di **€{abs(IMPORTO_RETTIFICA):,.2f}** dagli incassi di Febbraio 2024, distribuendoli proporzionalmente sui servizi attivi in quel mese.")
st.sidebar.markdown("""
- **01/01/2024**: Assunzione Lancelotti.
- **01/04/2024**: Attivazione ParkingHUB (MooneyGo).
- **01/04/2024**: Inizio sanzionamento, oltre che controllo.
- **01/04/2024**: **Rettifica Manuale Dati**: Aggiunti € 3.130,50/mese per Gen-Mar a 'Hub Sosta (App)'.
- **03/04/2024**: Attivazione parcometri estivi.
- **27/04/2024**: Attivazione POS su parcometri.
- **21/05/2024**: Attivazione EasyPark.
- **01/06/2024**: Il comando di PL ha smesso di rilasciare le autorizzazioni.
""")
st.sidebar.markdown("---")
st.sidebar.subheader("Anno 2025")
st.sidebar.markdown("""
- **07/04/2025**: Licenziamento Lancelotti.
- **09/05/2025**: Assunzione Viti, al momento solo sportello e controlli.
""")

# --- Definizione Tab ---
tab_confronto, tab_anno1, tab_anno2 = st.tabs([f"📊 Confronto {ANNO_1} vs {ANNO_2}", f"🗓️ Dettaglio {ANNO_1}", f"🗓️ Dettaglio {ANNO_2}"])

with tab_confronto:
    ### MODIFICA: Aggiornamento del titolo ###
    st.header(f"Andamento Temporale e Confronto {ANNO_1} vs {ANNO_2} (dal 01 gennaio al 30 giugno)")

    def colora_confronto(row, year1_str, year2_str):
        styles = [''] * len(row)
        if row.name == 'TOTALE' or year1_str not in row or year2_str not in row: return styles
        val1, val2 = row[year1_str], row[year2_str]
        idx1, idx2 = row.index.get_loc(year1_str), row.index.get_loc(year2_str)
        colore_verde, colore_rosso = 'background-color: #D4EDDA', 'background-color: #F8D7DA'
        if val2 > val1: styles[idx2], styles[idx1] = colore_verde, colore_rosso
        elif val1 > val2: styles[idx1], styles[idx2] = colore_verde, colore_rosso
        return styles
    
    def format_variazione_pp(val):
        if val > 0: return f"↑ {val:+.2f} p.p."
        elif val < 0: return f"↓ {val:+.2f} p.p."
        else: return f"{val:.2f} p.p."

    def color_variazione_pp(val):
        if val > 0: color = 'green'
        elif val < 0: color = 'red'
        else: color = 'grey'
        return f'color: {color}'

    st.markdown("---")
    st.subheader("Tabella di Confronto per Tipologia di Servizio (Dettagliato)")
    adjust_servizi = st.checkbox(f"✅ Applica rettifica anno bisestile ({IMPORTO_RETTIFICA:,.2f}€)", key="leap_servizi")
    dati_servizi = full_data.copy()
    if adjust_servizi and not RETTIFICA_PROPORZIONALE_DF.empty:
        dati_servizi = pd.concat([dati_servizi, RETTIFICA_PROPORZIONALE_DF], ignore_index=True)
    pivot_servizi = dati_servizi.pivot_table(values='Importo Totale', index='Servizio', columns='Anno', aggfunc='sum', observed=False).fillna(0)
    pivot_servizi = pivot_servizi.reindex(columns=[ANNO_1, ANNO_2], fill_value=0)
    pivot_servizi['Variazione Assoluta'] = pivot_servizi[ANNO_2] - pivot_servizi[ANNO_1]
    pivot_servizi['Variazione %'] = (pivot_servizi['Variazione Assoluta'] / pivot_servizi[ANNO_1].replace(0, pd.NA)) * 100
    totali_servizi = pivot_servizi[[ANNO_1, ANNO_2, 'Variazione Assoluta']].sum()
    totali_servizi['Variazione %'] = (totali_servizi['Variazione Assoluta'] / totali_servizi[ANNO_1]) * 100 if totali_servizi[ANNO_1] != 0 else 0
    totali_servizi.name = 'TOTALE'
    pivot_servizi_con_totale = pd.concat([pivot_servizi, totali_servizi.to_frame().T])
    pivot_servizi_con_totale.columns = pivot_servizi_con_totale.columns.astype(str)
    st.dataframe(pivot_servizi_con_totale.style.format({str(ANNO_1): '€ {:,.2f}', str(ANNO_2): '€ {:,.2f}', 'Variazione Assoluta': '€ {:+,.2f}', 'Variazione %': '{:+.2f}%'}).apply(colora_confronto, year1_str=str(ANNO_1), year2_str=str(ANNO_2), axis=1).apply(lambda row: ['font-weight: bold; background-color: #D9E1F2'] * len(row) if row.name == 'TOTALE' else [''] * len(row), axis=1), use_container_width=True)
    st.markdown("---")

    st.subheader("Confronto Composizione Incassi (%)")
    adjust_composizione = st.checkbox(f"✅ Applica rettifica anno bisestile ({IMPORTO_RETTIFICA:,.2f}€)", key="leap_composizione")
    dati_composizione = full_data.copy()
    if adjust_composizione and not RETTIFICA_PROPORZIONALE_DF.empty:
        dati_composizione = pd.concat([dati_composizione, RETTIFICA_PROPORZIONALE_DF], ignore_index=True)
    pivot_comp = dati_composizione.pivot_table(values='Importo Totale', index='Servizio', columns='Anno', aggfunc='sum', observed=False).fillna(0)
    total_24 = pivot_comp[2024].sum()
    total_25 = pivot_comp[2025].sum()
    comp_df = pd.DataFrame(index=SERVIZI_ORDER)
    comp_df[f'Composizione % {ANNO_1}'] = (pivot_comp[ANNO_1] / total_24 * 100) if total_24 > 0 else 0
    comp_df[f'Composizione % {ANNO_2}'] = (pivot_comp[ANNO_2] / total_25 * 100) if total_25 > 0 else 0
    comp_df['Variazione (p.p.)'] = comp_df[f'Composizione % {ANNO_2}'] - comp_df[f'Composizione % {ANNO_1}']
    
    st.dataframe(comp_df.style
        .apply(lambda x: x.map(color_variazione_pp), subset=['Variazione (p.p.)'])
        .format({
            f'Composizione % {ANNO_1}': '{:.2f}%',
            f'Composizione % {ANNO_2}': '{:.2f}%',
            'Variazione (p.p.)': format_variazione_pp
        }), 
        use_container_width=True
    )

    col1, col2 = st.columns(2)
    with col1:
        fig_pie_24 = px.pie(pivot_comp.reset_index(), names='Servizio', values=2024, title=f'Distribuzione Incassi {ANNO_1}', hole=0.3)
        fig_pie_24.update_traces(textposition='inside', textinfo='percent+label', sort=False)
        st.plotly_chart(fig_pie_24, use_container_width=True, key="pie_comp_24")
    with col2:
        fig_pie_25 = px.pie(pivot_comp.reset_index(), names='Servizio', values=2025, title=f'Distribuzione Incassi {ANNO_2}', hole=0.3)
        fig_pie_25.update_traces(textposition='inside', textinfo='percent+label', sort=False)
        st.plotly_chart(fig_pie_25, use_container_width=True, key="pie_comp_25")
    st.markdown("---")

    st.subheader("Confronto per Categorie Aggregate")
    adjust_aggregate = st.checkbox(f"✅ Applica rettifica anno bisestile ({IMPORTO_RETTIFICA:,.2f}€)", key="leap_aggregate")
    dati_aggregate = full_data.copy()
    if adjust_aggregate and not RETTIFICA_PROPORZIONALE_DF.empty:
        dati_aggregate = pd.concat([dati_aggregate, RETTIFICA_PROPORZIONALE_DF], ignore_index=True)
    servizio_mapping = {'Parcometri': 'Sosta Occasionale', 'Hub Sosta (App)': 'Sosta Occasionale', 'Tap&Park': 'Sosta Occasionale', 'Autorizzazioni': 'Autorizzazioni', 'Abbonamenti': 'Abbonamenti'}
    dati_aggregate['Categoria'] = dati_aggregate['Servizio'].map(servizio_mapping)
    pivot_aggregato = dati_aggregate.pivot_table(values='Importo Totale', index='Categoria', columns='Anno', aggfunc='sum').fillna(0)
    pivot_aggregato = pivot_aggregato.reindex(columns=[ANNO_1, ANNO_2], fill_value=0)
    pivot_aggregato['Variazione Assoluta'] = pivot_aggregato[ANNO_2] - pivot_aggregato[ANNO_1]
    pivot_aggregato['Variazione %'] = (pivot_aggregato['Variazione Assoluta'] / pivot_aggregato[ANNO_1].replace(0, pd.NA)) * 100
    totali_aggregati = pivot_aggregato[[ANNO_1, ANNO_2, 'Variazione Assoluta']].sum()
    totali_aggregati['Variazione %'] = (totali_aggregati['Variazione Assoluta'] / totali_aggregati[ANNO_1]) * 100 if totali_aggregati[ANNO_1] != 0 else 0
    totali_aggregati.name = 'TOTALE'
    pivot_aggregato_con_totale = pd.concat([pivot_aggregato, totali_aggregati.to_frame().T])
    pivot_aggregato_con_totale.columns = pivot_aggregato_con_totale.columns.astype(str)
    st.dataframe(pivot_aggregato_con_totale.style.format({str(ANNO_1): '€ {:,.2f}', str(ANNO_2): '€ {:,.2f}', 'Variazione Assoluta': '€ {:+,.2f}', 'Variazione %': '{:+.2f}%'}).apply(colora_confronto, year1_str=str(ANNO_1), year2_str=str(ANNO_2), axis=1).apply(lambda row: ['font-weight: bold; background-color: #D9E1F2'] * len(row) if row.name == 'TOTALE' else [''] * len(row), axis=1), use_container_width=True)
    df_plot_aggregato = pivot_aggregato.reset_index().melt(id_vars='Categoria', value_vars=[ANNO_1, ANNO_2], var_name='Anno', value_name='Incasso')
    fig_bar_aggregato = px.bar(df_plot_aggregato, x='Categoria', y='Incasso', color='Anno', barmode='group', text_auto='.2s', title='Confronto Incassi per Categoria Aggregata', labels={'Incasso': 'Incasso Totale (€)', 'Categoria': 'Categoria'})
    st.plotly_chart(fig_bar_aggregato, use_container_width=True, key="bar_chart_aggregato")
    st.markdown("---")

    st.header("Analisi Dettagliata per Linea di Prodotto (Base Mensile)")
    adjust_mensile = st.checkbox(f"✅ Applica rettifica anno bisestile ({IMPORTO_RETTIFICA:,.2f}€)", key="leap_mensile")
    dati_mensili = full_data.copy()
    if adjust_mensile and not RETTIFICA_PROPORZIONALE_DF.empty:
        dati_mensili = pd.concat([dati_mensili, RETTIFICA_PROPORZIONALE_DF], ignore_index=True)
    opzioni_filtro = ['Tutti i Servizi', 'Sosta Occasionale (Aggregato)'] + SERVIZI_ORDER
    col_menu, col_vuota = st.columns([1, 3])
    with col_menu:
        servizio_selezionato = st.selectbox("Seleziona una vista da analizzare:", options=opzioni_filtro, key="filtro_servizio")
    if servizio_selezionato == 'Tutti i Servizi':
        dati_filtrati = dati_mensili.copy()
        titolo_grafico = "Confronto Mensile Incassi (Tutti i Servizi)"
    elif servizio_selezionato == 'Sosta Occasionale (Aggregato)':
        servizi_occasionali = ['Parcometri', 'Hub Sosta (App)', 'Tap&Park']
        dati_filtrati = dati_mensili[dati_mensili['Servizio'].isin(servizi_occasionali)].copy()
        titolo_grafico = "Confronto Mensile Incassi per: Sosta Occasionale"
    else:
        dati_filtrati = dati_mensili[dati_mensili['Servizio'] == servizio_selezionato].copy()
        titolo_grafico = f"Confronto Mensile Incassi per: {servizio_selezionato}"
    pivot_confronto = dati_filtrati.pivot_table(values='Importo Totale', index='Mese', columns='Anno', aggfunc='sum', observed=False).fillna(0)
    pivot_confronto = pivot_confronto.reindex(columns=[ANNO_1, ANNO_2], fill_value=0)
    nomi_mesi = {1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile', 5: 'Maggio', 6: 'Giugno'}
    pivot_confronto = pivot_confronto.loc[pivot_confronto.index.isin(nomi_mesi.keys())]
    pivot_confronto.index = pivot_confronto.index.map(nomi_mesi)
    pivot_confronto['Variazione Assoluta'] = pivot_confronto[ANNO_2] - pivot_confronto[ANNO_1]
    pivot_confronto['Variazione %'] = (pivot_confronto['Variazione Assoluta'] / pivot_confronto[ANNO_1].replace(0, pd.NA)) * 100
    totali = pivot_confronto[[ANNO_1, ANNO_2, 'Variazione Assoluta']].sum()
    totali['Variazione %'] = (totali['Variazione Assoluta'] / totali[ANNO_1]) * 100 if totali[ANNO_1] != 0 else 0
    totali.name = 'TOTALE'
    pivot_confronto_con_totale = pd.concat([pivot_confronto, totali.to_frame().T])
    pivot_confronto_con_totale.columns = pivot_confronto_con_totale.columns.astype(str)
    st.dataframe(pivot_confronto_con_totale.style.format({str(ANNO_1): '€ {:,.2f}', str(ANNO_2): '€ {:,.2f}', 'Variazione Assoluta': '€ {:+,.2f}', 'Variazione %': '{:+.2f}%'}).apply(colora_confronto, year1_str=str(ANNO_1), year2_str=str(ANNO_2), axis=1).apply(lambda row: ['font-weight: bold; background-color: #D9E1F2'] * len(row) if row.name == 'TOTALE' else [''] * len(row), axis=1), use_container_width=True)
    df_plot_line = pivot_confronto[[ANNO_1, ANNO_2]].copy()
    df_plot_line.columns = df_plot_line.columns.astype(str)
    fig_line = px.line(df_plot_line, title=titolo_grafico, markers=True, labels={"value": "Incasso Totale (€)", "index": "Mese", "variable": "Anno"})
    fig_line.update_layout(yaxis_title="Incasso Totale (€)", xaxis_title="Mese")
    st.plotly_chart(fig_line, use_container_width=True, key=f"confronto_mensile_{servizio_selezionato.replace(' ', '_')}")

with tab_anno1:
    display_analysis_for_year(full_data, ANNO_1)
with tab_anno2:
    display_analysis_for_year(full_data, ANNO_2)