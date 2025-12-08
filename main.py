import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import FuncFormatter
import os
import matplotlib.dates as mdates
from agent import run_query
import kpis

st.set_page_config(page_title="Cloudbot", layout="wide")
# Header: title on the left, optional logo on the right

with st.sidebar:
    st.header("Daily KPIs")
    # 1. Inputs
    kpi_date = st.date_input("Reference Date", value=None)
    
    st.subheader("Alert Thresholds")
    # Use columns in sidebar for compact threshold inputs
    sb_col1, sb_col2 = st.columns(2)
    with sb_col1:
        thresh_low = st.number_input("Lower (<)", value=-0.25, step=0.05, format="%.2f")
    with sb_col2:
        thresh_high = st.number_input("Upper (>)", value=0.25, step=0.05, format="%.2f")

    default_webhook = os.getenv("ALERT_WEBHOOK_URL", "")
    kpi_webhook = st.text_input("Webhook URL", value=default_webhook)

    st.markdown("---")

    # 2. Run Button
    if st.button("Run KPIs", use_container_width=True):
        import datetime as _dt
        target = kpi_date if kpi_date is not None else _dt.date.today()
        
        st.session_state['kpi_summary'] = kpis.compute_daily_tpv_summary(target)
        st.session_state['kpi_ran'] = True

    # 3. Sidebar Results
    if st.session_state.get('kpi_ran'):
        summary = st.session_state['kpi_summary']
        
        st.success(f"**TPV Summary: {summary['date']}**")
        st.write(f"**Total:** {kpis.format_currency(summary.get('tpv'))}")
        st.markdown("---")
        
        # Helper to color code the output
        def display_metric(label, key):
            val = summary.get(key)
            pct = summary.get(f"pct_{key}".replace("tpv_", "vs_"))
            
            icon = "➖"
            if pct is not None:
                if pct < thresh_low: icon = "🔻"
                elif pct > thresh_high: icon = "🔺"
            
            # Using simple text for sidebar cleanliness
            st.write(f"**{label}**: {kpis.format_currency(val)}")
            st.caption(f"{icon} {kpis.format_pct(pct)} change")

        display_metric("vs D-1", "tpv_d1")
        display_metric("vs D-7", "tpv_d7")
        display_metric("vs D-30", "tpv_d30")

        # Alert Logic
        fired_reasons = []
        check_periods = ["d1", "d7", "d30"]
        
        for period in check_periods:
            pct = summary.get(f"pct_vs_{period}")
            if pct is not None:
                if pct < thresh_low:
                    fired_reasons.append(f"{period} (Drop {kpis.format_pct(pct)})")
                elif pct > thresh_high:
                    fired_reasons.append(f"{period} (Spike {kpis.format_pct(pct)})")

        if fired_reasons:
            st.error(f"⚠️ Triggers: {', '.join(fired_reasons)}")
            
            current_triggers = {"low": thresh_low, "high": thresh_high}
            alert_msg = kpis.build_alert_message(summary, current_triggers)
            alert_msg += f"\n\nSpecific Triggers:\n" + "\n".join(f"- {r}" for r in fired_reasons)
            
            with st.expander("View Alert Message"):
                st.code(alert_msg, language="text")

            if kpi_webhook:
                if st.button("Send Alert 🚀", use_container_width=True):
                    ok = kpis.send_webhook_alert(kpi_webhook, alert_msg, extra=summary)
                    if ok:
                        st.toast("Webhook sent successfully!", icon="✅")
                    else:
                        st.error("Failed to send webhook")
        else:
            st.info("✅ No alerts fired.")


# Set theme and palette
sns.set_theme(style="whitegrid")
TEXT_COLOR = "#ffffff" # Force white for charts on dark backgrounds

IMAGE_PATH = os.getenv("APP_LOGO_PATH", "")
if not IMAGE_PATH:
    IMAGE_PATH = "logo.png"

cols = st.columns([0.06, 0.94])

with cols[0]:

    try:

        st.image(IMAGE_PATH, width=80)

    except Exception:

        pass    

with cols[1]:

    st.title("Cloudbot – Transaction Analytics Agent")

question = st.text_input(
    "Ask a question about the transaction data:",
    placeholder="e.g., What is the total amount by MCC for last week?"
)

# 1. RUN QUERY
if st.button("Run Query"):
    if question:
        with st.spinner("Generating SQL..."):
            sql, result = run_query(question)
            st.session_state['last_sql'] = sql
            st.session_state['last_result'] = result
            st.session_state['query_ran'] = True
    else:
        st.warning("Please enter a question.")

# 2. DISPLAY RESULTS
if st.session_state.get('query_ran'):
    sql = st.session_state.get('last_sql')
    result = st.session_state.get('last_result')

    st.subheader("Generated SQL")
    st.code(sql, language="sql")

    st.subheader("Results")
    if isinstance(result, str):
        st.error(result)
    else:
        df: pd.DataFrame = result
        st.dataframe(df)

        # ---------------------------------------------------------
        # Interactive Visualization Section
        # ---------------------------------------------------------
        if not df.empty and df.shape[1] >= 1:
            st.markdown("---")
            
            viz_col1, viz_col2 = st.columns([1, 1])
            with viz_col1:
                st.subheader("Visualization")
            with viz_col2:
                chart_type = st.radio(
                    "Chart Type",
                    ["Bar", "Line", "Boxplot"],
                    horizontal=True,
                    label_visibility="collapsed"
                )

            try:
                # 1. SMART COLUMN DETECTION
                cols = df.columns
                x_col = cols[0]  # First column is usually X (Date/Category)
                
                # Find Numeric Column (Y Axis)
                nums = df.select_dtypes(include=['number']).columns
                y_col = nums[0] if len(nums) > 0 else (cols[1] if len(cols) > 1 else cols[0])
                
                # Find Hue Column (The "Legend" column, e.g., 'client_type' -> PJ/PF)
                # It is any column that is NOT x_col and NOT y_col
                hue_col = None
                remaining = [c for c in cols if c not in [x_col, y_col]]
                if remaining:
                    hue_col = remaining[0] # Use the first extra column as the grouper

                # 2. FIGURE SETUP
                fig, ax = plt.subplots(figsize=(8, 3))
                fig.patch.set_alpha(0)
                ax.set_facecolor("none")

                # Tiny Fonts & Styling
                ax.tick_params(axis='x', colors=TEXT_COLOR, labelsize=6) 
                ax.tick_params(axis='y', colors=TEXT_COLOR, labelsize=6)
                ax.xaxis.label.set_size(6)
                ax.yaxis.label.set_size(6)
                ax.xaxis.label.set_color(TEXT_COLOR)
                ax.yaxis.label.set_color(TEXT_COLOR)

                for spine in ax.spines.values():
                    spine.set_color(TEXT_COLOR)
                    spine.set_linewidth(0.5)
                ax.grid(True, linestyle='--', alpha=0.2, linewidth=0.5)

                # 3. PLOTTING LOGIC
                if chart_type == "Bar":
                    # If we have a Hue (Legend), use it to group bars
                    if hue_col:
                        sns.barplot(data=df, x=x_col, y=y_col, hue=hue_col, ax=ax, palette="crest")
                    else:
                        # Standard Bar Plot
                        if df[x_col].nunique() > 20 and pd.api.types.is_numeric_dtype(df[y_col]):
                            top = df.groupby(x_col)[y_col].sum().nlargest(20)
                            sns.barplot(x=top.values, y=top.index, ax=ax, palette="crest")
                            for i, v in enumerate(top.values):
                                ax.text(v, i, f" {v:,.0f}", va='center', fontsize=6, color=TEXT_COLOR)
                        else:
                            sns.barplot(data=df, x=x_col, y=y_col, ax=ax, palette="crest")
                    
                    if df[x_col].nunique() > 5:
                        plt.setp(ax.get_xticklabels(), rotation=45, ha='right', color=TEXT_COLOR)

                elif chart_type == "Line":
                    df_sorted = df.sort_values(by=x_col)
                    
                    # Pass 'hue' if it exists to draw multiple lines (e.g. PJ vs PF)
                    sns.lineplot(data=df_sorted, x=x_col, y=y_col, hue=hue_col, ax=ax, marker='o', palette="crest", lw=1.5, markersize=4)
                    
                    if pd.api.types.is_datetime64_any_dtype(df_sorted[x_col]):
                        locator = mdates.AutoDateLocator()
                        formatter = mdates.ConciseDateFormatter(locator)
                        ax.xaxis.set_major_locator(locator)
                        ax.xaxis.set_major_formatter(formatter)
                    plt.setp(ax.get_xticklabels(), rotation=30, ha='right', color=TEXT_COLOR)

                elif chart_type == "Boxplot":
                    is_datetime = pd.api.types.is_datetime64_any_dtype(df[x_col])
                    high_cardinality = df[x_col].nunique() > 20
                    
                    # If we have a Hue, we usually keep X to show side-by-side comparison
                    if hue_col:
                         sns.boxplot(data=df, x=x_col, y=y_col, hue=hue_col, ax=ax, palette="crest", linewidth=0.8, fliersize=2)
                         plt.setp(ax.get_xticklabels(), rotation=45, ha='right', color=TEXT_COLOR)
                    elif is_datetime or high_cardinality:
                        sns.boxplot(data=df, x=None, y=y_col, ax=ax, palette="crest", linewidth=0.8, fliersize=2)
                        st.caption(f"ℹ️ Showing overall distribution of {y_col}.")
                    else:
                        sns.boxplot(data=df, x=x_col, y=y_col, ax=ax, palette="crest", linewidth=0.8, fliersize=2)
                        plt.setp(ax.get_xticklabels(), rotation=45, ha='right', color=TEXT_COLOR)

                # 4. CUSTOM LEGEND STYLING (Crucial for Dark Mode)
                if hue_col:
                    leg = ax.get_legend()
                    if leg:
                        # Clean up legend title and text
                        leg.set_title(hue_col)
                        leg.get_title().set_color(TEXT_COLOR)
                        leg.get_title().set_fontsize(6)
                        
                        # Style the legend box to be transparent but readable
                        leg.get_frame().set_facecolor("none")
                        leg.get_frame().set_edgecolor(TEXT_COLOR)
                        leg.get_frame().set_linewidth(0.3)
                        
                        for text in leg.get_texts():
                            text.set_color(TEXT_COLOR)
                            text.set_fontsize(6)

                # Format Y Axis (Thousands)
                if len(df.select_dtypes(include=['number']).columns) > 0:
                    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:,.0f}"))
                
                plt.tight_layout()
                ax.xaxis.label.set_size(6)
                ax.yaxis.label.set_size(6)
                
                st.pyplot(fig, use_container_width=False)

            except Exception as e:
                st.warning(f"Could not render {chart_type}: {e}")