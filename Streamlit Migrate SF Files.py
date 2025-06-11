import streamlit as st
import tempfile
import zipfile
from simple_salesforce.api import Salesforce
import requests
import base64
import os

st.set_page_config(page_title="Conga Template File Migration Utility", layout="centered")
st.title("Conga Template File Migration Utility")

# -- Helper Functions --
def auth_sf(username, password, token, domain):
    return Salesforce(username=username, password=password, security_token=token, domain=domain)

def get_template_names(sf):
    template_names = []
    status_area.text("Getting List of Conga Templates in Source Org...")
    query = """
        SELECT APXTConga4__Name__c 
        FROM APXTConga4__Conga_Template__c
    """
    result = sf.query(query)
    
    for template in result['records']:
        template_names.append(template['APXTConga4__Name__c']) 

    return template_names

def get_cdls(sf, status_area, selected_templates):
    status_area.text("Querying ContentDocumentLinks in Source Org...")
    template_name_string = ", ".join([f"'{name}'" for name in selected_templates])   
    query = f"""
        SELECT max(ContentDocumentId), LinkedEntityId 
        FROM ContentDocumentLink 
        WHERE LinkedEntityId IN (
            SELECT Id FROM APXTConga4__Conga_Template__c WHERE APXTConga4__Name__c IN ({template_name_string})
        )
        GROUP BY LinkedEntityId
    """
    return sf.query(query)

def form_submit_status():
    st.session_state.formsubmit = True

def download_files(sf, doc_links, status_area):
    file_data = []
    status_area.text("Downloading files from Source Org...")

    for link in doc_links['records']:
        doc_id = link['expr0']
        entity_id = link['LinkedEntityId']
        version_query = f"""
            SELECT Id, Title, FileExtension, VersionData 
            FROM ContentVersion 
            WHERE ContentDocumentId = '{doc_id}' 
            ORDER BY VersionNumber DESC 
            LIMIT 1
        """
        version_result = sf.query(version_query)
        if version_result['records']:
            version = version_result['records'][0]
            file_id = version['Id']
            file_name = f"{version['Title']}.{version['FileExtension']}"
            file_url = f"{sf.base_url}sobjects/ContentVersion/{file_id}/VersionData"

            response = requests.get(file_url, headers={'Authorization': f'Bearer {sf.session_id}'})
            if response.status_code == 200:
                file_data.append({
                    'content': response.content,
                    'filename': file_name,
                    'entity_id': entity_id
                })
    return file_data

def map_orgA_to_orgB(sf_a, sf_b, orgA_ids, status_area):
    status_area.text("Mapping Source Org records to Target Org records...")
    id_list_str = ",".join([f"'{i}'" for i in orgA_ids])
    query_a = f"""
        SELECT Id, APXTConga4__Key__c 
        FROM APXTConga4__Conga_Template__c 
        WHERE Id IN ({id_list_str})
    """
    records_a = sf_a.query(query_a)['records']
    key_map = {r['Id']: r['APXTConga4__Key__c'] for r in records_a}

    records_b = sf_b.query("SELECT Id, APXTConga4__Key__c FROM APXTConga4__Conga_Template__c")['records']
    b_key_map = {r['APXTConga4__Key__c']: r['Id'] for r in records_b}

    return [b_key_map.get(key_map[i]) for i in orgA_ids]

def upload_files(sf, file_data, orgB_ids, status_area):
    status_area.text("Uploading files to Target Org...")
    for file, orgB_id in zip(file_data, orgB_ids):
        base64_str = base64.b64encode(file['content']).decode('utf-8')
        sf.ContentVersion.create({
            'Title': file['filename'].rsplit('.', 1)[0],
            'PathOnClient': file['filename'],
            'VersionData': base64_str,
            'FirstPublishLocationId': orgB_id
        })

def create_zip(files):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    with zipfile.ZipFile(tmp.name, 'w') as zipf:
        for file in files:
            zipf.writestr(file['filename'], file['content'])
    return tmp.name

def main(sf_a, sf_b, status_area, selected_templates):
    links = get_cdls(sf_a, status_area, selected_templates)
    files = download_files(sf_a, links, status_area)
    orgA_ids = [f['entity_id'] for f in files]
    orgB_ids = map_orgA_to_orgB(sf_a, sf_b, orgA_ids, status_area)

    upload_files(sf_b, files, orgB_ids, status_area)
    status_area.text("Creating zip archive of downloaded files...")
    zip_path = create_zip(files)

    with open(zip_path, "rb") as f:
        status_area.empty()
        st.success("Migration complete! If needed, you can download the files below.")
        st.download_button("Download ZIP of Migrated Files", f.read(), file_name="migrated_files.zip")

############################
# -- Welcome Screen --
st.header("Welcome to the Conga Template File Migration Utility!")
st.info("This utility helps you migrate Conga Template Files from one Salesforce org to another.", icon="📁")

# -- Initialize Session State Variables --
if "formsubmit" not in st.session_state:
    st.session_state.formsubmit = False

# -- Spacing --
st.divider()

# -- Authentication Selection --
st.subheader("Do you want to use OAuth or Security Token authentication?")
auth_selection = st.selectbox(
    "_Choose an option to continue:_",
    options=["-- Select --", "Security Token", "OAuth"],
    index=0
)

if auth_selection == "OAuth":
    st.warning("OAuth is not yet implemented in this utility. Please use Security Token for now.", icon="‼️")

elif auth_selection == "Security Token":
    st.info("Please ensure you have your Salesforce username, password, and security token ready.", icon="💻")
    st.info("If your org does not allow you to reset your security token in user settings, insert your domain into this URL: https://[SalesforceDomainHere]/_ui/system/security/ResetApiTokenEdit", icon="ℹ️")     

# -- Template Record Migration Check --
st.subheader("Have you migrated all your Conga Template records into the target org?")
migration_status = st.selectbox(
    "_Choose an option to continue:_",
    options=["-- Select --", "Yes", "No"],
    index=0
)

# -- Spacing --
st.divider()

# -- Show Credentials Form When User Confirms Template Records are in Target Org --
if migration_status == "Yes":
    # -- Show credentials form. Hide form if already submitted. --
    if not st.session_state.formsubmit:
        st.subheader("Enter Salesforce Credentials To Get Started")
        with st.form("creds_form"):
            st.markdown("**Source Org Credentials**")
            username_a = st.text_input("Username A", key="username_a")
            password_a = st.text_input("Password A", key="password_a", type="password")
            token_a = st.text_input("Security Token A", key="token_a", type="password")
            domain_a = st.selectbox("Domain A - _\"login\" for dev or prod, \"test\" for sandbox_", ["login", "test"], index=0, key="domain_a")

            st.markdown("**Target Org Credentials**")
            username_b = st.text_input("Username B", key="username_b")
            password_b = st.text_input("Password B", key="password_b", type="password")
            token_b = st.text_input("Security Token B", key="token_b", type="password")
            domain_b = st.selectbox("Domain B - _\"login\" for dev or prod, \"test\" for sandbox_", ["login", "test"], index=0, key="domain_b")

            submitted = st.form_submit_button("Authenticate Salesforce Credentials", on_click=form_submit_status)

    # -- Submit Form Data and Authenticate --
    if st.session_state.formsubmit:
        status_area = st.empty()
        try:
             # Authenticate only if not already in session_state
            if "sf_a" not in st.session_state or "sf_b" not in st.session_state:
                status_area.text("Authenticating Salesforce Credentials...")
                sf_a = auth_sf(st.session_state.username_a, st.session_state.password_a, st.session_state.token_a, st.session_state.domain_a)
                sf_b = auth_sf(st.session_state.username_b, st.session_state.password_b, st.session_state.token_b, st.session_state.domain_b)
                st.session_state.sf_a = sf_a
                st.session_state.sf_b = sf_b
            else:
                sf_a = st.session_state.sf_a
                sf_b = st.session_state.sf_b

            template_names = get_template_names(sf_a)
            st.success("✅ Templates retrieved successfully!")
           
        except Exception as e:
            status_area.empty()
            st.error(f"Error: {e}")

        # -- Determine all or some templates to migrate --
        st.subheader("Do you want to migrate all templates or select specific templates to migrate?")
        all_or_some = st.selectbox(
            "_Choose an option to continue:_",
            options=["-- Select --", "All Templates", "Select Templates"],
            index=0
        )

        # -- Migrate all templates --
        if all_or_some == "All Templates":
            if st.button("Migrate Templates"):
                with st.spinner("Migrating All Templates Files"):
                    status_area = st.empty()
                    try:
                        main(sf_a, sf_b, status_area, template_names)

                    except Exception as e:
                        status_area.empty()
                        st.error(f"Error: {e}")
        
        # -- Migrate selected templates --
        elif all_or_some == "Select Templates":
            st.divider()
            selected_templates = st.multiselect(
                "Select Conga Templates to Migrate",
                template_names,
                key="selected_templates")
            st.write("Selected Templates:", selected_templates)
            if st.button("Migrate Selected Templates"):
                    status_area = st.empty()
                    with st.spinner("Migrating Selected Templates Files"):
                        try:
                            main(sf_a, sf_b, status_area, selected_templates)

                        except Exception as e:
                            status_area.empty()
                            st.error(f"Error: {e}")

# -- Stop user if Template Records are not in target org --
elif migration_status == "No":
    st.warning("⚠️ Please migrate your Conga Template records and return here when done. Thank you!")
