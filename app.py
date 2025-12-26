import streamlit as st
import requests
import pandas as pd

# Keys from Streamlit Cloud secrets
LINZ_API_KEY = st.secrets["LINZ_API_KEY"]
GOOGLE_PLACES_KEY = st.secrets["GOOGLE_PLACES_KEY"]

# Load real data CSVs
pop_df = pd.read_csv('data/2023_Census_population_change_by_SA2_5545354433051253430.csv')
income_df = pd.read_csv('data/2023_Census_totals_by_topic_for_households_by_SA2_-132143055565075773.csv')

# Normalize main suburb name (column 4 is ASCII name)
pop_df['main_suburb'] = pop_df.iloc[:,3].astype(str).str.strip()
income_df['main_suburb'] = income_df.iloc[:,3].astype(str).str.strip()

# Session state
if "map_data" not in st.session_state:
    st.session_state.map_data = pd.DataFrame()
if "insights" not in st.session_state:
    st.session_state.insights = None

st.set_page_config(page_title="NZ Property Insights AI", layout="wide")
st.title("🏠 NZ Property Insights AI")
st.markdown("**Free tool** – Aerial + elevation + flood/coastal risk + suburb demographics (2023 Census)")

address = st.text_input("Enter NZ address or place:", placeholder="e.g. skytower or 39 Lanyon Place, Whitby")

if st.button("🔍 Analyse Property", type="primary"):
    st.session_state.map_data = pd.DataFrame()
    st.session_state.insights = None

    with st.spinner("Searching location with Google Places..."):
        places_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        params = {
            "input": address,
            "inputtype": "textquery",
            "fields": "formatted_address,geometry",
            "key": GOOGLE_PLACES_KEY,
            "locationbias": "country:nz"
        }

        response = requests.get(places_url, params=params)
        data = response.json()

        if data["status"] != "OK" or not data["candidates"]:
            st.error("Location not found – try more specific")
            st.stop()

        candidate = data["candidates"][0]
        full_address = candidate["formatted_address"]
        short_address = full_address.split(',')[0]
        lat = candidate["geometry"]["location"]["lat"]
        lon = candidate["geometry"]["location"]["lng"]

        # Extract main suburb from formatted address
        address_parts = full_address.split(',')
        main_suburb = "Unknown"
        if len(address_parts) > 1:
            main_suburb = address_parts[1].strip().title()

        # Demographics from main suburb
        income = "N/A"
        pop_2023 = "N/A"
        growth = "N/A"

        if main_suburb != "Unknown":
            pop_match = pop_df[pop_df['main_suburb'] == main_suburb]
            if not pop_match.empty:
                pop_cols = [col for col in pop_match.columns if '2023' in col and 'population' in col.lower()]
                growth_cols = [col for col in pop_match.columns if 'change' in col.lower() or 'growth' in col.lower()]
                if pop_cols:
                    pop_val = pop_match[pop_cols[0]].iloc[0]
                    pop_2023 = int(pop_val) if pd.notna(pop_val) else "N/A"
                if growth_cols:
                    growth_val = pop_match[growth_cols[0]].iloc[0]
                    growth = f"{growth_val:+.1f}" if pd.notna(growth_val) else "N/A"

            income_match = income_df[income_df['main_suburb'] == main_suburb]
            if not income_match.empty:
                income_cols = [col for col in income_match.columns if 'median' in col.lower() and 'income' in col.lower()]
                if income_cols:
                    income_val = income_match[income_cols[0]].iloc[0]
                    income = int(income_val) if pd.notna(income_val) else "N/A"

        # Elevation
        elev_url = f"https://api.opentopodata.org/v1/nzdem8m?locations={lat},{lon}"
        elev_response = requests.get(elev_url)
        elev_data = elev_response.json()
        elevation = round(elev_data["results"][0]["elevation"], 1) if elev_data["status"] == "OK" else "N/A"

        # Flood/Coastal Risk
        if isinstance(elevation, float):
            if elevation > 30:
                risk = "Low"
                risk_color = "green"
                risk_desc = "Well elevated – minimal flood/coastal risk"
            elif elevation > 10:
                risk = "Moderate"
                risk_color = "orange"
                risk_desc = "Some elevation – check local flood maps"
            else:
                risk = "High"
                risk_color = "red"
                risk_desc = "Low-lying – higher potential flood/coastal exposure"
        else:
            risk = "Unknown"
            risk_color = "gray"
            risk_desc = "Elevation data unavailable"

        # Save
        st.session_state.insights = {
            "short_address": short_address,
            "suburb": main_suburb,
            "elevation": elevation,
            "risk": risk,
            "risk_color": risk_color,
            "risk_desc": risk_desc,
            "income": income,
            "pop": pop_2023,
            "growth": growth
        }

        # Map data
        st.session_state.map_data = pd.DataFrame({
            "lat": [lat],
            "lon": [lon]
        })

# Display
if not st.session_state.map_data.empty and st.session_state.insights:
    i = st.session_state.insights

    st.success(f"**Found:** {i['short_address']} ({i['suburb']})")

    cols = st.columns(3)
    with cols[0]:
        st.metric("Elevation (m)", i["elevation"])
    with cols[1]:
        st.markdown(f"**Flood/Coastal Risk**: <span style='color:{i['risk_color']}'>{i['risk']}</span>", unsafe_allow_html=True)
    with cols[2]:
        income_display = f"${i['income']:,}" if i['income'] != "N/A" else "N/A"
        st.metric("Median Income", income_display)

    pop_display = f"{i['pop']:,} ({i['growth']}% growth)" if i['pop'] != "N/A" else "N/A"
    st.metric("Population (2023)", pop_display)

    st.info(f"**Insight**: {i['risk_desc']} in {i['suburb']} area")

    st.markdown("### 🗺️ Map & Aerial View")
    st.map(st.session_state.map_data, zoom=18)

    st.markdown("### 🤖 AI Summary")
    st.write(f"Property in {i['short_address']} ({i['suburb']}) at {i['elevation']}m – {i['risk']} flood/coastal risk.")
    if i['income'] != "N/A" and i['pop'] != "N/A":
        st.write(f"Suburb {i['suburb']}: {i['pop']:,} residents ({i['growth']}% growth), median income ${i['income']:,}.")
        st.write("Strong for risk-aware investment in growing areas.")

    st.warning("Disclaimer: Public data – check official LIM/survey for accuracy.")

else:
    st.info("Enter any NZ address or place and click Analyse – results stay!")

st.caption("Free open data: LINZ + Open Topo | v6.2 – Built in NZ 🇳🇿")
