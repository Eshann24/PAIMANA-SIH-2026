from pathlib import Path
import re
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'results' / 'risk_engine'
MODEL_READY = ROOT / 'model_ready_dataset.csv'

st.set_page_config(
    page_title='PAIMANA | Infrastructure Monitoring Command Center',
    page_icon='PA',
    layout='wide',
    initial_sidebar_state='expanded',
)

st.markdown('''
<style>
.block-container {padding-top: 1.15rem; padding-bottom: 2.5rem; max-width: 1500px;}
.hero {background: linear-gradient(120deg,#0b3558,#176b91); color:#fff; padding:1.35rem 1.7rem; border-radius:14px; margin-bottom:1rem; box-shadow:0 4px 14px rgba(15,53,88,.12);}
.hero h1 {margin:0; font-size:2rem; letter-spacing:-.02em;}
.hero p {margin:.38rem 0 0; opacity:.92; font-size:1rem;}
.section-title {font-size:1.35rem; font-weight:700; color:#153b5b; margin:.65rem 0 .35rem;}
.section-note {color:#5f6f7d; font-size:.9rem; margin-bottom:.65rem;}
.kpi {background:#f7fafc; border:1px solid #dce7ef; border-radius:11px; padding:.82rem .95rem; min-height:94px; height:100%; overflow-wrap:anywhere;}
.kpi-label {font-size:.71rem;color:#596b79;text-transform:uppercase;letter-spacing:.055em;line-height:1.22;}
.kpi-value {font-size:1.52rem;font-weight:750;color:#123b5c;margin-top:.48rem;line-height:1.14;}
.kpi-value-long {font-size:1.04rem;line-height:1.18;}
.status-panel {background:#eef6fa; border-left:4px solid #176b91; border-radius:8px; padding:.85rem 1rem; margin:.75rem 0 1.05rem; color:#183d56;}
.signal {background:#f7fafc;border-left:4px solid #176b91;padding:.65rem .85rem;margin:.4rem 0;border-radius:5px;}
.signal b {color:#153b5b;}
.small-note {font-size:.82rem;color:#61717e;}
.card {background:#fff;border:1px solid #e1e8ee;border-radius:10px;padding:1rem;}
.active {color:#a33036;font-weight:750;}
.inactive {color:#3f7d59;font-weight:650;}
.warning-grid {display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.55rem;}
.warning-item {background:#f7fafc;border:1px solid #e1e8ee;border-radius:8px;padding:.65rem .7rem;min-height:75px;}
.warning-name {font-size:.75rem;color:#526273;line-height:1.2;}
.warning-state {font-size:.85rem;margin-top:.45rem;}
@media (max-width: 900px) {.warning-grid {grid-template-columns:repeat(2,minmax(0,1fr));}.hero h1 {font-size:1.55rem;}}
</style>
''', unsafe_allow_html=True)


FILES = {
    'summary': 'project_risk_summary.csv',
    'predictions': 'project_risk_predictions.csv',
    'explanations': 'project_explanations.csv',
    'warnings': 'early_warning_scores.csv',
    'trends': 'risk_trends.csv',
    'importance': 'permutation_importance.csv',
}


@st.cache_data(show_spinner=False)
def load_data():
    data = {key: pd.read_csv(DATA / filename, dtype='string') for key, filename in FILES.items()}
    if MODEL_READY.exists():
        model_ready = pd.read_csv(MODEL_READY, dtype='string')
        keep = [c for c in [
            'Project Code', 'Report_Month', 'physical_progress_pct',
            'cumulative_expenditure_cr', 'expected_progress_by_time_pct',
            'progress_vs_expected_pct_points',
        ] if c in model_ready.columns]
        data['observations'] = model_ready[keep].copy()
    else:
        data['observations'] = pd.DataFrame()
    return data


def numeric(value):
    return pd.to_numeric(value, errors='coerce')


def fmt_num(value, decimals=2, suffix=''):
    n = numeric(pd.Series([value])).iloc[0]
    return '—' if pd.isna(n) else f'{n:,.{decimals}f}{suffix}'


def short_band(value):
    mapping = {
        'LOW EARLY-WARNING SIGNAL': 'LOW',
        'MODERATE EARLY-WARNING SIGNAL': 'MODERATE',
        'HIGH EARLY-WARNING SIGNAL': 'HIGH',
        'VERY HIGH EARLY-WARNING SIGNAL': 'VERY HIGH',
    }
    return mapping.get(str(value), '—' if pd.isna(value) else str(value))


def trend_value(value):
    return 'NO PRIOR CONSECUTIVE SCORE' if pd.isna(value) or str(value).strip() == '' else str(value)


def risk_colors():
    return {
        'LOW EARLY-WARNING SIGNAL': '#4f8a68',
        'MODERATE EARLY-WARNING SIGNAL': '#e0ad34',
        'HIGH EARLY-WARNING SIGNAL': '#d96d3c',
        'VERY HIGH EARLY-WARNING SIGNAL': '#b53d4f',
        'LOW': '#4f8a68', 'MODERATE': '#e0ad34', 'HIGH': '#d96d3c', 'VERY HIGH': '#b53d4f',
    }


def trend_colors():
    return {'IMPROVING': '#4f8a68', 'STABLE': '#71808c', 'WORSENING': '#b53d4f', 'NO PRIOR CONSECUTIVE SCORE': '#9aa6ae'}


def kpi(label, value, help_text=None, compact=False):
    help_attr = f' title="{help_text}"' if help_text else ''
    value_class = 'kpi-value kpi-value-long' if compact else 'kpi-value'
    st.markdown(f'<div class="kpi"{help_attr}><div class="kpi-label">{label}</div><div class="{value_class}">{value}</div></div>', unsafe_allow_html=True)


def page_header(title, note=''):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="section-note">{note}</div>', unsafe_allow_html=True)


def hero():
    st.markdown('<div class="hero"><h1>PAIMANA | Infrastructure Monitoring Command Center</h1><p>Predictive analytics and early-warning signals for SIH 2026</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="status-panel"><b>Prototype early-warning system for next-month reported physical-progress decline.</b><br>Risk bands are prototype operating categories, not calibrated probabilities of project failure. All scores and warning indicators should be interpreted as model-associated and rule-based monitoring signals.</div>', unsafe_allow_html=True)


FEATURE_LABELS = {
    'target_schedule_duration_months': 'Planned schedule duration',
    'project_age_months': 'Project age',
    'progress_vs_expected_pct_points': 'Progress vs expected',
    'expected_progress_by_time_pct': 'Expected progress by time',
    'cumulative_expenditure_cr': 'Cumulative expenditure',
    'original_cost_cr': 'Original project cost',
    'Agency': 'Agency category',
    'State': 'State category',
    'physical_progress_pct': 'Physical progress',
    'physical_progress_lag_1': 'Previous-month physical progress',
    'physical_progress_change_1m': 'Month-to-month progress change',
    'physical_progress_acceleration_1m': 'Progress acceleration',
    'expenditure_vs_expected_progress_pct_points': 'Expenditure vs expected progress',
    'expenditure_pct_original_cost': 'Expenditure as percentage of original cost',
    'elapsed_implementation_months': 'Elapsed implementation time',
    'cumulative_expenditure_change_1m': 'Month-to-month expenditure change',
}
PERCENT_FEATURES = {'physical_progress_pct', 'progress_vs_expected_pct_points', 'expected_progress_by_time_pct', 'expenditure_vs_expected_progress_pct_points', 'expenditure_pct_original_cost'}
COST_FEATURES = {'cumulative_expenditure_cr', 'original_cost_cr', 'cumulative_expenditure_change_1m'}
MONTH_FEATURES = {'target_schedule_duration_months', 'project_age_months', 'elapsed_implementation_months'}


def human_feature_name(feature):
    return FEATURE_LABELS.get(feature, feature.replace('_', ' ').strip().capitalize())


def format_signal_value(feature, value):
    if pd.isna(value) or str(value).strip() == '':
        return 'missing'
    if feature in PERCENT_FEATURES:
        return fmt_num(value, 2, '%')
    if feature in COST_FEATURES:
        return fmt_num(value, 2, ' cr')
    if feature in MONTH_FEATURES:
        return fmt_num(value, 1, ' months')
    return str(value)


def readable_signal(raw_signal, observed_value):
    raw = '' if pd.isna(raw_signal) else str(raw_signal)
    feature, _, detail = raw.partition(':')
    feature = feature.strip()
    if not feature:
        return None
    relation = detail.split(';')[0].strip() if detail else 'associated with the model score'
    match = re.search(r'global importance\s+([-+]?\d*\.?\d+)', raw)
    importance = f'{float(match.group(1)):.6f}' if match else 'not available'
    value = str(observed_value).split(' (model score change', 1)[0].strip()
    explanation = f'Model-associated signal associated with the model score; {relation.lower()}. This is not a causal explanation.'
    return human_feature_name(feature), format_signal_value(feature, value), explanation, importance


def chart_layout(fig, height=360):
    fig.update_layout(height=height, margin=dict(l=20, r=20, t=60, b=55), legend_title_text='', template='plotly_white')
    return fig


def latest_summary(s):
    return s.copy()


def active_warning_count(row):
    cols = ['Top Warning Signal 1', 'Top Warning Signal 2', 'Top Warning Signal 3']
    return int((row[cols].fillna('') != 'No thresholded rule warning').sum())


def command_center(d):
    s = latest_summary(d['summary'])
    active_projects = int((~s[['Top Warning Signal 1', 'Top Warning Signal 2', 'Top Warning Signal 3']].fillna('').eq('No thresholded rule warning').all(axis=1)).sum())
    cols = st.columns(5, gap='small')
    values = [
        ('Projects Monitored', f'{len(s):,}'),
        ('Very High Signals', f'{(s["Risk Band"] == "VERY HIGH EARLY-WARNING SIGNAL").sum():,}'),
        ('High Signals', f'{(s["Risk Band"] == "HIGH EARLY-WARNING SIGNAL").sum():,}'),
        ('Worsening Risk Trends', f'{(s["Risk Trend"] == "WORSENING").sum():,}'),
        ('Active Warning Indicators', f'{active_projects:,}'),
    ]
    for col, (label, value) in zip(cols, values):
        with col:
            kpi(label, value)

    st.divider()
    page_header('Command status', 'Latest eligible project summaries are used for the project-level KPIs. July raw observations are not treated as scored future-outcome rows.')
    c1, c2 = st.columns([1.1, 1], gap='large')
    with c1:
        band = s['Risk Band'].map(short_band).value_counts().rename_axis('Risk Band').reset_index(name='Projects')
        st.plotly_chart(chart_layout(px.bar(band, x='Risk Band', y='Projects', color='Risk Band', color_discrete_map=risk_colors(), title='Latest eligible project risk bands')), use_container_width=True)
    with c2:
        trend = s['Risk Trend'].map(trend_value).value_counts().rename_axis('Risk Trend').reset_index(name='Projects')
        st.plotly_chart(chart_layout(px.bar(trend, x='Risk Trend', y='Projects', color='Risk Trend', color_discrete_map=trend_colors(), title='Latest eligible project trends')), use_container_width=True)

    state = s.assign(State=s['State'].fillna('Unknown'))
    state = state[state['Risk Band'].isin(['HIGH EARLY-WARNING SIGNAL', 'VERY HIGH EARLY-WARNING SIGNAL'])].groupby('State').size().sort_values(ascending=False).head(10).sort_values().reset_index(name='High + Very High Projects')
    if not state.empty:
        st.plotly_chart(chart_layout(px.bar(state, x='High + Very High Projects', y='State', orientation='h', color='High + Very High Projects', color_continuous_scale=['#f1c453', '#b53d4f'], title='Top states by high and very-high latest signals')), use_container_width=True)

    page_header('Projects requiring attention', 'A compact operational queue combining HIGH / VERY HIGH latest signals and WORSENING latest trends.')
    attention = s[s['Risk Band'].isin(['VERY HIGH EARLY-WARNING SIGNAL', 'HIGH EARLY-WARNING SIGNAL']) | s['Risk Trend'].eq('WORSENING')].copy()
    attention['Risk Band'] = attention['Risk Band'].map(short_band)
    attention['Risk Trend'] = attention['Risk Trend'].map(trend_value)
    attention['ML Probability'] = numeric(attention['ML Probability']).map(lambda x: f'{x:.2%}' if pd.notna(x) else '—')
    st.dataframe(attention[['Project Code', 'Project Name', 'State', 'Agency', 'Latest Report Month', 'ML Probability', 'Risk Band', 'Risk Trend', 'Top Warning Signal 1']], hide_index=True, use_container_width=True, column_config={
        'Project Code': st.column_config.TextColumn('Project Code', width='small'),
        'Project Name': st.column_config.TextColumn('Project Name', width='large'),
        'State': st.column_config.TextColumn('State', width='medium'),
        'Agency': st.column_config.TextColumn('Agency', width='medium'),
        'Latest Report Month': st.column_config.TextColumn('Latest Eligible Prediction Month', width='medium'),
        'ML Probability': st.column_config.TextColumn('Model-Associated Score', width='small'),
        'Risk Band': st.column_config.TextColumn('Risk Band', width='small'),
        'Risk Trend': st.column_config.TextColumn('Risk Trend', width='medium'),
        'Top Warning Signal 1': st.column_config.TextColumn('Top Warning Indicator', width='large'),
    })


def explorer_filters(s, key_prefix='explorer'):
    st.sidebar.markdown('### Project filters')
    search = st.sidebar.text_input('Search Project Code or Project Name', '', key=f'{key_prefix}_search')
    states = sorted(s['State'].dropna().unique().tolist())
    agencies = sorted(s['Agency'].dropna().unique().tolist())
    bands = ['LOW', 'MODERATE', 'HIGH', 'VERY HIGH']
    trends = ['IMPROVING', 'STABLE', 'WORSENING', 'NO PRIOR CONSECUTIVE SCORE']
    months = sorted(s['Latest Report Month'].dropna().unique().tolist())
    chosen_state = st.sidebar.multiselect('State', states, key=f'{key_prefix}_state')
    chosen_agency = st.sidebar.multiselect('Agency', agencies, key=f'{key_prefix}_agency')
    chosen_band = st.sidebar.multiselect('Risk Band', bands, key=f'{key_prefix}_band')
    chosen_trend = st.sidebar.multiselect('Risk Trend', trends, key=f'{key_prefix}_trend')
    chosen_month = st.sidebar.multiselect('Latest Eligible Prediction Month', months, key=f'{key_prefix}_month')
    out = s.copy()
    out['_short_band'] = out['Risk Band'].map(short_band)
    out['_trend_display'] = out['Risk Trend'].map(trend_value)
    if search:
        text = (out['Project Code'].fillna('') + ' ' + out['Project Name'].fillna('')).str.contains(search, case=False, na=False)
        out = out[text]
    if chosen_state: out = out[out['State'].isin(chosen_state)]
    if chosen_agency: out = out[out['Agency'].isin(chosen_agency)]
    if chosen_band: out = out[out['_short_band'].isin(chosen_band)]
    if chosen_trend: out = out[out['_trend_display'].isin(chosen_trend)]
    if chosen_month: out = out[out['Latest Report Month'].isin(chosen_month)]
    return out


def display_project_table(s):
    if s.empty:
        st.info('No projects match the current filters.')
        return
    view = s.copy()
    view['Active Warning Indicators'] = view.apply(active_warning_count, axis=1)
    view['Top Model-Associated Signal'] = view['Top Warning Signal 1'].fillna('No model-associated signal available')
    view['Risk Band'] = view['Risk Band'].map(short_band)
    view['Risk Trend'] = view['Risk Trend'].map(trend_value)
    view['ML Probability'] = numeric(view['ML Probability']).map(lambda x: f'{x:.2%}' if pd.notna(x) else '—')
    view = view.rename(columns={'Latest Report Month': 'Latest Eligible Prediction Month'})
    columns = ['Project Code', 'Project Name', 'State', 'Agency', 'Latest Eligible Prediction Month', 'ML Probability', 'Risk Band', 'Risk Trend', 'Active Warning Indicators', 'Top Model-Associated Signal']
    st.dataframe(view[columns], hide_index=True, use_container_width=True, column_config={
        'Project Code': st.column_config.TextColumn('Project Code', width='small'),
        'Project Name': st.column_config.TextColumn('Project Name', width='large'),
        'State': st.column_config.TextColumn('State', width='medium'),
        'Agency': st.column_config.TextColumn('Agency', width='medium'),
        'Latest Eligible Prediction Month': st.column_config.TextColumn('Latest Eligible Prediction Month', width='medium'),
        'ML Probability': st.column_config.TextColumn('Model-Associated Score', width='small'),
        'Risk Band': st.column_config.TextColumn('Risk Band', width='small'),
        'Risk Trend': st.column_config.TextColumn('Risk Trend', width='medium'),
        'Active Warning Indicators': st.column_config.NumberColumn('Active Warning Indicators', width='small'),
        'Top Model-Associated Signal': st.column_config.TextColumn('Top Model-Associated Signal', width='large'),
    })
    st.download_button('Download filtered project table', view[columns].to_csv(index=False).encode('utf-8'), 'paimana_filtered_project_risk_summary.csv', 'text/csv')


def project_explorer(d):
    page_header('Project Explorer', 'Filter the one-row-per-project latest eligible summary. Use Project Code for identity; Project Name is display metadata.')
    filtered = explorer_filters(d['summary'])
    st.caption(f'{len(filtered):,} projects match the current filters.')
    display_project_table(filtered)


def project_choices(s, key):
    choices = s[['Project Code', 'Project Name']].drop_duplicates('Project Code').copy()
    choices['display'] = choices['Project Name'].fillna('Unnamed project') + ' | ' + choices['Project Code'].astype(str)
    selected = st.selectbox('Select project', choices['Project Code'].tolist(), format_func=lambda x: choices.loc[choices['Project Code'] == x, 'display'].iloc[0], key=key)
    return selected


def warning_cards(row):
    labels = [
        ('progress_behind_expected', 'Progress Behind Expected'),
        ('recent_progress_slowdown', 'Recent Progress Slowdown'),
        ('expenditure_ahead_of_progress', 'Expenditure Ahead of Progress'),
        ('long_implementation_duration', 'Long Implementation Duration'),
        ('schedule_pressure', 'Schedule Pressure'),
    ]
    cards = []
    for field, label in labels:
        is_active = str(row.get(field, '0')) == '1'
        state = 'ACTIVE' if is_active else 'INACTIVE'
        cls = 'active' if is_active else 'inactive'
        cards.append(f'<div class="warning-item"><div class="warning-name">{label}</div><div class="warning-state {cls}">{state}</div></div>')
    st.markdown('<div class="warning-grid">' + ''.join(cards) + '</div>', unsafe_allow_html=True)


def project_detail(d):
    page_header('Project Detail', 'Detailed project identity, current latest eligible status, rule-based warning indicators, model-associated signals, and scored monthly observations.')
    selected = project_choices(d['summary'], 'detail_project')
    row = d['summary'][d['summary']['Project Code'] == selected].iloc[0]
    st.subheader(str(row['Project Name']))
    st.caption(f'Project Code: {selected} | Latest eligible prediction month: {row["Latest Report Month"]}')

    cols = st.columns([1.35, 1, 1, 1, 1, 1], gap='small')
    identity = [('Agency', row['Agency']), ('State', row['State']), ('Risk Band', short_band(row['Risk Band'])), ('Model-Associated Score', fmt_num(row['ML Probability'], 2, '%')), ('Risk Trend', trend_value(row['Risk Trend'])), ('Active Warning Indicators', active_warning_count(row))]
    for col, (label, value) in zip(cols, identity):
        with col:
            kpi(label, '—' if pd.isna(value) else str(value), 'Official band: ' + str(row['Risk Band']) if label == 'Risk Band' else None, compact=label in {'Agency', 'State'})

    st.divider()
    page_header('Current rule-based warning indicators')
    warning_row = d['warnings'][d['warnings']['Project Code'] == selected].copy().sort_values('Report_Month')
    if warning_row.empty:
        st.info('No warning-indicator row is available for this project.')
    else:
        warning_cards(warning_row.iloc[-1])

    st.divider()
    page_header('Model-Associated Signals', 'These are global-importance-informed model-associated factors, not causal explanations.')
    exp = d['explanations'][d['explanations']['Project Code'] == selected].sort_values('Report_Month')
    if exp.empty:
        st.info('No model-associated signal details are available for this project.')
    else:
        e = exp.iloc[-1]
        shown = 0
        for i in range(1, 4):
            parsed = readable_signal(e.get(f'top_factor_{i}', ''), e.get(f'top_factor_{i}_value', ''))
            if parsed:
                label, value, explanation, importance = parsed
                st.markdown(f'<div class="signal"><b>{label}</b><br><span class="small-note">Observed value: {value}. {explanation} Global model-associated importance: {importance}.</span></div>', unsafe_allow_html=True)
                shown += 1
        if not shown:
            st.info('No model-associated signals are available for this project.')

    st.divider()
    page_header('Scored monthly observations', 'Each point is a scored project-month observation. The project summary above is the latest eligible prediction month, not necessarily the latest raw observation month.')
    monthly = d['predictions'][d['predictions']['Project Code'] == selected].copy().sort_values('Report_Month')
    if monthly.empty:
        st.info('No scored monthly observations are available for this project.')
        return
    monthly = monthly.merge(d['explanations'][['Project Code', 'Report_Month', 'risk_band']], on=['Project Code', 'Report_Month'], how='left')
    obs = d['observations']
    if not obs.empty:
        monthly = monthly.merge(obs, on=['Project Code', 'Report_Month'], how='left')
    monthly['Month Display'] = pd.to_datetime(monthly['Report_Month'], format='%Y-%m', errors='coerce').dt.strftime('%b %Y')
    monthly['Score'] = numeric(monthly['predicted_probability'])
    monthly['Risk Band Short'] = monthly['risk_band'].map(short_band)
    c1, c2 = st.columns(2, gap='large')
    with c1:
        fig = px.line(monthly, x='Month Display', y='Score', markers=True, color='Risk Band Short', color_discrete_map=risk_colors(), title='Model-associated score by scored month')
        fig.update_yaxes(tickformat='.0%')
        st.plotly_chart(chart_layout(fig), use_container_width=True)
    with c2:
        if 'physical_progress_pct' in monthly.columns:
            plot = monthly.rename(columns={'physical_progress_pct': 'Physical Progress'}).copy()
            plot['Physical Progress'] = numeric(plot['Physical Progress'])
            fig = px.line(plot, x='Month Display', y='Physical Progress', markers=True, title='Reported physical progress by scored month')
            fig.update_yaxes(ticksuffix='%')
            st.plotly_chart(chart_layout(fig), use_container_width=True)
        else:
            st.info('Physical-progress time series is unavailable in the current artifacts.')
    c3, c4 = st.columns(2, gap='large')
    with c3:
        if 'cumulative_expenditure_cr' in monthly.columns:
            plot = monthly.rename(columns={'cumulative_expenditure_cr': 'Cumulative Expenditure'}).copy()
            plot['Cumulative Expenditure'] = numeric(plot['Cumulative Expenditure'])
            fig = px.line(plot, x='Month Display', y='Cumulative Expenditure', markers=True, title='Cumulative expenditure by scored month')
            fig.update_yaxes(ticksuffix=' cr')
            st.plotly_chart(chart_layout(fig), use_container_width=True)
        else:
            st.info('Cumulative-expenditure time series is unavailable in the current artifacts.')
    with c4:
        if {'physical_progress_pct', 'expected_progress_by_time_pct'} <= set(monthly.columns):
            plot = monthly.rename(columns={'physical_progress_pct': 'Physical Progress', 'expected_progress_by_time_pct': 'Expected Progress'}).copy()
            plot['Physical Progress'] = numeric(plot['Physical Progress'])
            plot['Expected Progress'] = numeric(plot['Expected Progress'])
            plot = plot.melt(id_vars=['Month Display'], value_vars=['Physical Progress', 'Expected Progress'], var_name='Measure', value_name='Percent')
            fig = px.line(plot, x='Month Display', y='Percent', color='Measure', markers=True, title='Actual vs expected progress by scored month')
            fig.update_yaxes(ticksuffix='%')
            st.plotly_chart(chart_layout(fig), use_container_width=True)
        else:
            st.info('Expected-progress comparison is unavailable in the current artifacts.')

    trends = d['trends'][d['trends']['Project Code'] == selected].sort_values('Report_Month')
    if not trends.empty:
        valid = trends[trends['risk_trend'].notna()]
        if not valid.empty:
            st.caption('Valid consecutive-month trends: ' + ', '.join(f'{m} {t}' for m, t in zip(valid['Report_Month'], valid['risk_trend'])))
        else:
            st.caption('No prior consecutive score is available for this project.')


def analytics(d):
    s = d['summary'].copy()
    page_header('Risk Analytics', 'Interactive distributions and operational patterns from the latest eligible project summaries and global model diagnostics.')
    c1, c2 = st.columns(2, gap='large')
    with c1:
        band = s['Risk Band'].map(short_band).value_counts().rename_axis('Risk Band').reset_index(name='Projects')
        st.plotly_chart(chart_layout(px.pie(band, names='Risk Band', values='Projects', color='Risk Band', color_discrete_map=risk_colors(), title='Risk-band distribution')), use_container_width=True)
    with c2:
        trend = s['Risk Trend'].map(trend_value).value_counts().rename_axis('Risk Trend').reset_index(name='Projects')
        st.plotly_chart(chart_layout(px.bar(trend, x='Risk Trend', y='Projects', color='Risk Trend', color_discrete_map=trend_colors(), title='Risk-trend distribution')), use_container_width=True)

    warning_map = {
        'Progress Behind Expected': 'progress_behind_expected',
        'Recent Progress Slowdown': 'recent_progress_slowdown',
        'Expenditure Ahead of Progress': 'expenditure_ahead_of_progress',
        'Long Implementation Duration': 'long_implementation_duration',
        'Schedule Pressure': 'schedule_pressure',
    }
    ew = d['warnings'].copy()
    warning_counts = pd.DataFrame({'Indicator': list(warning_map), 'Active Rows': [int((ew[c] == '1').sum()) for c in warning_map.values()]})
    st.plotly_chart(chart_layout(px.bar(warning_counts.sort_values('Active Rows'), x='Active Rows', y='Indicator', orientation='h', title='Warning-indicator frequency across scored project-month rows', color='Active Rows', color_continuous_scale=['#e0ad34', '#b53d4f'])), use_container_width=True)

    c1, c2 = st.columns(2, gap='large')
    with c1:
        state = s.assign(State=s['State'].fillna('Unknown')).groupby(['State', 'Risk Band']).size().reset_index(name='Projects')
        state['Risk Band'] = state['Risk Band'].map(short_band)
        st.plotly_chart(chart_layout(px.bar(state, x='Projects', y='State', color='Risk Band', orientation='h', barmode='stack', color_discrete_map=risk_colors(), title='State-level risk distribution')), use_container_width=True)
    with c2:
        agency = s.assign(Agency=s['Agency'].fillna('Unknown')).groupby(['Agency', 'Risk Band']).size().reset_index(name='Projects')
        top_agencies = agency.groupby('Agency')['Projects'].sum().nlargest(12).index
        agency = agency[agency['Agency'].isin(top_agencies)]
        agency['Risk Band'] = agency['Risk Band'].map(short_band)
        st.plotly_chart(chart_layout(px.bar(agency, x='Projects', y='Agency', color='Risk Band', orientation='h', barmode='stack', color_discrete_map=risk_colors(), title='Agency-level risk distribution')), use_container_width=True)

    probs = numeric(s['ML Probability']).dropna()
    st.plotly_chart(chart_layout(px.histogram(probs, nbins=24, labels={'value': 'Model-associated score'}, title='Distribution of model-associated scores')), use_container_width=True)
    imp = d['importance'].copy().sort_values('mean_importance', ascending=False).head(15).sort_values('mean_importance')
    imp['Feature'] = imp['feature'].map(human_feature_name)
    st.plotly_chart(chart_layout(px.bar(imp, x='mean_importance', y='Feature', orientation='h', error_x='std_importance', title='Global model-associated feature importance')), use_container_width=True)
    st.caption('Permutation importance and model-associated signals indicate association with the model score, not causation.')


def methodology(d):
    page_header('Methodology', 'A concise operating reference for the PAIMANA SIH 2026 prototype.')
    st.markdown('''
### Data

- PAIMANA infrastructure project observations
- Source window: **April–July 2026**
- Engineered dataset: **7,590 project-month records**
- Repeated `Project Code` values represent observations of the same project over time.

### Prediction target

`future_physical_progress_decline_1m`

The model estimates whether the **next consecutive monthly observation** for a project shows a decline in reported physical progress. It does not predict project failure, actual cost overrun, or actual schedule overrun.

### Temporal validation and eligibility

- Predictions are generated only for rows with a valid next-month observation.
- July 2026 is not part of the scored prediction cohort because no August observation is available.
- No artificial future rows or August targets were created.
- Validation uses forward temporal folds rather than random row splitting.

### Model

The dashboard reuses the existing trained **Random Forest** artifact. No retraining or expensive ML computation occurs when the dashboard starts.

### Prototype risk bands

| Model-associated score | Operating category |
|---:|---|
| `< 0.10` | LOW EARLY-WARNING SIGNAL |
| `0.10–<0.30` | MODERATE EARLY-WARNING SIGNAL |
| `0.30–<0.50` | HIGH EARLY-WARNING SIGNAL |
| `>= 0.50` | VERY HIGH EARLY-WARNING SIGNAL |

These are **prototype operating categories, not calibrated probabilities of project failure**.

### Warning indicators

Current rule-based warning indicators are calculated from current or prior information only:

- **Progress Behind Expected:** progress gap `< -20` percentage points
- **Recent Progress Slowdown:** month-to-month progress change `<= -2` percentage points
- **Expenditure Ahead of Progress:** expenditure gap `> 20` percentage points
- **Long Implementation Duration:** elapsed implementation time `>= 60` months
- **Schedule Pressure:** expected progress `>= 80%` and progress gap `< -10` points

### Model-associated signals

Project-level model-associated signals use global permutation-importance ranking and comparisons with a reference distribution. They are not causal explanations. The dashboard uses the wording **model-associated signal**, **higher-than-reference value**, **lower-than-reference value**, and **trajectory signal**.

### Limitations

- Only a short historical observation window is currently available.
- The target is relatively rare.
- Only two forward validation folds are currently available.
- The model should be treated as a prototype.
- Further historical data, calibration, and external validation are required before production deployment.
''')
    st.warning('Operational interpretation: use this dashboard to prioritize review and monitoring. Do not treat a band as a calibrated probability of project failure or as proof that a project will overrun.')


def main():
    d = load_data()
    hero()
    with st.sidebar:
        st.markdown('## Navigation')
        page = st.radio('Go to', ['Command Center', 'Project Explorer', 'Project Detail', 'Risk Analytics', 'Methodology'], label_visibility='collapsed')
        st.markdown('---')
        st.caption('Data source: existing PAIMANA risk-engine outputs.\n\nThe dashboard reports early-warning signals for next-month reported physical-progress decline. It does not report calibrated failure, cost-overrun, or schedule-overrun probabilities.')
    if page == 'Command Center':
        command_center(d)
    elif page == 'Project Explorer':
        project_explorer(d)
    elif page == 'Project Detail':
        project_detail(d)
    elif page == 'Risk Analytics':
        analytics(d)
    else:
        methodology(d)


if __name__ == '__main__':
    main()
