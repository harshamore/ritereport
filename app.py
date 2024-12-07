import streamlit as st
import pandas as pd
import json
import os
from fpdf import FPDF
from io import BytesIO

st.set_page_config(page_title="Financial Reporting MVP", layout="centered")

st.title("Automated Financial Reporting (MVP)")

MAPPING_FILE = "mapping.json"

# Load existing mappings if available
if "chart_mapping" not in st.session_state:
    if os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, "r") as f:
            st.session_state.chart_mapping = json.load(f)
    else:
        st.session_state.chart_mapping = {}

# Define more granular categories
categories = [
    "Current Assets",
    "Long-term Assets",
    "Current Liabilities",
    "Long-term Liabilities",
    "Equity",
    "Revenue",
    "Operating Expenses",
    "Non-Operating Expenses"
]

uploaded_file = st.file_uploader("Upload a CSV file of your trial balance", type=["csv"])

def save_mappings():
    """Save the current chart mappings to a JSON file."""
    with open(MAPPING_FILE, "w") as f:
        json.dump(st.session_state.chart_mapping, f)

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    required_columns = {"Account Name", "Debit", "Credit"}
    if not required_columns.issubset(df.columns):
        st.error("The CSV must contain columns: Account Name, Debit, Credit")
    else:
        # Basic validation: Check if total debits = total credits
        total_debits = df["Debit"].sum()
        total_credits = df["Credit"].sum()
        if abs(total_debits - total_credits) > 1e-6:
            st.warning(f"Total Debits (${total_debits:,.2f}) do not equal Total Credits (${total_credits:,.2f}). Please check your data.")
        else:
            st.success("Trial balance debits and credits are balanced.")

        st.subheader("Uploaded Trial Balance")
        st.dataframe(df)

        # Attempt to auto-map if account already known
        account_names = df["Account Name"].unique()

        st.subheader("Map Accounts to Categories")
        with st.form("mapping_form"):
            for account in account_names:
                default_cat = st.session_state.chart_mapping.get(account, categories[0])
                cat = st.selectbox(f"{account}:", categories, index=categories.index(default_cat) if default_cat in categories else 0)
                st.session_state.chart_mapping[account] = cat
            submitted = st.form_submit_button("Save Mapping")

        if submitted:
            save_mappings()
            st.success("Mappings saved.")

        if st.button("Generate Financial Statements"):
            # Apply the mapping
            df["Category"] = df["Account Name"].map(st.session_state.chart_mapping)

            # Convert Debit/Credit into a single signed value (Debit positive, Credit negative)
            df["Amount"] = df["Debit"] - df["Credit"]

            # Aggregate by category
            cat_sums = df.groupby("Category")["Amount"].sum()

            # Summarize categories for statements
            # Balance Sheet categories:
            total_current_assets = cat_sums.get("Current Assets", 0)
            total_long_assets = cat_sums.get("Long-term Assets", 0)
            total_assets = total_current_assets + total_long_assets

            total_current_liab = cat_sums.get("Current Liabilities", 0)
            total_long_liab = cat_sums.get("Long-term Liabilities", 0)
            total_liabilities = total_current_liab + total_long_liab
            total_equity = cat_sums.get("Equity", 0)

            # Income Statement categories:
            total_revenue = cat_sums.get("Revenue", 0)
            total_op_exp = cat_sums.get("Operating Expenses", 0)
            total_non_op_exp = cat_sums.get("Non-Operating Expenses", 0)
            total_expenses = total_op_exp + total_non_op_exp
            net_income = total_revenue - total_expenses

            # Display Income Statement
            st.subheader("Income Statement")
            st.write("**Revenue**:", f"${total_revenue:,.2f}")
            st.write("**Operating Expenses**:", f"${total_op_exp:,.2f}")
            st.write("**Non-Operating Expenses**:", f"${total_non_op_exp:,.2f}")
            st.write("---")
            st.write("**Net Income**:", f"${net_income:,.2f}")

            # Display Balance Sheet
            st.subheader("Balance Sheet")
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Assets**")
                st.write("Current Assets:", f"${total_current_assets:,.2f}")
                st.write("Long-term Assets:", f"${total_long_assets:,.2f}")
                st.write("---")
                st.write("Total Assets:", f"${total_assets:,.2f}")
            with col2:
                st.write("**Liabilities & Equity**")
                st.write("Current Liabilities:", f"${total_current_liab:,.2f}")
                st.write("Long-term Liabilities:", f"${total_long_liab:,.2f}")
                st.write("Equity:", f"${total_equity:,.2f}")
                st.write("---")
                st.write("Total L&E:", f"${(total_liabilities + total_equity):,.2f}")

            # Check if balance sheet balances
            if abs(total_assets - (total_liabilities + total_equity)) < 1e-6:
                st.success("Balance Sheet is balanced.")
            else:
                st.warning("Balance Sheet does not balance. Check your mappings or data.")

            # Prepare dataframes for export
            income_statement_df = pd.DataFrame({
                "Description": ["Revenue", "Operating Expenses", "Non-Operating Expenses", "Net Income"],
                "Amount": [total_revenue, total_op_exp, total_non_op_exp, net_income]
            })

            balance_sheet_df = pd.DataFrame({
                "Description": ["Current Assets", "Long-term Assets", "Total Assets", 
                                "Current Liabilities", "Long-term Liabilities", "Equity", "Total Liabilities & Equity"],
                "Amount": [total_current_assets, total_long_assets, total_assets,
                           total_current_liab, total_long_liab, total_equity, total_liabilities + total_equity]
            })

            # CSV Export
            st.subheader("Export Reports")
            income_csv = income_statement_df.to_csv(index=False).encode('utf-8')
            bs_csv = balance_sheet_df.to_csv(index=False).encode('utf-8')

            st.download_button(
                label="Download Income Statement (CSV)",
                data=income_csv,
                file_name="income_statement.csv",
                mime="text/csv"
            )

            st.download_button(
                label="Download Balance Sheet (CSV)",
                data=bs_csv,
                file_name="balance_sheet.csv",
                mime="text/csv"
            )

            # PDF Export
            def create_pdf(income_df, bs_df):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, "Income Statement", ln=True)
                pdf.set_font("Arial", "", 12)
                for _, row in income_df.iterrows():
                    pdf.cell(0, 10, f"{row['Description']}: ${row['Amount']:,.2f}", ln=True)

                pdf.ln(10)
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, "Balance Sheet", ln=True)
                pdf.set_font("Arial", "", 12)
                for _, row in bs_df.iterrows():
                    pdf.cell(0, 10, f"{row['Description']}: ${row['Amount']:,.2f}", ln=True)

                # Return PDF as bytes
                pdf_output = BytesIO()
                pdf.output(pdf_output, "F")
                pdf_output.seek(0)
                return pdf_output

            pdf_bytes = create_pdf(income_statement_df, balance_sheet_df)
            st.download_button(
                label="Download Reports (PDF)",
                data=pdf_bytes,
                file_name="financial_reports.pdf",
                mime="application/pdf"
            )
