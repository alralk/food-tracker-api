"""
Dashboard page for the Food Tracker application using Streamlit.
"""
import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Food Tracker")
st.title("🍏 Food Tracker Dashboard")

if "token" not in st.session_state:
    st.session_state.token = None

if st.session_state.token is None:
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            try:
                response = requests.post(
                    f"{API_URL}/login",
                    data={"username": username, "password": password},
                    timeout=5
                )
                if response.status_code == 200:
                    st.session_state.token = response.json()["access_token"]
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            except requests.exceptions.RequestException as e:
                st.error(f"Could not connect to API: {e}")

else:
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    try:
        response = requests.get(
            f"{API_URL}/dashboard",
            headers=headers,
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Monthly Spending", f"{data['monthly_total']:.2f} euro")

            if "top_categories" in data and data["top_categories"]:
                st.subheader("Top Categories")
                chart_data = {item["category"]: item["total"] for item in data["top_categories"]}
                st.bar_chart(chart_data)

            st.subheader("Recent Food Items")
            if data.get("recent_entries"):
                st.table(data["recent_entries"])
            else:
                st.write("No recent entries found.")

            if st.sidebar.button("Logout"):
                st.session_state.token = None
                st.rerun()
        else:
            st.error("Session expired. Please login again.")
            st.session_state.token = None
            st.rerun()

    except requests.exceptions.RequestException as e:
        st.error(f"Could not connect to API: {e}")
