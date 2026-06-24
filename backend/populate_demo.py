#!/usr/bin/env python
import os
import sys
import json
import requests

# Set up Django environment so we can load settings from .env via Django
import django

# Add the backend directory to path if not already there
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings

def run():
    base_url = settings.LEGALSERVER_BASE_URL.rstrip('/')
    token = settings.LEGALSERVER_API_TOKEN
    
    if not base_url or not token:
        print("Error: LEGALSERVER_BASE_URL or LEGALSERVER_API_TOKEN is not set.")
        sys.exit(1)
        
    print(f"Connecting to LegalServer: {base_url}")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    # 1. Create the matter for Eleanor Vance
    print("\n1. Creating matter for Eleanor Vance...")
    matter_payload = {
        'first': 'Eleanor',
        'last': 'Vance',
        'case_disposition': 'Open',
        'legal_problem_code': '63 Private Landlord/Tenant',
        'pro_bono_opportunity_summary': (
            "Eviction defense: Tenant Eleanor Vance is facing an eviction action filed by Apex Properties LLC "
            "for non-payment of rent. Tenant has withheld rent for April, May, and June 2026 due to the landlord's "
            "ongoing failure to repair a severe ceiling leak and associated toxic black mold in her bathroom. "
            "Tenant's 7-year-old daughter has asthma, which was severely exacerbated by the mold, resulting in "
            "an emergency room visit. Tenant has saved all withheld rent and is prepared to pay it into escrow. "
            "Needs assistance drafting an Answer and Counterclaims."
        )
    }
    
    matters_url = f"{base_url}/api/v1/matters"
    res = requests.post(matters_url, headers=headers, json=matter_payload)
    if res.status_code not in (200, 201):
        print(f"Failed to create matter: {res.status_code} - {res.text}")
        sys.exit(1)
        
    matter_data = res.json()
    # Support both wrapped and unwrapped response structures
    if 'data' in matter_data:
        matter_data = matter_data['data']
        
    matter_uuid = matter_data.get('matter_uuid')
    matter_id = matter_data.get('case_id')
    print(f"Matter created successfully! UUID: {matter_uuid}, ID: {matter_id}")
    
    # 2. Assign the case to advocate Quinten Steenhuis (user id 34, uuid 4397ebbd-6db9-42d3-848e-e57643f8a890)
    # so that it shows up automatically in the synced cases for the connected advocate.
    print("\n2. Creating primary assignment to advocate Quinten Steenhuis...")
    assign_url = f"{base_url}/api/v1/matters/{matter_uuid}/assignments"
    assign_payload = {
        'type': 'Primary',
        'user': '4397ebbd-6db9-42d3-848e-e57643f8a890',
        'assigned_by': '4397ebbd-6db9-42d3-848e-e57643f8a890',
        'office': 'Main Office',
        'program': 'General'
    }
    res = requests.post(assign_url, headers=headers, json=assign_payload)
    if res.status_code not in (200, 201):
        print(f"Failed to assign matter: {res.status_code} - {res.text}")
        # Not exiting here as the case is created, we can proceed
    else:
        print("Matter successfully assigned to Quinten Steenhuis.")
        
    # 3. Create and upload the required case documents
    documents_to_upload = {
        "Summons_and_Complaint.txt": (
            "COURT OF COMMON PLEAS\n"
            "CUYAHOGA COUNTY, OHIO\n"
            "HOUSING DIVISION\n\n"
            "APEX PROPERTIES LLC,\n"
            "Plaintiff,\n\n"
            "v.\n\n"
            "ELEANOR VANCE,\n"
            "Defendant.\n\n"
            "Case No. 2026-CVG-008912\n"
            "Judge Raymond J. Pianka\n\n"
            "SUMMONS AND COMPLAINT IN EVICTION (FORCIBLE ENTRY AND DETAINER) AND FOR MONEY DAMAGES\n\n"
            "FIRST CLAIM FOR RELIEF: EVICTION (POSSESSION)\n"
            "1. Plaintiff Apex Properties LLC is the owner and landlord of the residential real property located at 1428 Elm Street, Apt 3B, Cleveland, Ohio 44113 (the \"Premises\").\n"
            "2. Defendant Eleanor Vance is a tenant at the Premises pursuant to a written lease agreement dated August 1, 2025. A copy of the lease is attached hereto as Exhibit B.\n"
            "3. Under the terms of the lease agreement, Defendant agreed to pay monthly rent in the amount of $950.00, due on the first day of each month.\n"
            "4. Defendant failed to pay monthly rent for the months of April 2026, May 2026, and June 2026.\n"
            "5. On June 1, 2026, Plaintiff served Defendant with a written 3-day notice to leave the premises in compliance with Ohio Revised Code Section 1923.04. A copy of the notice is attached hereto as Exhibit A.\n"
            "6. Defendant has failed to vacate the premises and continues to hold over and unlawfully detain possession of the Premises.\n\n"
            "SECOND CLAIM FOR RELIEF: MONEY DAMAGES\n"
            "7. Plaintiff repeats and realleges the allegations in paragraphs 1 through 6.\n"
            "8. As a result of Defendant's breach, Defendant owes Plaintiff back rent for April, May, and June 2026 in the amount of $2,850.00, plus accrued late fees of $150.00.\n"
            "9. Plaintiff is also entitled to damages for any physical damage to the Premises beyond normal wear and tear.\n\n"
            "WHEREFORE, Plaintiff prays for judgment against Defendant:\n"
            "1. For restitution and possession of the Premises.\n"
            "2. For money damages in the amount of $3,000.00 representing unpaid rent and late fees.\n"
            "3. For costs of this action and interest as allowed by law.\n\n"
            "Dated: June 12, 2026\n\n"
            "Respectfully submitted,\n"
            "/s/ Thomas J. Kutz\n"
            "Thomas J. Kutz, Esq. (OH Bar #0087123)\n"
            "Kutz & Associates, Co. LPA\n"
            "Attorney for Plaintiff\n"
        ),
        "Lease_Agreement.txt": (
            "RESIDENTIAL LEASE AGREEMENT\n\n"
            "This Residential Lease Agreement (\"Lease\") is entered into on August 1, 2025, between Apex Properties LLC (\"Landlord\") and Eleanor Vance (\"Tenant\").\n\n"
            "1. PREMISES: Landlord leases to Tenant the residential apartment located at 1428 Elm Street, Apt 3B, Cleveland, Ohio 44113 (the \"Premises\").\n"
            "2. TERM: The term of this Lease shall be for one (1) year, commencing on August 1, 2025, and terminating on July 31, 2026.\n"
            "3. RENT: Tenant agrees to pay rent in the amount of $950.00 per month. Rent is due in advance on the 1st day of each month. Payment shall be made to the Landlord/Property Manager at the office or via the electronic tenant portal.\n"
            "4. LATE FEES: If rent is not received by the 5th day of the month, a late fee of $50.00 shall be assessed.\n"
            "5. SECURITY DEPOSIT: Tenant shall deposit the sum of $950.00 as a security deposit for the faithful performance of the terms of this Lease.\n"
            "6. UTILITIES: Landlord shall pay for water and trash collection services. Tenant shall be responsible for electric and gas services.\n"
            "7. MAINTENANCE AND REPAIRS: Landlord agrees to maintain the Premises, including plumbing, heating, and structural components, in good repair and in a fit and habitable condition. Tenant shall keep the Premises clean and notify Landlord promptly of any defects or required repairs.\n"
            "8. RIGHT OF ENTRY: Landlord or Landlord's agents shall have the right to enter the Premises at reasonable times, upon 24-hour advance notice, to inspect the Premises or make necessary repairs.\n"
            "9. DEFAULT: If Tenant fails to pay rent when due or violates any other term of this Lease, Landlord may terminate this Lease and initiate eviction proceedings as permitted by law.\n\n"
            "IN WITNESS WHEREOF, the parties have executed this Lease.\n\n"
            "Landlord: Apex Properties LLC\n"
            "By: /s/ Sarah Jenkins, Property Manager\n\n"
            "Tenant: /s/ Eleanor Vance\n"
        ),
        "Notice_to_Quit.txt": (
            "3-DAY NOTICE TO LEAVE PREMISES\n"
            "Ohio Revised Code Section 1923.04\n\n"
            "Date: June 1, 2026\n\n"
            "To: Eleanor Vance\n"
            "And all other occupants\n"
            "Address: 1428 Elm Street, Apt 3B, Cleveland, Ohio 44113\n\n"
            "You are hereby notified that Apex Properties LLC, owner/landlord, requires you to leave the premises you now occupy at 1428 Elm Street, Apt 3B, Cleveland, Ohio 44113.\n\n"
            "The reason for this notice is that you have failed to comply with the terms of your lease agreement by failing to pay monthly rent for April 2026 ($950.00) and May 2026 ($950.00), totaling $1,900.00.\n\n"
            "If you do not leave the premises within three (3) days from the service of this notice, an eviction action (forcible entry and detainer) will be filed against you in court.\n\n"
            "YOU ARE BEING ASKED TO LEAVE THE PREMISES. IF YOU DO NOT LEAVE, AN EVICTION ACTION MAY BE INITIATED WITH THE COURT. IF YOU ARE IN DOUBT REGARDING YOUR LEGAL RIGHTS AND OBLIGATIONS AS A TENANT, IT IS RECOMMENDED THAT YOU SEEK LEGAL ASSISTANCE.\n\n"
            "Served by:\n"
            "Hand-delivered and posted to front door on June 1, 2026.\n\n"
            "Apex Properties LLC\n"
            "By: /s/ Sarah Jenkins\n"
            "Sarah Jenkins, Property Manager\n"
        ),
        "Intake_Notes.txt": (
            "LEGAL AID INTAKE NOTES\n"
            "Client Name: Eleanor Vance\n"
            "Date of Intake: June 15, 2026\n"
            "Interviewer: Quinten Steenhuis, Esq.\n"
            "Case Type: Eviction Defense / Private Landlord Tenant\n"
            "Adverse Party: Apex Properties LLC (represented by Thomas J. Kutz, Esq.)\n"
            "Property Manager: Sarah Jenkins\n\n"
            "FACTUAL BACKGROUND & CHRONOLOGY:\n"
            "- Tenant Eleanor Vance lives at 1428 Elm Street, Apt 3B, Cleveland, OH 44113 with her 7-year-old daughter.\n"
            "- Move-in date: August 1, 2025, under a 1-year written lease. Rent is $950.00/month.\n"
            "- Around mid-January 2026, a severe leak began dripping from the bathroom ceiling. Tenant immediately notified Sarah Jenkins (Property Manager) by text on Jan 18.\n"
            "- The leak continued, causing the bathroom drywall to degrade, crumble, and eventually fall. A large patch of black mold (approx. 3x4 feet) developed on the ceiling and wall.\n"
            "- Tenant sent additional text messages on Feb 10 and March 4, asking for repairs. Landlord sent a maintenance technician once in March, who only looked at it and left without making repairs, stating that the leak was from the upstairs apartment (also owned by Apex Properties) and they had to coordinate access.\n"
            "- On April 2, Tenant sent an email with photos of the mold and drywall damage to Sarah Jenkins, stating she would withhold rent if it wasn't fixed.\n"
            "- No repairs were made. Tenant withheld April 2026, May 2026, and June 2026 rent ($2,850 total).\n"
            "- Tenant's 7-year-old daughter has asthma. The mold exacerbated her condition, leading to an ER visit on April 28, 2026. The discharge papers list environmental allergens/mold as a likely trigger.\n"
            "- On June 1, 2026, Tenant received a 3-Day Notice to Leave.\n"
            "- On June 12, 2026, Tenant was served with a Summons and Complaint. Hearing is scheduled for July 2, 2026.\n\n"
            "LEGAL ISSUES & DEFENSES IDENTIFIED:\n"
            "1. Breach of Warranty of Habitability (O.R.C. 5321.04): Landlord failed to maintain plumbing and structural components in fit/habitable condition. Mold is a serious hazard.\n"
            "2. Retaliation (O.R.C. 5321.02): Landlord filed eviction in response to Tenant's repeated written notices of habitability defects.\n"
            "3. Rent Escrow / Withholding: Tenant did not formally escrow rent with the court under O.R.C. 5321.07 prior to withholding, but has the entire $2,850 saved in a separate account and is prepared to pay it to the court escrow immediately.\n"
            "4. Defective 3-Day Notice: Notice contains the statutory language, but we need to check if there is any issue with timing or method of service.\n\n"
            "PLAN OF ACTION:\n"
            "- File an Answer and Counterclaims (breach of warranty of habitability, breach of contract, retaliation).\n"
            "- File a motion to deposit rent with the court clerk.\n"
            "- Request a continuance of the first hearing to conduct inspection/discovery.\n"
            "- Subpoena ER records and Sarah Jenkins' communication logs.\n"
        )
    }
    
    docs_url = f"{base_url}/api/v1/documents"
    print("\n3. Uploading case documents...")
    for filename, content in documents_to_upload.items():
        print(f"Uploading {filename}...")
        files = {
            'file': (filename, content, 'text/plain')
        }
        metadata_payload = {
            'metadata': json.dumps({
                'matter_uuid': matter_uuid,
                'filename': filename
            })
        }
        res = requests.post(docs_url, headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'}, files=files, data=metadata_payload)
        if res.status_code == 200:
            print(f"Uploaded {filename} successfully! Document UUID: {res.json().get('uuid')}")
        else:
            print(f"Failed to upload {filename}: {res.status_code} - {res.text}")

    # 4. Create the case notes on LegalServer
    print("\n4. Creating intake notes on LegalServer...")
    notes_url = f"{base_url}/api/v1/notes"
    notes_payload = {
        'module': 'matter',
        'module_uuid': matter_uuid,
        'subject': 'Intake Notes: Eleanor Vance',
        'body': documents_to_upload["Intake_Notes.txt"],
        'note_type': 'Generated Documents'
    }
    res = requests.post(notes_url, headers=headers, json=notes_payload)
    if res.status_code in (200, 201):
        print(f"Intake Notes note created successfully! Note UUID: {res.json().get('data', {}).get('note_uuid')}")
    else:
        print(f"Failed to create intake notes note: {res.status_code} - {res.text}")
        
    print("\nDone populating realistic case details on the remote LegalServer site!")
    print("Now you can reload the Lemma-Demo site or run sync inside Django to see the new case.")

if __name__ == "__main__":
    run()
