# Conga-Template-File-Migration-Utility

A Streamlit-powered tool that helps you securely migrate Conga Template file attachments from one Salesforce org (Org A) to another (Org B), matching records via template keys.

## 🚀 Features

- 🔐 Secure login for two Salesforce orgs
- 📂 Automatically finds files linked to Conga Templates in Org A
- ⬇️ Downloads latest file versions
- 🔄 Matches records in Org B using `APXTConga4__Key__c`
- ⬆️ Uploads files into Org B, linked to matching templates
- 🗜 Option to download all transferred files in a `.zip` archive

## 🧱 Requirements

- Python 3.9 or later
- Salesforce credentials for both orgs with API access

## ⚠️ Security Note
This utility directly takes in and uses Salesforce credentials.
Credentials are not saved or shared.
For production use, consider adding OAuth2 or environment-based secrets management.

## 📦 Installation

Clone the repo and install dependencies:

```bash
git clone https://github.com/yourusername/conga-file-migrator.git
cd conga-file-migrator
pip install -r requirements.txt

