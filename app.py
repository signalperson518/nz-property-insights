import streamlit as st
import requests
import pandas as pd
# Use Streamlit secrets for keys
LINZ_API_KEY = st.secrets["LINZ_API_KEY"]
GOOGLE_PLACES_KEY = st.secrets["GOOGLE_PLACES_KEY"]
# Load real data CSVs
pop_df = pd.read_csv('data/2023_Census_population_change_by_SA2_5545354433051253430.csv')
income_df = pd.read_csv('data/2023_Census_totals_by_topic_for_households_by_SA2_-132143055565075773.csv')
# Load individuals data (clean wide version)
individuals_df = pd.read_csv('data/individuals_clean_wide.csv')
# Normalize main suburb name (column index 3 is the ASCII name)
pop_df['main_suburb'] = pop_df.iloc[:,3].astype(str).str.strip().str.title()
income_df['main_suburb'] = income_df.iloc[:,3].astype(str).str.strip().str.title()
individuals_df['main_suburb'] = individuals_df.iloc[:,3].astype(str).str.strip().str.title()
# Session state
if "map_data" not in st.session_state:
    st.session_state.map_data = pd.DataFrame()
if "insights" not in st.session_state:
    st.session_state.insights = None
if "show_boundaries" not in st.session_state:
    st.session_state.show_boundaries = True
st.set_page_config(page_title="NZ Property Insights AI", layout="wide")
st.title("🏠 NZ Property Insights AI")
st.markdown("**Free tool** – Aerial + elevation + flood/coastal risk + suburb demographics (2023 Census)")
address = st.text_input("Enter NZ address or place:", placeholder="e.g. 18 lanyon place, whitby or upper hutt college")
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
        # Extract main suburb
        address_parts = full_address.split(',')
        main_suburb = "Unknown"
        if len(address_parts) > 1:
            main_suburb = address_parts[1].strip().title()
        suburb = main_suburb
        # Demographics
        income = "N/A"
        pop_2023 = "N/A"
        growth = "N/A"
        lower_bachelor = "N/A"
        bachelor_higher = "N/A"
        age_le20 = "N/A"
        age_le40 = "N/A"
        age_le60 = "N/A"
        age_le65 = "N/A"
        age_65plus = "N/A"
        european_pct = "N/A"
        maori_pct = "N/A"
        pacific_pct = "N/A"
        asian_pct = "N/A"
        occupation_profile = {}
        if main_suburb != "Unknown":
            # Matches
            pop_matches = pop_df[pop_df['main_suburb'].str.contains(main_suburb, case=False, na=False)]
            income_matches = income_df[income_df['main_suburb'].str.contains(main_suburb, case=False, na=False)]
            ind_matches = individuals_df[individuals_df['main_suburb'].str.contains(main_suburb, case=False, na=False)]
            if not pop_matches.empty:
                pop_cols = [col for col in pop_matches.columns if '2023' in col and 'population' in col.lower()]
                if pop_cols:
                    pop_total = pop_matches[pop_cols[0]].sum()
                    pop_2023 = int(pop_total) if pd.notna(pop_total) else "N/A"
                growth_cols = [col for col in pop_matches.columns if 'change' in col.lower() or 'growth' in col.lower()]
                if growth_cols:
                    growth_avg = pop_matches[growth_cols[0]].mean()
                    growth = f"{growth_avg:+.1f}" if pd.notna(growth_avg) else "N/A"
            if not income_matches.empty:
                income_cols = [col for col in income_matches.columns if 'median' in col.lower() and 'income' in col.lower()]
                if income_cols:
                    income_avg = income_matches[income_cols[0]].mean()
                    income = int(income_avg) if pd.notna(income_avg) else "N/A"
            if not ind_matches.empty:
                # Clean suppressed values
                ind_matches = ind_matches.copy()
                numeric_cols = ind_matches.select_dtypes(include='number').columns
                ind_matches[numeric_cols] = ind_matches[numeric_cols].clip(lower=0).fillna(0)
                # --- Education ---
                lower_keys = ['no qualification', 'level 1', 'level 2', 'level 3', 'level 4', 'level 5', 'level 6', 'overseas secondary']
                lower_cols = [col for col in ind_matches.columns if any(k in col.lower() for k in lower_keys) and '2023' in col]
                higher_keys = ['bachelor', 'post-graduate', 'honours', 'masters', 'doctorate']
                higher_cols = [col for col in ind_matches.columns if any(k in col.lower() for k in higher_keys) and '2023' in col]
                if lower_cols and higher_cols:
                    lower_total = ind_matches[lower_cols].sum().sum()
                    higher_total = ind_matches[higher_cols].sum().sum()
                    total_stated = lower_total + higher_total
                    if total_stated > 0:
                        lower_bachelor = f"{(lower_total / total_stated * 100):.1f}%"
                        bachelor_higher = f"{(higher_total / total_stated * 100):.1f}%"
                # --- Age groups ---
                age_bin_patterns = ['0-4 years', '5-9 years', '10-14 years', '15-19 years', '20-24 years', '25-29 years', '30-34 years', '35-39 years', '40-44 years', '45-49 years', '50-54 years', '55-59 years', '60-64 years', '65-69 years', '70-74 years', '75-79 years', '80-84 years', '85 years and over']
                age_cols = [col for col in ind_matches.columns if any(p in col.lower() for p in age_bin_patterns) and '2023' in col]
                if age_cols:
                    total_age = ind_matches[age_cols].sum().sum()
                    if total_age > 0:
                        cum = 0.0
                        for p in ['0-4 years', '5-9 years', '10-14 years', '15-19 years']:
                            cols = [col for col in age_cols if p in col.lower()]
                            if cols:
                                cum += ind_matches[cols].sum().sum()
                        age_le20 = f"{(cum / total_age * 100):.1f}%"
                        for p in ['20-24 years', '25-29 years', '30-34 years', '35-39 years']:
                            cols = [col for col in age_cols if p in col.lower()]
                            if cols:
                                cum += ind_matches[cols].sum().sum()
                        age_le40 = f"{(cum / total_age * 100):.1f}%"
                        for p in ['40-44 years', '45-49 years', '50-54 years', '55-59 years']:
                            cols = [col for col in age_cols if p in col.lower()]
                            if cols:
                                cum += ind_matches[cols].sum().sum()
                        age_le60 = f"{(cum / total_age * 100):.1f}%"
                        for p in ['60-64 years']:
                            cols = [col for col in age_cols if p in col.lower()]
                            if cols:
                                cum += ind_matches[cols].sum().sum()
                        age_le65 = f"{(cum / total_age * 100):.1f}%"
                        age_65plus = f"{(100 - (cum / total_age * 100)):.1f}%"
                # --- Ethnic Diversity ---
                ethnic_total_cols = [col for col in ind_matches.columns if 'total stated' in col.lower() and 'ethnic' in col.lower() and '2023' in col]
                if ethnic_total_cols:
                    ethnic_total = ind_matches[ethnic_total_cols[0]].sum()
                    if ethnic_total > 0:
                        # European
                        european_cols = [col for col in ind_matches.columns if 'european' in col.lower() and '2023' in col and 'ethnicity' in col.lower() and 'total' not in col.lower()]
                        if european_cols:
                            european_pct = f"{(ind_matches[european_cols].sum().sum() / ethnic_total * 100):.1f}%"
                        # Māori
                        maori_cols = [col for col in ind_matches.columns if 'māori' in col.lower() and '2023' in col and 'ethnicity' in col.lower() and 'descent' not in col.lower() and 'total' not in col.lower()]
                        if maori_cols:
                            maori_pct = f"{(ind_matches[maori_cols].sum().sum() / ethnic_total * 100):.1f}%"
                        # Pacific Peoples
                        pacific_cols = [col for col in ind_matches.columns if 'pacific peoples' in col.lower() and '2023' in col and 'ethnicity' in col.lower() and 'total' not in col.lower()]
                        if pacific_cols:
                            pacific_pct = f"{(ind_matches[pacific_cols].sum().sum() / ethnic_total * 100):.1f}%"
                        # Asian
                        asian_cols = [col for col in ind_matches.columns if 'asian' in col.lower() and '2023' in col and 'ethnicity' in col.lower() and 'total' not in col.lower()]
                        if asian_cols:
                            asian_pct = f"{(ind_matches[asian_cols].sum().sum() / ethnic_total * 100):.1f}%"
                # --- Occupation Profile ---
                occ_total_cols = [col for col in ind_matches.columns if 'total stated' in col.lower() and 'occupation' in col.lower() and 'usual residence' in col.lower() and '2023' in col]
                if occ_total_cols:
                    occ_total = ind_matches[occ_total_cols[0]].sum()
                    if occ_total > 0:
                        occ_categories = {
                            'Managers': 'managers',
                            'Professionals': 'professionals',
                            'Technicians and Trades Workers': 'technicians and trades workers',
                            'Community and Personal Service Workers': 'community and personal service workers',
                            'Clerical and Administrative Workers': 'clerical and administrative workers',
                            'Sales Workers': 'sales workers',
                            'Machinery Operators and Drivers': 'machinery operators and drivers',
                            'Labourers': 'labourers'
                        }
                        occupation_profile = {}
                        for label, key in occ_categories.items():
                            occ_cols = [col for col in ind_matches.columns if key in col.lower() and '2023' in col and 'usual residence' in col.lower() and 'total' not in col.lower()]
                            if occ_cols:
                                occ_sum = ind_matches[occ_cols].sum().sum()
                                occupation_profile[label] = f"{(occ_sum / occ_total * 100):.1f}%"
        # Elevation
        elev_url = f"https://api.opentopodata.org/v1/nzdem8m?locations={lat},{lon}"
        elev_response = requests.get(elev_url)
        elev_data = elev_response.json()
        elev_value = elev_data["results"][0]["elevation"] if elev_data.get("status") == "OK" and "elevation" in elev_data["results"][0] else None
        elevation = round(elev_value, 1) if elev_value is not None else "N/A"
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
        # Resilience Score
        resilience_score = 0
        if isinstance(elevation, float):
            if elevation > 50: resilience_score += 60
            elif elevation > 30: resilience_score += 50
            elif elevation > 10: resilience_score += 30
            elif elevation > 5: resilience_score += 15
        if growth != "N/A":
            growth_float = float(growth.replace('+', '')) if isinstance(growth, str) else 0
            resilience_score += min(max(growth_float, 0) * 2, 20)
        if income != "N/A":
            resilience_score += min((income / 200000) * 20, 20)
        resilience_score = min(max(int(resilience_score), 0), 100)
        if resilience_score >= 80:
            resilience = "★★★★★ Excellent"
        elif resilience_score >= 60:
            resilience = "★★★★ Very Good"
        elif resilience_score >= 40:
            resilience = "★★★ Good"
        elif resilience_score >= 20:
            resilience = "★★ Fair"
        else:
            resilience = "★ Poor"
        # Save insights
        st.session_state.insights = {
            "short_address": short_address,
            "suburb": suburb,
            "main_suburb": main_suburb,
            "elevation": elevation,
            "risk": risk,
            "risk_color": risk_color,
            "risk_desc": risk_desc,
            "income": income,
            "pop": pop_2023,
            "growth": growth,
            "resilience_score": resilience_score,
            "resilience": resilience,
            "lower_bachelor": lower_bachelor,
            "bachelor_higher": bachelor_higher,
            "age_le20": age_le20,
            "age_le40": age_le40,
            "age_le60": age_le60,
            "age_le65": age_le65,
            "age_65plus": age_65plus,
            "european_pct": european_pct,
            "maori_pct": maori_pct,
            "pacific_pct": pacific_pct,
            "asian_pct": asian_pct,
            "occupation_profile": occupation_profile,
            "lat": lat,
            "lon": lon
        }
        st.session_state.map_data = pd.DataFrame({"lat": [lat], "lon": [lon]})
# Display results
if not st.session_state.map_data.empty and st.session_state.insights:
    i = st.session_state.insights
    st.success(f"**Found:** {i['short_address']} ({i['suburb']})")
    st.markdown(f"### Resilience Score: **{i['resilience_score']}/100**")
    st.progress(i['resilience_score'] / 100)
    with st.expander("How is Resilience Score calculated?"):
        st.write("Higher score = lower flood risk + higher suburb resilience.\n- Elevation: up to 60 points\n- Population growth: up to 20 points\n- Median income: up to 20 points")
    st.markdown(f"### Climate Resilience Rating: {i['resilience']}")
    with st.expander("How is Climate Resilience calculated?"):
        st.write("1-5 stars based on Resilience Score (80+ ★★★★★, etc.)")
    cols = st.columns(3)
    with cols[0]: st.metric("Elevation (m)", i["elevation"])
    with cols[1]: st.markdown(f"**Flood/Coastal Risk**: <span style='color:{i['risk_color']}'>{i['risk']}</span>", unsafe_allow_html=True)
    with cols[2]:
        income_display = f"${i['income']:,}" if i['income'] != "N/A" else "N/A"
        st.metric("Median Income", income_display)
    pop_display = f"{i['pop']:,} ({i['growth']}% growth)" if i['pop'] != "N/A" else "N/A"
    st.metric("Population (2023)", pop_display)
    st.info(f"**Insight**: {i['risk_desc']} in {i['suburb']} (stats for main {i['main_suburb']})")
    st.markdown("### Suburb Profile")
    tab_edu, tab_age, tab_ethnic, tab_occ = st.tabs(["📚 Education", "👥 Age", "🌍 Ethnic Diversity", "💼 Occupation"])
    with tab_edu:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Lower than Bachelor's degree", i["lower_bachelor"])
        with col2:
            st.metric("Bachelor's degree or higher", i["bachelor_higher"])
    with tab_age:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("≤20 years old", i["age_le20"])
            st.metric("≤40 years old", i["age_le40"])
            st.metric("≤60 years old", i["age_le60"])
        with col2:
            st.metric("≤65 years old", i["age_le65"])
            st.metric("65+ years old", i["age_65plus"])
        with st.expander("ℹ️ How age groups work"):
            st.write("""
            These age percentages are **cumulative** (they build on each other):
            - **≤20 years old**: % of residents aged 0–20
            - **≤40 years old**: % of residents aged 0–40 (includes everyone ≤20 + 21–40)
            - **≤60 years old**: % of residents aged 0–60 (includes everyone ≤40 + 41–60)
            - **≤65 years old**: % of residents aged 0–65 (includes everyone ≤60 + 61–65)
            - **65+ years old**: everyone 65 and older

            That's why the numbers increase as you go down – they are not separate buckets.
            
            The only math check you need: **≤65% + 65+% = 100%** ✅
            
            Example for a family suburb like Whitby:
            - Lots of kids → high ≤20%
            - Many young parents → big jump to ≤40%
            - Fewer retirees → low 65+%
            """)
    with tab_ethnic:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("% European", i.get("european_pct", "N/A"))
            st.metric("% Māori", i.get("maori_pct", "N/A"))
        with col2:
            st.metric("% Pacific Peoples", i.get("pacific_pct", "N/A"))
            st.metric("% Asian", i.get("asian_pct", "N/A"))
        st.caption("Note: Ethnic percentages may exceed 100% because people can identify with multiple ethnicities in the NZ Census.")
    with tab_occ:
        if i.get("occupation_profile", {}):
            occ_items = list(i["occupation_profile"].items())
            cols = st.columns(2)
            for idx, (label, pct) in enumerate(occ_items):
                with cols[idx % 2]:
                    st.metric(label, pct)
        else:
            st.write("N/A")
    # AI Summary – now BEFORE the map
    st.markdown("### 🤖 AI Summary")
    st.write(f"Property in {i['short_address']} ({i['suburb']}) at {i['elevation']}m – {i['risk']} flood/coastal risk.")
    st.write(f"**Resilience Score**: {i['resilience_score']}/100 | **Climate Resilience**: {i['resilience']}")
    if i['income'] != "N/A" and i['pop'] != "N/A":
        st.write(f"Main suburb {i['main_suburb']}: {i['pop']:,} residents ({i['growth']}% growth), median income ${i['income']:,}.")
    with st.expander("🤓 AI Insights & Interpretation", expanded=True):
        insights = []
        if i['bachelor_higher'] != "N/A":
            higher_pct = float(i['bachelor_higher'].replace('%', ''))
            if higher_pct >= 40:
                insights.append("🎓 **Highly educated** population – strong presence of professionals and knowledge workers.")
            elif higher_pct >= 30:
                insights.append("🎓 Well-educated community with a good share of degree holders.")
            elif higher_pct >= 20:
                insights.append("🎓 Solid education levels, typical of established suburbs.")
            else:
                insights.append("🎓 Education levels below average – may indicate more trade or practical skill-based workforce.")
        if i['age_le20'] != "N/A" and i['age_65plus'] != "N/A":
            young_pct = float(i['age_le20'].replace('%', ''))
            elderly_pct = float(i['age_65plus'].replace('%', ''))
            if young_pct >= 40:
                insights.append("👨‍👩‍👧‍👦 **Family-oriented** suburb with a high proportion of children and young families.")
            elif young_pct >= 30:
                insights.append("👨‍👩‍👧‍👦 Above-average number of children – good for schools and family amenities.")
            if elderly_pct <= 10:
                insights.append("👴 Relatively **young population** – low proportion of retirees.")
            elif elderly_pct >= 20:
                insights.append("👴 **Mature community** with higher share of retirees – may suit downsizers.")
        ethnic_note = ""
        if i.get("european_pct", "N/A") != "N/A":
            eur = float(i["european_pct"].replace('%', ''))
            if eur >= 80:
                ethnic_note = "Predominantly European with limited ethnic diversity."
            elif eur >= 70:
                ethnic_note = "Mainly European with some growing diversity."
            else:
                ethnic_note = "Culturally diverse community."
            if i.get("maori_pct", "N/A") != "N/A" and float(i["maori_pct"].replace('%', '')) >= 15:
                ethnic_note += " Significant Māori presence."
            if i.get("asian_pct", "N/A") != "N/A" and float(i["asian_pct"].replace('%', '')) >= 15:
                ethnic_note += " Strong Asian community."
            if i.get("pacific_pct", "N/A") != "N/A" and float(i["pacific_pct"].replace('%', '')) >= 10:
                ethnic_note += " Notable Pacific Peoples population."
            insights.append(f"🌍 {ethnic_note}")
        if i.get("occupation_profile", {}):
            prof_pct = float(i["occupation_profile"].get("Professionals", "0%").replace('%', ''))
            mgr_pct = float(i["occupation_profile"].get("Managers", "0%").replace('%', ''))
            trades_pct = float(i["occupation_profile"].get("Technicians and Trades Workers", "0%").replace('%', ''))
            if prof_pct + mgr_pct >= 50:
                insights.append("💼 **Professional hub** – high concentration of managers and specialists.")
            elif prof_pct + mgr_pct >= 40:
                insights.append("💼 Strong professional and managerial workforce.")
            elif trades_pct >= 20:
                insights.append("🔧 Skilled trades and practical occupations dominate.")
        if i['income'] != "N/A" and i['growth'] != "N/A":
            income_val = i['income']
            growth_val = float(i['growth'].replace('+', '')) if isinstance(i['growth'], str) else 0
            if income_val >= 100000 and growth_val > 5:
                insights.append("💰 **High-growth affluent area** – attractive for long-term investment and lifestyle.")
            elif income_val >= 90000:
                insights.append("💰 **Affluent suburb** with strong earning power.")
            elif income_val <= 60000:
                insights.append("💰 More **affordable** area – good entry point for first-home buyers or investors.")
            if growth_val > 10:
                insights.append("📈 **Rapidly growing** – increasing demand likely to support property values.")
            elif growth_val > 3:
                insights.append("📈 Positive population growth – stable and expanding community.")
            elif growth_val < 0:
                insights.append("📉 Declining population – may reflect changing demographics or outflow.")
        higher_pct = float(i['bachelor_higher'].replace('%', '')) if i['bachelor_higher'] != "N/A" else 0
        elderly_pct = float(i['age_65plus'].replace('%', '')) if i['age_65plus'] != "N/A" else 100
        prof_mgr_pct = float(i["occupation_profile"].get("Professionals", "0%").replace('%', '')) + float(i["occupation_profile"].get("Managers", "0%").replace('%', '')) if i.get("occupation_profile") else 0
        if i['resilience_score'] >= 70 and higher_pct >= 30 and prof_mgr_pct >= 40 and elderly_pct <= 15:
            insights.append("✅ **Premium family & professional suburb** – excellent long-term prospect.")
        elif i['resilience_score'] >= 50:
            insights.append("✅ **Solid, balanced community** – great mix of safety, growth, and lifestyle.")
        else:
            insights.append("⚖️ **Moderate resilience** – good affordability with some trade-offs.")
        for insight in insights:
            st.write(insight)
    # Map with boundaries (now AFTER AI Summary)
    boundaries_url = f"https://tiles.linz.govt.nz/services;key={LINZ_API_KEY}/tiles/v4/layer=50767/EPSG:3857/{{z}}/{{x}}/{{y}}.png"
    boundaries_html = f"""
    <div id="boundaries-map" style="width:100%; height:600px;"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script>
        var boundaries_map = L.map('boundaries-map').setView([{i['lat']}, {i['lon']}], 18);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{attribution: '© OpenStreetMap'}}).addTo(boundaries_map);
        L.tileLayer('{boundaries_url}', {{attribution: '© LINZ', opacity: 0.6}}).addTo(boundaries_map);
        L.marker([{i['lat']}, {i['lon']}]).addTo(boundaries_map).bindPopup('{i['short_address']}').openPopup();
    </script>
    """
    st.components.v1.html(boundaries_html, height=600)
    st.warning("Disclaimer: Public data – check official LIM/survey for accuracy.")
else:
    st.info("Enter any NZ address or place and click Analyse – results stay!")
st.caption("Free open data: LINZ + Open Topo | Built in NZ 🇳🇿")

