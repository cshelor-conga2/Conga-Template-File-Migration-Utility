import streamlit as st
import tempfile
import zipfile
from simple_salesforce import Salesforce
import requests
import base64
import os

st.set_page_config(page_title="Conga Template File Migration Utility", layout="centered")
st.title("Conga Template File Migration Utility")

# -- Helper Functions --
def auth_sf_oauth(username, password, security_token, client_id, client_secret, domain):
    login_url = f"https://{domain}.salesforce.com/services/oauth2/token"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    payload = {
        'grant_type': 'password',
        'client_id': client_id,
        'client_secret': client_secret,
        'username': username,
        'password': password  # Append security token if required
    }
    
    # Debugging
    st.write("Sending request to:", login_url)
    st.write("Payload:", payload)
    
    response = requests.post(login_url, headers=headers, data=payload)

    # Debugging response
    st.write("Response status code:", response.status_code)
    st.write("Response content:", response.text)

    response.raise_for_status()
    access = response.json()

    return Salesforce(instance_url=access['instance_url'],
                      session_id=access['access_token'],
                      )

def get_cdls(sf, status_area):
    status_area.text("Querying ContentDocumentLinks in Org A...")
    query = """
        SELECT max(ContentDocumentId), LinkedEntityId 
        FROM ContentDocumentLink 
        WHERE LinkedEntityId IN (
            SELECT Id FROM APXTConga4__Conga_Template__c
        )
        GROUP BY LinkedEntityId
    """
    return sf.query(query)

def download_files(sf, doc_links, status_area):
    file_data = []
    status_area.text("Downloading files from Org A...")

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
    status_area.text("Mapping Org A records to Org B records...")
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
    status_area.text("Uploading files to Org B...")
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

# -- Welcome Screen --
st.header("Welcome to the Conga Template File Migration Utility")
st.markdown("""
    This utility helps you migrate Conga Template files from one Salesforce org to another.
    Please ensure you have the necessary permissions and that the target org is ready for migration.
""")

# -- Second Screen --
st.subheader("Have you migrated all your Conga Template records into the target org?")
migration_status = st.selectbox(
    "_Choose an option to continue:_",
    options=["-- Select --", "Yes", "No"],
    index=0
)

if migration_status == "Yes":
    # Show credentials form
    st.subheader("Enter Salesforce Credentials To Get Started")
    with st.form("creds_form"):
        st.markdown("**Org A Credentials**")
        username_a = st.text_input("Username A")
        password_a = st.text_input("Password A", type="password")
        token_a = st.text_input("Security Token A", value="", type="password")
        client_id_a = st.text_input("Client ID A")
        client_secret_a = st.text_input("Client Secret A")
        domain_a = st.selectbox("Domain A - _\"login\" for dev or prod, \"test\" for sandbox_", ["login", "test"], index=0)

        st.markdown("**Org B Credentials**")
        username_b = st.text_input("Username B")
        password_b = st.text_input("Password B", type="password")
        token_b = st.text_input("Security Token B", value="", type="password")
        client_id_b = st.text_input("Client ID B")
        client_secret_b = st.text_input("Client Secret B")
        domain_b = st.selectbox("Domain B - _\"login\" for dev or prod, \"test\" for sandbox_", ["login", "test"], index=0)

        submitted = st.form_submit_button("Start Migration")

    # -- Processing Logic --
    if submitted:
        status_area = st.empty()
        with st.spinner("Authenticating and processing files..."):
            try:
                status_area.text("Authenticating to Salesforce...")
                sf_a = auth_sf_oauth(username_a, password_a, token_a, client_id_a, client_secret_a, domain_a)
                sf_b = auth_sf_oauth(username_b, password_b, token_b, client_id_b, client_secret_b, domain_b)

                links = get_cdls(sf_a, status_area)
                files = download_files(sf_a, links, status_area)
                orgA_ids = [f['entity_id'] for f in files]
                orgB_ids = map_orgA_to_orgB(sf_a, sf_b, orgA_ids, status_area)

                upload_files(sf_b, files, orgB_ids, status_area)
                status_area.text("Creating zip archive of downloaded files...")
                zip_path = create_zip(files)

                with open(zip_path, "rb") as f:
                    status_area.empty()
                    st.success("Migration complete! You can download the files below.")
                    st.download_button("Download ZIP of Migrated Files", f.read(), file_name="migrated_files.zip")

            except Exception as e:
                status_area.empty()
                st.error(f"Error: {e}")

elif migration_status == "No":
    st.info("➡️ Please go migrate your Conga Template records and return here when done. Thank you!")
