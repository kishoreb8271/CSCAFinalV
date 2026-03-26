import streamlit as st
import json
import pandas as pd
# FIX: Corrected import statements
import google.generativeai as genai 
from google.generativeai import types
from PIL import Image

# --- CONFIGURATION ---
# SECURITY NOTE: It is highly recommended to use st.secrets instead of hardcoding
# Go to Streamlit Cloud -> Settings -> Secrets and add: GOOGLE_API_KEY = "your_key"
GENAI_API_KEY = st.secrets.get("GOOGLE_API_KEY", "AIzaSyCH8GdET2HGA73sMnCafY8DKmGvh0pvUcA")

# FIX: Corrected initialization for the modern SDK
genai.configure(api_key=GENAI_API_KEY)

def load_data():
    try:
        with open('controls_library.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("controls_library.json not found. Please ensure the file exists.")
        return {"controls": []}

def validate_artifact_with_ai(control_question, required_desc, uploaded_file):
    try:
        img = Image.open(uploaded_file)
        prompt = f"""
        You are a Cyber Security Auditor. 
        Control Requirement: {control_question}
        Evidence Required: {required_desc}
        
        Task: Look at the attached image. Does it actually provide proof for the requirement?
        Respond ONLY in valid JSON format:
        {{
            "valid": true,
            "reason": "Short explanation",
            "confidence_score": 95
        }}
        """
        # FIX: Corrected model generation syntax for google-generativeai
        model = genai.GenerativeModel('gemini-1.5-flash') 
        response = model.generate_content(
            [prompt, img],
            generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        return {"valid": False, "reason": f"AI Error: {str(e)}", "confidence_score": 0}

# --- UI SETUP ---
st.set_page_config(page_title="Cybersecurity Control Assessment", layout="wide")
st.title("🛡️ AI-Powered Security Control Assessment")

data = load_data()

# --- SIDEBAR: INTAKE FORM ---
st.sidebar.header("Step 1: Intake Form")
risk_tier = st.sidebar.selectbox("What is the Risk Tier?", ["RT1", "RT2", "RT3", "RT4"])
data_class = st.sidebar.selectbox("Data Classification", ["Internal", "Public", "Confidential", "Highly Confidential"])
data_types = st.sidebar.multiselect("What type of data is involved?", ["PII", "PHI", "Claims", "None"])
internet_facing = st.sidebar.radio("Exposed to Internet?", ["YES", "NO"])
selected_components = st.sidebar.multiselect("Select Cloud Components", ["S3", "EC2", "EKS", "API", "Lambda"])

is_internet = True if internet_facing == "YES" else False

def filter_controls(controls, tier, components, internet, d_types):
    filtered = []
    for c in controls:
        if c['component'] in components:
            tier_match = tier in c['scenarios']['risk_tiers']
            internet_match = internet in c['scenarios']['internet_facing']
            # Simple check if any selected data type is in the control requirements
            data_match = any(dt in c['scenarios']['data_types'] for dt in d_types) if d_types else True
            if tier_match and internet_match and data_match:
                filtered.append(c)
    return filtered

# --- MAIN INTERFACE ---
if selected_components:
    relevant_controls = filter_controls(data.get('controls', []), risk_tier, selected_components, is_internet, data_types)
    st.subheader(f"Applicable Controls for {', '.join(selected_components)}")
    
    responses = {}
    
    for idx, ctrl in enumerate(relevant_controls):
        with st.expander(f"{ctrl['id']}: {ctrl['control_name']} ({ctrl['component']})"):
            st.write(f"**Question:** {ctrl['question']}")
            res = st.radio(f"Status for {ctrl['id']}", ["Select...", "YES", "NO", "NA"], key=f"res_{ctrl['id']}")
            responses[ctrl['id']] = res
            
            if res == "YES":
                st.info(f"Required Artifact: {ctrl['required_artifacts']}")
                uploaded_file = st.file_uploader(f"Upload Evidence for {ctrl['id']}", type=['png', 'jpg', 'jpeg'], key=f"file_{ctrl['id']}")
                if uploaded_file and st.button(f"🔍 AI Verify Artifact: {ctrl['id']}", key=f"verify_{ctrl['id']}"):
                    with st.spinner("AI Auditor is reviewing..."):
                        result = validate_artifact_with_ai(ctrl['question'], ctrl['required_artifacts'], uploaded_file)
                        if result['valid']:
                            st.success(f"✅ Passed: {result['reason']}")
                        else:
                            st.error(f"❌ Failed: {result['reason']}")
            
            if res == "NO":
                st.error(f"⚠️ GAP IDENTIFIED: {ctrl['guidance']}")

    # --- SUMMARY REPORT ---
    if st.button("Generate Summary Review Report"):
        st.divider()
        st.header("📋 Summary Review Report")
        
        report_data = []
        for ctrl in relevant_controls:
            status = responses.get(ctrl['id'], "Not Answered")
            
            if status == "NO":
                advisory = f"CRITICAL GAP: {ctrl['control_name']} is currently non-compliant.\nThis violates {ctrl['component']} security baselines for {risk_tier}."
                remediation = f"1. Review {ctrl['component']} configuration.\n2. Implement: {ctrl['guidance']}"
            else:
                advisory = "N/A - Control satisfied or not applicable."
                remediation = "No action required."

            report_data.append({
                "Control ID": ctrl['id'],
                "Component": ctrl['component'],
                "Status": status,
                "Advisory Notes": advisory,
                "Remediation Steps": remediation
            })
        
        df = pd.DataFrame(report_data)
        st.table(df)
else:
    st.info("Please select cloud components in the sidebar to begin.")
