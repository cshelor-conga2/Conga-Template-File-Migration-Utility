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

    template_name_string = ", ".join([f"'{name}'" for name in template_names])   

    return template_names, template_name_string

def get_cdls(sf, status_area, template_name_string):
    status_area.text("Querying ContentDocumentLinks in Source Org...")
    query = f"""
        SELECT max(ContentDocumentId), LinkedEntityId 
        FROM ContentDocumentLink 
        WHERE LinkedEntityId IN (
            SELECT Id FROM APXTConga4__Conga_Template__c WHERE APXTConga4__Name__c IN ({template_name_string})
        )
        GROUP BY LinkedEntityId
    """
    return sf.query(query)


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

# -- Welcome Screen --
st.header("Welcome to the Conga Template File Migration Utility")
st.markdown("""
    ⚙️ This utility helps you migrate Conga Template Files from one Salesforce org to another.
""")

# -- Initialize Session State Variables --
if "selected_templates" not in st.session_state:
    st.session_state.selected_templates = []

# -- Spacing --
st.markdown("<br><br>", unsafe_allow_html=True)

# -- Authentication Selection --
st.subheader("Do you want to use OAuth or Security Token authentication?")
auth_selection = st.selectbox(
    "_Choose an option to continue:_",
    options=["-- Select --", "OAuth", "Security Token"],
    index=0
)

if auth_selection == "OAuth":
    st.info("‼️ OAuth is not yet implemented in this utility. Please use Security Token for now.")

elif auth_selection == "Security Token":
    st.info("💻 Please ensure you have your Salesforce username, password, and security token ready.")
    st.info("ℹ️ If your org does not allow you to reset your security token in user settings, insert your domain into this URL: https://[SalesforceDomainHere]/_ui/system/security/ResetApiTokenEdit")     

# -- Template Record Migration Check --
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
        st.markdown("**Source Org Credentials**")
        username_a = st.text_input("Username A")
        password_a = st.text_input("Password A", type="password")
        token_a = st.text_input("Security Token A")
        domain_a = st.selectbox("Domain A - _\"login\" for dev or prod, \"test\" for sandbox_", ["login", "test"], index=0)

        st.markdown("**Target Org Credentials**")
        username_b = st.text_input("Username B")
        password_b = st.text_input("Password B", type="password")
        token_b = st.text_input("Security Token B")
        domain_b = st.selectbox("Domain B - _\"login\" for dev or prod, \"test\" for sandbox_", ["login", "test"], index=0)

        if "submitted" not in st.session_state:
            submitted = st.form_submit_button("Authenticate Salesforce Credentials")
        else:
            st.session_state.submitted = True


    # -- Processing Logic --
    if submitted:
       
        
        username_a = "chris.shelor@tinderbox.com"
        password_a = "gtx4rjx6TKJ@rap5kdc"
        token_a = "P5MIBO3cpFrC6N3PgDgqjDd2"
        domain_a = "login"

        username_b = "cshelor510@agentforce.com"
        password_b = "fwh3TUB7vqv8vkq_zqu"
        token_b = "fRm08ax01sqjnDZ5SgtF5LqRu"
        domain_b = "login"
        status_area = st.empty()
        try:
             # Authenticate only if not already in session_state
            if "sf_a" not in st.session_state or "sf_b" not in st.session_state:
                status_area.text("Authenticating Salesforce Credentials...")
                sf_a = auth_sf(username_a, password_a, token_a, domain_a)
                sf_b = auth_sf(username_b, password_b, token_b, domain_b)
                st.session_state.sf_a = sf_a
                st.session_state.sf_b = sf_b
            else:
                sf_a = st.session_state.sf_a
                sf_b = st.session_state.sf_b

            # Cache template_names and template_name_string in session_state, i.e. only run once
            if "template_names" not in st.session_state or "template_name_string" not in st.session_state:
                template_names, template_name_string = get_template_names(sf_a)
                st.session_state.template_names = template_names
                st.session_state.template_name_string = template_name_string
            else:
                template_names = st.session_state.template_names
                template_name_string = st.session_state.template_name_string

        except Exception as e:
            status_area.empty()
            st.error(f"Error: {e}")

        selected_templates = st.multiselect(
            "Select Conga Templates to Migrate",
            template_names,
            default=st.session_state.selected_templates,
            key="selected_templates")
        
     #   st.session_state.selected_templates = selected_templates
        
        if st.button("Migrate Selected Templates"):
            if st.session_state.selected_templates:
                with st.spinner("Creating Template List..."):
                    try:
                        links = get_cdls(sf_a, status_area, template_name_string)
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
    st.info("➡️ Please migrate your Conga Template records and return here when done. Thank you!")
