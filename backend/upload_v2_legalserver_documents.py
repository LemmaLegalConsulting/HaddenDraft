#!/usr/bin/env python
import os
import sys
import json
import requests
import django

# Set up Django environment
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings
from apps.matters.models import Matter
from apps.sources.connectors.legalserver import LegalServerClient

# Comprehensive dictionary of realistic case documents for LegalServer v2 API upload
CASE_DOCUMENTS_V2 = {
    "Eleanor Vance": [
        ("Summons_and_Complaint_Eleanor_Vance.txt", (
            "COURT OF COMMON PLEAS\nCUYAHOGA COUNTY, OHIO\nHOUSING DIVISION\n\n"
            "APEX PROPERTIES LLC, Plaintiff, v. ELEANOR VANCE, Defendant.\n"
            "Case No. 2026-CVG-008912\n\n"
            "COMPLAINT IN EVICTION AND FOR MONEY DAMAGES\n"
            "1. Plaintiff Apex Properties LLC is landlord of 1428 Elm Street, Apt 3B, Cleveland, OH 44113.\n"
            "2. Defendant failed to pay monthly rent ($950.00) for April, May, and June 2026.\n"
            "3. 3-day notice served June 1, 2026. Back rent owed: $2,850.00 plus $150 late fees."
        )),
        ("Lease_Agreement_Eleanor_Vance.txt", (
            "RESIDENTIAL LEASE AGREEMENT\n"
            "Landlord: Apex Properties LLC | Tenant: Eleanor Vance\n"
            "Premises: 1428 Elm Street, Apt 3B, Cleveland, OH 44113\n"
            "Rent: $950.00/month. Term: August 1, 2025 - July 31, 2026.\n"
            "Maintenance: Landlord shall maintain plumbing and structural components in good repair."
        )),
        ("Notice_to_Quit_Eleanor_Vance.txt", (
            "3-DAY NOTICE TO LEAVE PREMISES (O.R.C. 1923.04)\n"
            "Date: June 1, 2026\nTo: Eleanor Vance, 1428 Elm Street, Apt 3B, Cleveland, OH 44113\n"
            "Reason: Unpaid rent for April and May 2026 totaling $1,900.00."
        )),
        ("Intake_Notes_Eleanor_Vance.txt", (
            "LEGAL AID INTAKE NOTES\nClient: Eleanor Vance | Date: June 15, 2026\n"
            "Bathroom ceiling leak reported Jan 18. Black mold 3x4ft developed. Child ER visit April 28 for asthma.\n"
            "Rent withheld saved in escrow account ($2,850 total). Defense under ORC 5321.04 & 5321.02 retaliation."
        ))
    ],

    "Marcus Vance": [
        ("Summons_and_Complaint_Marcus_Vance.txt", (
            "CLEVELAND MUNICIPAL COURT - HOUSING DIVISION\n"
            "METRO HOUSING RENTALS LLC v. MARCUS VANCE\nCase No. 2026-CVG-010422\n\n"
            "COMPLAINT FOR EVICTION AND MONEY DAMAGES\n"
            "1. Landlord owns 3204 Superior Ave, Apt 12, Cleveland, OH 44114.\n"
            "2. Defendant Marcus Vance is in default of monthly tenant portion of rent ($150/mo) and claims $1,800 total balance.\n"
            "3. 3-day notice served May 28, 2026."
        )),
        ("HAP_Contract_and_Voucher_CMHA.txt", (
            "HOUSING ASSISTANCE PAYMENTS (HAP) CONTRACT - SECTION 8 VOUCHER PROGRAM\n"
            "Housing Authority: Cuyahoga Metropolitan Housing Authority (CMHA)\n"
            "Tenant: Marcus Vance | Landlord: Metro Housing Rentals LLC\n"
            "Contract Rent: $900.00 | Housing Assistance Payment (CMHA): $750.00 | Tenant Rent Share: $150.00."
        )),
        ("Tenant_Rent_Ledger_Extract.txt", (
            "METRO HOUSING RENTALS LLC - TENANT ACCOUNT STATEMENT\n"
            "Account: Marcus Vance - 3204 Superior Ave #12\n"
            "Jan 2026: Rent $900 | CMHA paid $750 | Tenant paid $150 | Bal $0\n"
            "Feb-Apr 2026: CMHA electronic payment failed due to vendor bank update; landlord charged full $900/mo to tenant."
        )),
        ("Legal_Aid_Intake_Marcus_Vance.txt", (
            "INTAKE SUMMARY - MARCUS VANCE\n"
            "Client paid his $150 share every month via money order. CMHA missed 2 payments during portal transition.\n"
            "Landlord cannot evict tenant for CMHA's delayed subsidy under Federal HAP contract regulations & HUD rules."
        ))
    ],

    "Linda Thompson": [
        ("Summons_and_Complaint_Linda_Thompson.txt", (
            "CLEVELAND HEIGHTS MUNICIPAL COURT\n"
            "EUCLID HEIGHTS APARTMENTS LLC v. LINDA THOMPSON\nCase No. 2026-CVG-004119\n\n"
            "COMPLAINT FOR FORCIBLE ENTRY AND DETAINER\n"
            "Premises: 2195 Coventry Rd, Apt 4C, Cleveland Heights, OH 44118.\n"
            "Claim: Unpaid rent for April and May 2026 ($1,700 balance)."
        )),
        ("Partial_Rent_Payment_Receipt.txt", (
            "EUCLID HEIGHTS APARTMENTS - RECEIPT OF PAYMENT\n"
            "Date: June 5, 2026 (4 days after 3-day notice served on June 1, 2026)\n"
            "Received from Linda Thompson: $400.00 via cashier's check #88412.\n"
            "Accepted and deposited by Property Manager without reservation."
        )),
        ("Hospital_ER_Discharge_Report.txt", (
            "UNIVERSITY HOSPITALS RAINBOW BABIES & CHILDREN'S HOSPITAL\n"
            "Patient: Jayden Thompson (Age 5) | Mother: Linda Thompson\n"
            "Admission Date: May 12, 2026 | Diagnosis: Acute severe asthma exacerbation.\n"
            "Environmental Notes: Triggered by severe indoor mold spore exposure in bathroom."
        )),
        ("Intake_Notes_Linda_Thompson.txt", (
            "LEGAL AID INTAKE NOTES - LINDA THOMPSON\n"
            "Defenses: 1. Waiver of 3-Day Notice under Ohio law by accepting $400 partial rent after notice.\n"
            "2. Breach of Warranty of Habitability (O.R.C. 5321.04) due to toxic mold & ceiling collapse."
        ))
    ],

    "Robert Garcia": [
        ("Summons_and_Complaint_Robert_Garcia.txt", (
            "LAKEWOOD MUNICIPAL COURT\nLAKEWOOD PROPERTY GROUP LLC v. ROBERT GARCIA\n"
            "Case No. 2026-CVG-002180\n"
            "Filed: June 12, 2026 for nonpayment of $1,100 June rent at 14500 Detroit Ave #602."
        )),
        ("Three_Day_Notice_to_Leave.txt", (
            "3-DAY NOTICE TO LEAVE PREMISES\nServed: Wednesday, June 10, 2026 at 4:00 PM.\n"
            "Note: Landlord filed court action Friday, June 12, violating 3 full business days rule."
        )),
        ("Physician_Verification_Mobility_Impairment.txt", (
            "METROHEALTH MEDICAL CENTER - PHYSICIAN STATEMENT\n"
            "Patient: Robert Garcia (DOB: 03/14/1954)\n"
            "Diagnosis: Severe osteoarthritis, wheelchair dependent. Requires elevator access and home care."
        )),
        ("Intake_Notes_Robert_Garcia.txt", (
            "LEGAL AID INTAKE NOTES - ROBERT GARCIA\n"
            "Motion to Dismiss for lack of subject matter jurisdiction: 3-day notice served June 10, suit filed June 12.\n"
            "Under Ohio law (ORC 1923.04), 3 full business days must elapse before complaint filing."
        ))
    ],

    "James Miller": [
        ("Summons_and_Complaint_James_Miller.txt", (
            "PARMA MUNICIPAL COURT\nPARMA LANDLORDS LLC v. JAMES MILLER\nCase No. 2026-CVG-005120\n"
            "Premises: 5812 Ridge Rd #104, Parma, OH 44129. Amount claimed: $1,900.00."
        )),
        ("Rental_Assistance_Application_Confirmation.txt", (
            "CUYAHOGA COUNTY HOUSING STABILITY FUND\n"
            "Applicant: James Miller | Status: APPROVED for $2,400.00.\n"
            "Disbursement check scheduled to Parma Landlords LLC within 10 business days."
        )),
        ("Intake_Notes_James_Miller.txt", (
            "INTAKE NOTES - JAMES MILLER\n"
            "File Motion for Continuance to allow rental assistance check to process. Landlord open to dismissal upon receipt."
        ))
    ],

    "Sarah Jenkins": [
        ("Summons_and_Complaint_Sarah_Jenkins.txt", (
            "CLEVELAND HEIGHTS MUNICIPAL COURT\nHEIGHTS REALTY LLC v. SARAH JENKINS\nCase No. 2026-CVG-003910\n"
            "Action for holdover possession of 3421 Mayfield Rd #2B."
        )),
        ("City_Housing_Inspection_Report.txt", (
            "CLEVELAND HEIGHTS BUILDING DEPARTMENT\n"
            "Inspection Date: February 14, 2026 | Premises: 3421 Mayfield Rd #2B\n"
            "Violation Cited: Heating unit failing to maintain 68 deg F minimum temperature requirement (ORC 5321.04)."
        )),
        ("Intake_Notes_Sarah_Jenkins.txt", (
            "INTAKE NOTES - SARAH JENKINS\n"
            "Retaliatory Eviction Defense under ORC 5321.02. Non-renewal notice was served 6 days after building inspection."
        ))
    ],

    "Charles Davis": [
        ("Summons_and_Complaint_Charles_Davis.txt", (
            "SHAKER HEIGHTS MUNICIPAL COURT\nSHAKER SQUARE APARTMENTS LLC v. CHARLES DAVIS\n"
            "Case No. 2026-CVG-001920\nUnpaid rent for May/June 2026 ($1,650 balance)."
        )),
        ("Intake_Notes_Charles_Davis.txt", (
            "INTAKE NOTES - CHARLES DAVIS\nClient started new job June 1. Seeking agreed consent judgment with stay of execution."
        ))
    ],

    "Donna Evans": [
        ("Summons_and_Complaint_Donna_Evans.txt", (
            "EAST CLEVELAND MUNICIPAL COURT\nEAST CLEVELAND PROPERTIES LLC v. DONNA EVANS\n"
            "Case No. 2026-CVG-007140\nAlleged lease violation: Unauthorized guest over 14 days."
        )),
        ("Guest_Caregiver_Statement.txt", (
            "STATEMENT OF MARY EVANS\n"
            "I am Donna Evans' sister. I stayed at 13405 Euclid Ave #510 for 5 days following her knee surgery to assist her."
        )),
        ("Intake_Notes_Donna_Evans.txt", (
            "INTAKE NOTES - DONNA EVANS\nDefenses: 1. No breach of lease (temporary medical guest). 2. Defective summons (illegible date)."
        ))
    ],

    "Thomas Wilson": [
        ("Summons_and_Complaint_Thomas_Wilson.txt", (
            "GARFIELD HEIGHTS MUNICIPAL COURT\nTURNEY ROAD MANAGEMENT LLC v. THOMAS WILSON\n"
            "Case No. 2026-CVG-003110\nEviction for alleged waste and property damage."
        )),
        ("Police_Incident_Report_Garfield_Heights.txt", (
            "GARFIELD HEIGHTS POLICE DEPARTMENT - INCIDENT REPORT\n"
            "Report No. 26-09812 | Incident: Attempted Burglary / Vandalism\n"
            "Location: 4810 Turney Rd #14 | Reporting Party: Thomas Wilson\n"
            "Officer Notes: Unknown suspect attempted forced entry causing outer window crack and lock deformation."
        )),
        ("Intake_Notes_Thomas_Wilson.txt", (
            "INTAKE NOTES - THOMAS WILSON\nTenant is victim of crime; not liable for third-party criminal damage under lease."
        ))
    ],

    "Patricia Taylor": [
        ("Summons_and_Complaint_Patricia_Taylor.txt", (
            "BEREA MUNICIPAL COURT\nSTRONGSVILLE APARTMENTS LLC v. PATRICIA TAYLOR\n"
            "Case No. 2026-CVG-004810\nComplaint signed: /s/ Brenda Vance, Property Manager (non-attorney)."
        )),
        ("Intake_Notes_Patricia_Taylor.txt", (
            "INTAKE NOTES - PATRICIA TAYLOR\n"
            "Motion to Dismiss for Unauthorized Practice of Law (UPL) as complaint was filed by non-lawyer for corporate LLC."
        ))
    ],

    "Christopher Anderson": [
        ("Summons_and_Complaint_Christopher_Anderson.txt", (
            "ROCKY RIVER MUNICIPAL COURT\nWESTLAKE VILLAGE APARTMENTS LLC v. CHRISTOPHER ANDERSON\n"
            "Case No. 2026-CVG-001840\nClaim: Lease termination for alleged noise disturbance."
        )),
        ("Gas_Company_Inspection_Report.txt", (
            "DOMINION ENERGY OHIO - EMERGENCY SERVICE CALL LOG\n"
            "Date: May 19, 2026 | Address: 26900 Detroit Rd #115\n"
            "Technician Findings: Active gas leak detected at stove supply line; gas shut off pending landlord repair."
        )),
        ("Intake_Notes_Christopher_Anderson.txt", (
            "INTAKE NOTES - CHRISTOPHER ANDERSON\nRetaliation defense under ORC 5321.02 following gas leak report."
        ))
    ],

    "Samuel Green": [
        ("Medicaid_Notice_of_Action.txt", (
            "OHIO DEPARTMENT OF MEDICAID - NOTICE OF ACTION\n"
            "To: Samuel Green | Date: May 10, 2026\n"
            "Notice: Termination of PASSPORT Waiver Personal Care Aide Hours effective June 1, 2026."
        )),
        ("Treating_Physician_Level_of_Care_Assessment.txt", (
            "CLEVELAND CLINIC - GERIATRIC MEDICINE EVALUATION\n"
            "Patient: Samuel Green (Age 78)\n"
            "Assessment: Patient requires assistance with 4 ADLs (bathing, dressing, mobility, medication management)."
        ))
    ],

    "Maria Santos": [
        ("Divorce_Complaint_Santos.txt", (
            "CUYAHOGA COUNTY COMMON PLEAS COURT - DOMESTIC RELATIONS DIVISION\n"
            "MARIA SANTOS v. CARLOS SANTOS\nCase No. DR-26-381902\n"
            "Complaint for Divorce, Custody, and Equitable Division of Marital Property."
        )),
        ("Proposed_Parenting_Plan.txt", (
            "PROPOSED SHARED PARENTING PLAN\nMother Maria Santos proposes primary residential parent designation."
        ))
    ],

    "David Kowalski": [
        ("Creditor_Balance_Sheet.txt", (
            "SCHEDULE OF UNSECURED CREDITORS - DAVID KOWALSKI\n"
            "1. Cleveland Clinic Health System: $32,450.00 (Medical)\n"
            "2. Capital One Bank: $12,800.00 (Credit Card)"
        )),
        ("Chapter_7_Petition_Draft.txt", (
            "UNITED STATES BANKRUPTCY COURT - NORTHERN DISTRICT OF OHIO\n"
            "In re: DAVID KOWALSKI, Debtor. Chapter 7 Voluntary Petition."
        ))
    ],

    "Aisha Jackson": [
        ("DUI_Arrest_Record_Excerpt.txt", (
            "CLEVELAND MUNICIPAL COURT - CRIMINAL DIVISION\n"
            "State of Ohio v. Marcus Jackson | Case No. 2026-TRC-011204\n"
            "Charge: OVI / Operating Vehicle Impaired."
        )),
        ("Motion_for_Supervised_Visitation.txt", (
            "CUYAHOGA COUNTY JUVENILE COURT\nAISHA JACKSON v. MARCUS JACKSON\n"
            "Motion to Modify Allocation of Parental Rights and Order Supervised Visitation."
        ))
    ],

    "Carlos Mendez": [
        ("Overtime_Hours_Log.txt", (
            "CARLOS MENDEZ - WEEKLY HOURS WORKED LOG\n"
            "Avg hours worked: 54 hours/week. Paid flat cash rate without 1.5x overtime multiplier."
        )),
        ("FLSA_Wage_Demand_Letter.txt", (
            "NOTICE OF WAGE CLAIM AND DEMAND FOR PAYMENT\n"
            "To: El Sol Restaurant & Grill LLC / Ricardo Lopez\n"
            "Demand for unpaid overtime compensation and liquidated damages under 29 U.S.C. 207."
        ))
    ],

    "Brenda Taylor": [
        ("SSA_Reconsideration_Denial.txt", (
            "SOCIAL SECURITY ADMINISTRATION - NOTICE OF RECONSIDERATION DENIAL\n"
            "Claimant: Brenda Taylor | SSN: XXX-XX-4819\nClaim for Supplemental Security Income."
        )),
        ("MRI_Spine_Medical_Report.txt", (
            "METROHEALTH NEUROLOGY - MRI LUMBAR SPINE\n"
            "Findings: Severe spinal stenosis L4-L5 with nerve root compression."
        ))
    ],

    "Karen Novak": [
        ("Resignation_Email.txt", (
            "From: Karen Novak To: HR Midwest Logistics\n"
            "Subject: Resignation due to unaddressed safety hazards on forklift loading dock."
        )),
        ("ODJFS_Unemployment_Appeal.txt", (
            "OHIO DEPT OF JOB & FAMILY SERVICES - APPEAL TO REVIEW COMMISSION\n"
            "Claimant Karen Novak appeals initial disallowance of benefits."
        ))
    ],

    "Olivia Martinez": [
        ("IEP_Speech_Evaluation_Excerpt.txt", (
            "CLEVELAND METROPOLITAN SCHOOL DISTRICT - IEP EVALUATION REPORT\n"
            "Student: Mateo Martinez (Age 8) | Diagnosis: ASD Level 2."
        )),
        ("Independent_Speech_Therapy_Assessment.txt", (
            "CLEVELAND SPEECH & HEARING CENTER\n"
            "Recommends minimum 3 hours/week direct speech-language pathology services."
        ))
    ],

    "Evelyn Carter": [
        ("Will_Intake_Information.txt", (
            "ESTATE PLANNING INTAKE - EVELYN CARTER\n"
            "Asset: Residence at 14208 Kinsman Rd, Cleveland OH. Beneficiary: Granddaughter Maya Carter."
        )),
        ("Last_Will_and_Testament_Draft.txt", (
            "LAST WILL AND TESTAMENT OF EVELYN CARTER\n"
            "I, Evelyn Carter, declare this to be my Last Will and Testament..."
        ))
    ],

    "Daniel O'Connor": [
        ("Medicare_Part_D_Denial_Notice.txt", (
            "HUMANA MEDICARE PART D - NOTICE OF DENIAL OF MEDICARE PRESCRIPTION DRUG COVERAGE\n"
            "Enrollee: Daniel O'Connor | Drug: Entresto 97/103mg | Reason: Non-formulary."
        )),
        ("Cardiologist_Prior_Auth_Statement.txt", (
            "CLEVELAND CLINIC HEART & VASCULAR INSTITUTE\n"
            "Re: Daniel O'Connor | Physician statement confirming formulary alternatives (ACE inhibitors) caused severe angioedema."
        ))
    ]
}


def run_v2_uploads():
    base_url = settings.LEGALSERVER_BASE_URL.rstrip('/')
    token = settings.LEGALSERVER_API_TOKEN
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }

    client = LegalServerClient()
    matters = client.search_matters(limit=100)
    print(f"Loaded {len(matters)} matters from LegalServer.")

    # 1. Clean up local shadowed documents from Django Matter records
    print("\n1. Cleaning up local shadowed file uploads from Django Matter raw_payload...")
    cleaned_count = 0
    for matter in Matter.objects.all():
        if matter.raw_payload:
            raw = dict(matter.raw_payload)
            changed = False
            if "documents" in raw:
                del raw["documents"]
                changed = True
            if "case_notes" in raw:
                del raw["case_notes"]
                changed = True
            if changed:
                matter.raw_payload = raw
                matter.save(update_fields=["raw_payload"])
                cleaned_count += 1
    print(f"Cleaned local raw_payload shadow files from {cleaned_count} Django Matter records.")

    # 2. Upload documents via LegalServer v2 API (/api/v2/documents)
    print("\n2. Uploading case documents directly to LegalServer via v2 API (`POST /api/v2/documents`)...")
    v2_url = f"{base_url}/api/v2/documents"

    for m in matters:
        muuid = m.get('matter_uuid')
        db_id = m.get('case_id') or m.get('database_id') or m.get('id')
        mno = m.get('matter_identification_number') or m.get('case_number')
        first = m.get('first', '')
        last = m.get('last', '')
        name = f"{first} {last}".strip() or m.get('case_title', '')

        # Find matching documents in CASE_DOCUMENTS_V2
        matching_docs = None
        for key, docs_list in CASE_DOCUMENTS_V2.items():
            if key.casefold() in name.casefold() or name.casefold() in key.casefold():
                matching_docs = docs_list
                break

        if not matching_docs:
            continue

        # Check existing documents on LegalServer to avoid duplicates
        existing_docs = client.get_matter_documents(muuid or db_id)
        existing_names = {d.get('name') or d.get('title') for d in existing_docs}

        print(f"\nProcessing [{mno}] {name} (DB ID {db_id}):")
        for filename, content in matching_docs:
            if filename in existing_names:
                print(f"  -> Already exists in LegalServer: {filename}")
                continue

            files = {
                'file': (filename, content, 'text/plain')
            }
            data = {
                'name': filename,
                'matter_uuid': muuid
            }

            res = requests.post(v2_url, headers=headers, files=files, data=data)
            if res.status_code in (200, 201):
                doc_uuid = res.json().get('data', {}).get('uuid')
                print(f"  -> SUCCESS uploaded {filename} via v2 API! (UUID: {doc_uuid})")
            else:
                print(f"  -> FAILED to upload {filename} via v2 API: {res.status_code} - {res.text}")

    print("\nFinished v2 document upload execution!")

if __name__ == "__main__":
    run_v2_uploads()
