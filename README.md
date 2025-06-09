# Conga-Template-File-Migration-Utility

A Streamlit-powered tool that helps you securely migrate Conga Template file attachments from one Salesforce org (Org A) to another (Org B), matching records via Conga Template keys.

## 🚀 Features

- 🔐 Securely log in to a target and source Salesforce org
- 📂 Automatically downloads latest versions of files attached to Conga Template records in the source org
- 🔄 Matches Conga Template records in Source Org to Conga Template records in Target ORg using the `APXTConga4__Key__c` field
- ⬆️ Uploads files into Target Org, linked to matching Conga Template records
- 🗜 Allows users to optionally download all transferred files in a `.zip` archive

## 🌐 URL
Access the app via:
https://conga-template-file-migration-utility.streamlit.app/


## 📝 Requirements
- Username, password, and security token for both Salesforce orgs
- Salesforce API access

## ⚠️ Security Note
This utility directly takes in and uses Salesforce credentials.
Credentials are not saved or shared.
Improvements are being worked on in v2 to utilize OAuth2 for logins.

# Local Use Only
## 🧱 Install Requirements
- Python 3.9 or later (only if run locally)

## 📦 Installation

Clone the repo and install dependencies:

```bash
git clone https://github.com/cshelor-conga2/Conga-Template-File-Migration-Utility
cd Conga-Template-File-Migration-Utility
pip install -r requirements.txt

