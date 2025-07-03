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

# --- 1. FUNZIONE DI CARICAMENTO E PROCESSING DATI ---
@st.cache_data
def load_and_process_data(excel_path):
    if not os.path.exists(excel_path):
        st.error(f"File di dati non trovato: '{excel_path}'. Assicurati che il file si trovi nella sottocartella 'data'.")
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
            if servizio_nome == "Sconosciuto":
                st.warning(f"Nome foglio non riconosciuto: '{sheet_name}'. Verrà saltato.")
                continue
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
    if not lista_df:
        return None
    dati_completi = pd.concat(lista_df, ignore_index=True)
    rettifiche = [
        {'Anno': 2024, 'Mese': 1, 'Servizio': 'Hub Sosta (App)', 'Importo Totale': 3130.5, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-01-31')},
        {'Anno': 2024, 'Mese': 2, 'Servizio': 'Hub Sosta (App)', 'Importo Totale': 3130.5, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-02-29')},
        {'Anno': 2024, 'Mese': 3, 'Servizio': 'Hub Sosta (App)', 'Importo Totale': 3130.5, 'DATA_ORA_INSERIMENTO': pd.to_datetime('2024-03-31')}
    ]
    df_rettifiche = pd.DataFrame(rettifiche)
    dati_finali = pd.concat([dati_completi, df_rettifiche], ignore_index=True)
    return dati_finali

# --- 2. FUNZIONE PER VISUALIZZARE L'ANALISI DI UN ANNO ---
def display_analysis_for_year(df, year):
    df_anno = df[df['Anno'] == year].copy()
    if df_anno.empty:
        st.warning(f"Nessun dato disponibile per l'anno {year}.")
        return
    data_inizio = df_anno['DATA_ORA_INSERIMENTO'].min()
    data_fine = df_anno['DATA_ORA_INSERIMENTO'].max()
    mesi_italiani = {1: 'gennaio', 2: 'febbraio', 3: 'marzo', 4: 'aprile', 5: 'maggio', 6: 'giugno', 7: 'luglio', 8: 'agosto', 9: 'settembre', 10: 'ottobre', 11: 'novembre', 12: 'dicembre'}
    data_inizio_str = f"{data_inizio.day:02d} {mesi_italiani.get(data_inizio.month, '')}"
    data_fine_str = f"{data_fine.day:02d} {mesi_italiani.get(data_fine.month, '')}"
    st.header(f"Riepilogo Incassi Anno {year} (dal {data_inizio_str} al {data_fine_str})")
    incasso_totale = df_anno['Importo Totale'].sum()
    transazioni_totali = len(df_anno)
    col1, col2 = st.columns(2)
    col1.metric("Incasso Totale Annuo", f"€ {incasso_totale:,.2f}")
    col2.metric("Numero Transazioni", f"{transazioni_totali:,}")
    incassi_per_servizio = df_anno.groupby('Servizio')['Importo Totale'].sum().reset_index().sort_values(by='Importo Totale', ascending=False)
    st.subheader("Dettaglio Incassi per Tipologia di Servizio")
    incassi_per_servizio['Percentuale'] = (incassi_per_servizio['Importo Totale'] / incasso_totale * 100) if incasso_totale > 0 else 0
    riga_totale = pd.DataFrame({'Servizio': ['TOTALE'], 'Importo Totale': [incasso_totale], 'Percentuale': [100.0]})
    tabella_visualizzata = pd.concat([incassi_per_servizio, riga_totale], ignore_index=True)
    st.dataframe(tabella_visualizzata.style.format({'Importo Totale': '€ {:,.2f}', 'Percentuale': '{:.2f}%'}).apply(lambda x: ['background-color: #D9E1F2; font-weight: bold'] * len(x) if x.name == len(tabella_visualizzata) - 1 else [''] * len(x), axis=1), use_container_width=True, hide_index=True)
    col1_graf, col2_graf = st.columns(2)
    with col1_graf:
        st.subheader("Composizione Incassi")
        fig_pie = px.pie(incassi_per_servizio, names='Servizio', values='Importo Totale', title=f'Distribuzione Incassi {year}', hole=0.3)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label', hovertemplate='<b>%{label}</b><br>Incasso: €%{value:,.2f}<br>Percentuale: %{percent}<extra></extra>')
        st.plotly_chart(fig_pie, use_container_width=True, key=f"pie_chart_{year}") # AGGIUNTA KEY
    with col2_graf:
        st.subheader("Confronto Servizi")
        fig_bar = px.bar(incassi_per_servizio, x='Servizio', y='Importo Totale', title=f'Incassi per Servizio {year}', text_auto='.2s', custom_data=['Percentuale'])
        fig_bar.update_traces(textangle=0, textposition="outside", hovertemplate='<b>%{x}</b><br>Incasso: €%{y:,.2f}<br>Percentuale sul totale: %{customdata[0]:.2f}%<extra></extra>')
        st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_chart_{year}") # AGGIUNTA KEY
    st.subheader("Andamento Temporale Mensile per Servizio")
    andamento_mensile_dettaglio = df_anno.pivot_table(values='Importo Totale', index='Mese', columns='Servizio', aggfunc='sum').fillna(0)
    andamento_mensile_dettaglio['Totale'] = andamento_mensile_dettaglio.sum(axis=1)
    df_plot = andamento_mensile_dettaglio.reset_index().melt(id_vars='Mese', var_name='Servizio', value_name='Importo')
    df_plot = pd.merge(df_plot, andamento_mensile_dettaglio[['Totale']], on='Mese', how='left')
    df_plot['Percentuale sul mese'] = (df_plot['Importo'] / df_plot['Totale'].replace(0, pd.NA) * 100).fillna(0)
    nomi_mesi_map = {1: 'Gen', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mag', 6: 'Giu'}
    df_plot['MeseStr'] = df_plot['Mese'].map(nomi_mesi_map)
    fig_line_dettaglio = px.line(df_plot, x='MeseStr', y='Importo', color='Servizio', title=f'Andamento Incassi Mensili per Servizio - {year}', markers=True, custom_data=['Percentuale sul mese'], labels={"Importo": "Incasso (€)", "MeseStr": "Mese", "Servizio": "Servizio"})
    fig_line_dettaglio.update_layout(yaxis_title="Incasso Totale (€)", xaxis_title="Mese")
    fig_line_dettaglio.update_traces(hovertemplate='Incasso: €%{y:,.2f}<br>Percentuale sul mese: %{customdata[0]:.2f}%<extra></extra>')
    st.plotly_chart(fig_line_dettaglio, use_container_width=True, key=f"line_dettaglio_{year}") # AGGIUNTA KEY
    st.info("💡 Clicca sugli elementi nella legenda del grafico per nascondere o mostrare le linee.")

# --- 3. CORPO PRINCIPALE DELL'APPLICAZIONE ---
st.title("🚗 Dashboard Analisi Incassi Parcheggi")
st.markdown("Applicazione per il confronto degli incassi su base annuale e mensile.")

script_dir = os.path.dirname(os.path.abspath(__file__))
excel_file_path = os.path.join(script_dir, "data", "Dati_Incassi_Completo.xlsx")
full_data = load_and_process_data(excel_file_path)

if full_data is None:
    st.stop()

st.sidebar.title("Note e Cronistoria")
st.sidebar.markdown("---")
st.sidebar.subheader("Anno 2023")
st.sidebar.markdown("- **Fine Ottobre 2023**: Assunzione di Tombolini e Marinelli.\n- **18/10/2023**: Attivazione parcometri annuali.\n- **15/12/2023**: Attivazione ARU per abbonamenti.\n- **20/12/2023**: Licenziamento Marinelli.")
st.sidebar.markdown("---")
st.sidebar.subheader("Anno 2024")
st.sidebar.markdown("- **01/01/2024**: Assunzione Lancelotti.\n- **01/04/2024**: Attivazione ParkingHUB (MooneyGo).\n- **01/04/2024**: Inizio sanzionamento, oltre che controllo.\n- **01/04/2024**: **Rettifica Manuale Dati**: Aggiunti € 3.130,50/mese per Gen-Mar a 'Hub Sosta (App)'.\n- **03/04/2024**: Attivazione parcometri estivi.\n- **27/04/2024**: Attivazione POS su parcometri.\n- **21/05/2024**: Attivazione EasyPark.\n- **01/06/2024**: Il comando di PL ha smesso di rilasciare le autorizzazioni.")
st.sidebar.markdown("---")
st.sidebar.subheader("Anno 2025")
st.sidebar.markdown("- **07/04/2025**: Licenziamento Lancelotti.\n- **09/05/2025**: Assunzione Viti, al momento solo sportello e controlli.")

ANNO_1, ANNO_2 = 2024, 2025
tab_confronto, tab_anno1, tab_anno2 = st.tabs([f"📊 Confronto {ANNO_1} vs {ANNO_2}", f"🗓️ Dettaglio {ANNO_1}", f"🗓️ Dettaglio {ANNO_2}"])

# --- CONTENUTO DEL PRIMO TAB ---
with tab_confronto:
    st.header(f"Andamento Temporale e Confronto {ANNO_1} vs {ANNO_2}")

    # Funzione di stile per colorare le celle
    def colora_confronto(row, year1_str, year2_str):
        styles = [''] * len(row)
        if row.name == 'TOTALE' or year1_str not in row or year2_str not in row:
            return styles
        val1 = row[year1_str]
        val2 = row[year2_str]
        idx1 = row.index.get_loc(year1_str)
        idx2 = row.index.get_loc(year2_str)
        colore_verde = 'background-color: #D4EDDA'
        colore_rosso = 'background-color: #F8D7DA'
        if val2 > val1:
            styles[idx2] = colore_verde
            styles[idx1] = colore_rosso
        elif val1 > val2:
            styles[idx1] = colore_verde
            styles[idx2] = colore_rosso
        return styles

    # Le sezioni di riepilogo annuale e aggregato rimangono invariate
    st.subheader("Tabella di Confronto per Tipologia di Servizio (Dettagliato)")
    pivot_servizi = full_data.pivot_table(values='Importo Totale', index='Servizio', columns='Anno', aggfunc='sum').fillna(0)
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
    st.subheader("Confronto per Categorie Aggregate")
    df_aggregato = full_data.copy()
    servizio_mapping = {'Parcometri': 'Sosta Occasionale', 'Hub Sosta (App)': 'Sosta Occasionale', 'Tap&Park': 'Sosta Occasionale', 'Autorizzazioni': 'Autorizzazioni', 'Abbonamenti': 'Abbonamenti'}
    df_aggregato['Categoria'] = df_aggregato['Servizio'].map(servizio_mapping)
    pivot_aggregato = df_aggregato.pivot_table(values='Importo Totale', index='Categoria', columns='Anno', aggfunc='sum').fillna(0)
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

    ### 2. ORDINAMENTO PERSONALIZZATO ###
    # Definisci l'ordine desiderato in un dizionario
    ordine_servizi = {
        "Autorizzazioni": 1,
        "Abbonamenti": 2,
        "Parcometri": 3,
        "Hub Sosta (App)": 4,
        "Tap&Park": 5
    }
    lista_servizi_unica = list(full_data['Servizio'].unique())
    # Ordina la lista usando il dizionario. Aggiungi 999 per gestire eventuali nuovi servizi non presenti nel dizionario.
    lista_servizi_unica.sort(key=lambda x: ordine_servizi.get(x, 999))
    opzioni_filtro = ['Tutti i Servizi'] + lista_servizi_unica
    
    ### 1. LAYOUT A COLONNE PER IL MENU ###
    # Crea una colonna larga 1/4 per il menu e lascia le altre 3/4 vuote
    col_menu, col_vuota = st.columns([1, 3])
    
    with col_menu:
        servizio_selezionato = st.selectbox(
            "Seleziona una linea di prodotto da analizzare:",
            options=opzioni_filtro,
            key="filtro_servizio" # Aggiungiamo una key anche qui per massima stabilità
        )
    
    # Il resto del codice rimane fuori dalle colonne per usare la piena larghezza
    if servizio_selezionato == 'Tutti i Servizi':
        dati_filtrati = full_data.copy()
        titolo_grafico = f"Confronto Andamento Mensile Incassi (Tutti i Servizi)"
    else:
        dati_filtrati = full_data[full_data['Servizio'] == servizio_selezionato].copy()
        titolo_grafico = f"Confronto Andamento Mensile Incassi per: {servizio_selezionato}"
    
    pivot_confronto = dati_filtrati.pivot_table(values='Importo Totale', index='Mese', columns='Anno', aggfunc='sum').fillna(0)
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
    st.plotly_chart(fig_line, use_container_width=True, key=f"confronto_mensile_{servizio_selezionato}")
# --- CONTENUTO DEGLI ALTRI TAB ---
with tab_anno1:
    display_analysis_for_year(full_data, ANNO_1)

with tab_anno2:
    display_analysis_for_year(full_data, ANNO_2)