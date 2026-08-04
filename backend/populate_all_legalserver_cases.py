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

# Comprehensive dictionary of case data for each client / matter
CASE_DEFINITIONS = {
    "Eleanor Vance": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "1428 Elm Street",
            "apt_num": "Apt 3B",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44113"
        },
        "adverse_party": {
            "organization_name": "Apex Properties LLC",
            "relationship_type": "Landlord"
        },
        "summary": (
            "Eviction defense: Tenant Eleanor Vance is facing an eviction action filed by Apex Properties LLC "
            "for non-payment of rent. Tenant has withheld rent for April, May, and June 2026 due to the landlord's "
            "ongoing failure to repair a severe ceiling leak and associated toxic black mold in her bathroom. "
            "Tenant's 7-year-old daughter has asthma, which was severely exacerbated by the mold, resulting in "
            "an emergency room visit. Tenant has saved all withheld rent and is prepared to pay it into escrow. "
            "Needs assistance drafting an Answer and Counterclaims."
        ),
        "documents": [
            {
                "id": "doc-ev-1",
                "title": "Summons_and_Complaint.txt",
                "filename": "Summons_and_Complaint.txt",
                "source": "Court Record",
                "text": (
                    "COURT OF COMMON PLEAS\nCUYAHOGA COUNTY, OHIO\nHOUSING DIVISION\n\n"
                    "APEX PROPERTIES LLC, Plaintiff, v. ELEANOR VANCE, Defendant.\n"
                    "Case No. 2026-CVG-008912\n\n"
                    "COMPLAINT IN EVICTION AND FOR MONEY DAMAGES\n"
                    "1. Plaintiff Apex Properties LLC is landlord of 1428 Elm Street, Apt 3B, Cleveland, OH 44113.\n"
                    "2. Defendant failed to pay monthly rent ($950.00) for April, May, and June 2026.\n"
                    "3. 3-day notice served June 1, 2026. Back rent owed: $2,850.00 plus $150 late fees."
                )
            },
            {
                "id": "doc-ev-2",
                "title": "Lease_Agreement.txt",
                "filename": "Lease_Agreement.txt",
                "source": "Lease Document",
                "text": (
                    "RESIDENTIAL LEASE AGREEMENT\n"
                    "Landlord: Apex Properties LLC | Tenant: Eleanor Vance\n"
                    "Premises: 1428 Elm Street, Apt 3B, Cleveland, OH 44113\n"
                    "Rent: $950.00/month. Term: August 1, 2025 - July 31, 2026.\n"
                    "Maintenance: Landlord shall maintain plumbing and structural components in good repair."
                )
            },
            {
                "id": "doc-ev-3",
                "title": "Notice_to_Quit.txt",
                "filename": "Notice_to_Quit.txt",
                "source": "Statutory Notice",
                "text": (
                    "3-DAY NOTICE TO LEAVE PREMISES (O.R.C. 1923.04)\n"
                    "Date: June 1, 2026\nTo: Eleanor Vance, 1428 Elm Street, Apt 3B, Cleveland, OH 44113\n"
                    "Reason: Unpaid rent for April and May 2026 totaling $1,900.00."
                )
            },
            {
                "id": "doc-ev-4",
                "title": "Intake_Notes.txt",
                "filename": "Intake_Notes.txt",
                "source": "Legal Aid Intake Notes",
                "text": (
                    "LEGAL AID INTAKE NOTES\nClient: Eleanor Vance | Date: June 15, 2026\n"
                    "Bathroom ceiling leak reported Jan 18. Black mold 3x4ft developed. Child ER visit April 28 for asthma.\n"
                    "Rent withheld saved in escrow account ($2,850 total). Defense under ORC 5321.04 & 5321.02 retaliation."
                )
            }
        ]
    },

    "Marcus Vance": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "3204 Superior Avenue",
            "apt_num": "Apt 12",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44114"
        },
        "adverse_party": {
            "organization_name": "Metro Housing Rentals LLC",
            "relationship_type": "Landlord"
        },
        "summary": (
            "Tenant Marcus Vance is facing a nonpayment eviction action filed by Metro Housing Rentals LLC at "
            "Cleveland Municipal Court. Tenant resides in a unit subsidized by a Section 8 Housing Choice Voucher. "
            "The dispute involves a ledger balance of $1,800, which includes unpaid tenant rent portions as well "
            "as the housing authority's subsidy payments that were improperly withheld due to an administrative "
            "accounting error between landlord and CMHA. Tenant lives with two minor children."
        ),
        "documents": [
            {
                "id": "doc-mv-1",
                "title": "Summons_and_Complaint_Marcus_Vance.txt",
                "filename": "Summons_and_Complaint_Marcus_Vance.txt",
                "source": "Court Filing",
                "text": (
                    "CLEVELAND MUNICIPAL COURT - HOUSING DIVISION\n"
                    "METRO HOUSING RENTALS LLC v. MARCUS VANCE\nCase No. 2026-CVG-010422\n\n"
                    "COMPLAINT FOR EVICTION AND MONEY DAMAGES\n"
                    "1. Landlord owns 3204 Superior Ave, Apt 12, Cleveland, OH 44114.\n"
                    "2. Defendant Marcus Vance is in default of monthly tenant portion of rent ($150/mo) and claims $1,800 total balance.\n"
                    "3. 3-day notice served May 28, 2026."
                )
            },
            {
                "id": "doc-mv-2",
                "title": "HAP_Contract_and_Voucher_CMHA.txt",
                "filename": "HAP_Contract_and_Voucher_CMHA.txt",
                "source": "Housing Authority Record",
                "text": (
                    "HOUSING ASSISTANCE PAYMENTS (HAP) CONTRACT - SECTION 8 VOUCHER PROGRAM\n"
                    "Housing Authority: Cuyahoga Metropolitan Housing Authority (CMHA)\n"
                    "Tenant: Marcus Vance | Landlord: Metro Housing Rentals LLC\n"
                    "Contract Rent: $900.00 | Housing Assistance Payment (CMHA): $750.00 | Tenant Rent Share: $150.00."
                )
            },
            {
                "id": "doc-mv-3",
                "title": "Tenant_Rent_Ledger_Extract.txt",
                "filename": "Tenant_Rent_Ledger_Extract.txt",
                "source": "Landlord Ledger",
                "text": (
                    "METRO HOUSING RENTALS LLC - TENANT ACCOUNT STATEMENT\n"
                    "Account: Marcus Vance - 3204 Superior Ave #12\n"
                    "Jan 2026: Rent $900 | CMHA paid $750 | Tenant paid $150 | Bal $0\n"
                    "Feb-Apr 2026: CMHA electronic payment failed due to vendor bank update; landlord charged full $900/mo to tenant."
                )
            },
            {
                "id": "doc-mv-4",
                "title": "Legal_Aid_Intake_Marcus_Vance.txt",
                "filename": "Legal_Aid_Intake_Marcus_Vance.txt",
                "source": "Intake Notes",
                "text": (
                    "INTAKE SUMMARY - MARCUS VANCE\n"
                    "Client paid his $150 share every month via money order. CMHA missed 2 payments during portal transition.\n"
                    "Landlord cannot evict tenant for CMHA's delayed subsidy under Federal HAP contract regulations & HUD rules."
                )
            }
        ]
    },

    "Linda Thompson": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "2195 Coventry Road",
            "apt_num": "Apt 4C",
            "city": "Cleveland Heights",
            "state": "OH",
            "zip": "44118"
        },
        "adverse_party": {
            "organization_name": "Euclid Heights Apartments LLC",
            "relationship_type": "Landlord"
        },
        "summary": (
            "Eviction action filed against Linda Thompson by Euclid Heights Apartments for nonpayment of rent. "
            "The tenant reports that the landlord accepted a partial rent payment of $400 shortly after serving "
            "the 3-day notice. Additionally, tenant states that they withheld rent due to a severe ceiling leak "
            "and toxic black mold in the bathroom that caused her child to be hospitalized for asthma. Tenant is "
            "6 months pregnant and has two minor children."
        ),
        "documents": [
            {
                "id": "doc-lt-1",
                "title": "Summons_and_Complaint_Linda_Thompson.txt",
                "filename": "Summons_and_Complaint_Linda_Thompson.txt",
                "source": "Court Record",
                "text": (
                    "CLEVELAND HEIGHTS MUNICIPAL COURT\n"
                    "EUCLID HEIGHTS APARTMENTS LLC v. LINDA THOMPSON\nCase No. 2026-CVG-004119\n\n"
                    "COMPLAINT FOR FORCIBLE ENTRY AND DETAINER\n"
                    "Premises: 2195 Coventry Rd, Apt 4C, Cleveland Heights, OH 44118.\n"
                    "Claim: Unpaid rent for April and May 2026 ($1,700 balance)."
                )
            },
            {
                "id": "doc-lt-2",
                "title": "Partial_Rent_Payment_Receipt.txt",
                "filename": "Partial_Rent_Payment_Receipt.txt",
                "source": "Payment Record",
                "text": (
                    "EUCLID HEIGHTS APARTMENTS - RECEIPT OF PAYMENT\n"
                    "Date: June 5, 2026 (4 days after 3-day notice served on June 1, 2026)\n"
                    "Received from Linda Thompson: $400.00 via cashier's check #88412.\n"
                    "Accepted and deposited by Property Manager without reservation."
                )
            },
            {
                "id": "doc-lt-3",
                "title": "Hospital_ER_Discharge_Report.txt",
                "filename": "Hospital_ER_Discharge_Report.txt",
                "source": "Medical Record",
                "text": (
                    "UNIVERSITY HOSPITALS RAINBOW BABIES & CHILDREN'S HOSPITAL\n"
                    "Patient: Jayden Thompson (Age 5) | Mother: Linda Thompson\n"
                    "Admission Date: May 12, 2026 | Diagnosis: Acute severe asthma exacerbation.\n"
                    "Environmental Notes: Triggered by severe indoor mold spore exposure in bathroom."
                )
            },
            {
                "id": "doc-lt-4",
                "title": "Intake_Notes_Linda_Thompson.txt",
                "filename": "Intake_Notes_Linda_Thompson.txt",
                "source": "Intake Notes",
                "text": (
                    "LEGAL AID INTAKE NOTES - LINDA THOMPSON\n"
                    "Defenses: 1. Waiver of 3-Day Notice under Ohio law by accepting $400 partial rent after notice.\n"
                    "2. Breach of Warranty of Habitability (O.R.C. 5321.04) due to toxic mold & ceiling collapse."
                )
            }
        ]
    },

    "Robert Garcia": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "14500 Detroit Avenue",
            "apt_num": "Apt 602",
            "city": "Lakewood",
            "state": "OH",
            "zip": "44107"
        },
        "adverse_party": {
            "organization_name": "Lakewood Property Group LLC",
            "relationship_type": "Landlord"
        },
        "summary": (
            "Eviction complaint filed against Robert Garcia by Lakewood Property Group in Lakewood Municipal Court. "
            "The landlord served a 3-day notice to leave the premises on June 10, 2026, and subsequently filed the "
            "eviction complaint on June 12, 2026 (premature filing prior to expiration of 3 full business days). "
            "The 3-day notice also fails to contain required statutory legal aid disclosures. Tenant is 72 years "
            "old and has a severe mobility impairment."
        ),
        "documents": [
            {
                "id": "doc-rg-1",
                "title": "Summons_and_Complaint_Robert_Garcia.txt",
                "filename": "Summons_and_Complaint_Robert_Garcia.txt",
                "source": "Court Record",
                "text": (
                    "LAKEWOOD MUNICIPAL COURT\nLAKEWOOD PROPERTY GROUP LLC v. ROBERT GARCIA\n"
                    "Case No. 2026-CVG-002180\n"
                    "Filed: June 12, 2026 for nonpayment of $1,100 June rent at 14500 Detroit Ave #602."
                )
            },
            {
                "id": "doc-rg-2",
                "title": "Three_Day_Notice_to_Leave.txt",
                "filename": "Three_Day_Notice_to_Leave.txt",
                "source": "Landlord Notice",
                "text": (
                    "3-DAY NOTICE TO LEAVE PREMISES\nServed: Wednesday, June 10, 2026 at 4:00 PM.\n"
                    "Note: Landlord filed court action Friday, June 12, violating 3 full business days rule."
                )
            },
            {
                "id": "doc-rg-3",
                "title": "Physician_Verification_Mobility_Impairment.txt",
                "filename": "Physician_Verification_Mobility_Impairment.txt",
                "source": "Medical Verification",
                "text": (
                    "METROHEALTH MEDICAL CENTER - PHYSICIAN STATEMENT\n"
                    "Patient: Robert Garcia (DOB: 03/14/1954)\n"
                    "Diagnosis: Severe osteoarthritis, wheelchair dependent. Requires elevator access and home care."
                )
            },
            {
                "id": "doc-rg-4",
                "title": "Intake_Notes_Robert_Garcia.txt",
                "filename": "Intake_Notes_Robert_Garcia.txt",
                "source": "Intake Notes",
                "text": (
                    "LEGAL AID INTAKE NOTES - ROBERT GARCIA\n"
                    "Motion to Dismiss for lack of subject matter jurisdiction: 3-day notice served June 10, suit filed June 12.\n"
                    "Under Ohio law (ORC 1923.04), 3 full business days must elapse before complaint filing."
                )
            }
        ]
    },

    "James Miller": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "5812 Ridge Road",
            "apt_num": "Apt 104",
            "city": "Parma",
            "state": "OH",
            "zip": "44129"
        },
        "adverse_party": {
            "organization_name": "Parma Landlords LLC",
            "relationship_type": "Landlord"
        },
        "summary": (
            "Nonpayment eviction case filed against James Miller by Parma Landlords LLC in Parma Municipal Court. "
            "The tenant, a single adult living alone in a private market apartment, fell behind on rent for May "
            "and June 2026 after a sudden corporate layoff. Emergency rental assistance from Cuyahoga County has "
            "been approved and is awaiting disbursement."
        ),
        "documents": [
            {
                "id": "doc-jm-1",
                "title": "Summons_and_Complaint_James_Miller.txt",
                "filename": "Summons_and_Complaint_James_Miller.txt",
                "source": "Court Record",
                "text": (
                    "PARMA MUNICIPAL COURT\nPARMA LANDLORDS LLC v. JAMES MILLER\nCase No. 2026-CVG-005120\n"
                    "Premises: 5812 Ridge Rd #104, Parma, OH 44129. Amount claimed: $1,900.00."
                )
            },
            {
                "id": "doc-jm-2",
                "title": "Rental_Assistance_Application_Confirmation.txt",
                "filename": "Rental_Assistance_Application_Confirmation.txt",
                "source": "Agency Confirmation",
                "text": (
                    "CUYAHOGA COUNTY HOUSING STABILITY FUND\n"
                    "Applicant: James Miller | Status: APPROVED for $2,400.00.\n"
                    "Disbursement check scheduled to Parma Landlords LLC within 10 business days."
                )
            },
            {
                "id": "doc-jm-3",
                "title": "Intake_Notes_James_Miller.txt",
                "filename": "Intake_Notes_James_Miller.txt",
                "source": "Intake Notes",
                "text": (
                    "INTAKE NOTES - JAMES MILLER\n"
                    "File Motion for Continuance to allow rental assistance check to process. Landlord open to dismissal upon receipt."
                )
            }
        ]
    },

    "Sarah Jenkins": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "3421 Mayfield Road",
            "apt_num": "Apt 2B",
            "city": "Cleveland Heights",
            "state": "OH",
            "zip": "44118"
        },
        "adverse_party": {
            "organization_name": "Heights Realty LLC",
            "relationship_type": "Landlord"
        },
        "summary": (
            "Holdover eviction complaint filed against Sarah Jenkins in Cleveland Heights. The tenant is a single "
            "adult living in a private market rental. The landlord issued a non-renewal notice immediately after "
            "tenant complained to the city building inspector regarding lack of heat during winter."
        ),
        "documents": [
            {
                "id": "doc-sj-1",
                "title": "Summons_and_Complaint_Sarah_Jenkins.txt",
                "filename": "Summons_and_Complaint_Sarah_Jenkins.txt",
                "source": "Court Record",
                "text": (
                    "CLEVELAND HEIGHTS MUNICIPAL COURT\nHEIGHTS REALTY LLC v. SARAH JENKINS\nCase No. 2026-CVG-003910\n"
                    "Action for holdover possession of 3421 Mayfield Rd #2B."
                )
            },
            {
                "id": "doc-sj-2",
                "title": "City_Housing_Inspection_Report.txt",
                "filename": "City_Housing_Inspection_Report.txt",
                "source": "Municipal Inspection",
                "text": (
                    "CLEVELAND HEIGHTS BUILDING DEPARTMENT\n"
                    "Inspection Date: February 14, 2026 | Premises: 3421 Mayfield Rd #2B\n"
                    "Violation Cited: Heating unit failing to maintain 68 deg F minimum temperature requirement (ORC 5321.04)."
                )
            },
            {
                "id": "doc-sj-3",
                "title": "Intake_Notes_Sarah_Jenkins.txt",
                "filename": "Intake_Notes_Sarah_Jenkins.txt",
                "source": "Intake Notes",
                "text": (
                    "INTAKE NOTES - SARAH JENKINS\n"
                    "Retaliatory Eviction Defense under ORC 5321.02. Non-renewal notice was served 6 days after building inspection."
                )
            }
        ]
    },

    "Charles Davis": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "16800 Chagrin Boulevard",
            "apt_num": "Apt 3A",
            "city": "Shaker Heights",
            "state": "OH",
            "zip": "44120"
        },
        "adverse_party": {
            "organization_name": "Shaker Square Apartments LLC",
            "relationship_type": "Landlord"
        },
        "summary": (
            "Nonpayment eviction case filed against Charles Davis in Shaker Heights Municipal Court. "
            "Tenant was laid off briefly and has now secured employment, seeking a payment plan or brief delay."
        ),
        "documents": [
            {
                "id": "doc-cd-1",
                "title": "Summons_and_Complaint_Charles_Davis.txt",
                "filename": "Summons_and_Complaint_Charles_Davis.txt",
                "source": "Court Record",
                "text": (
                    "SHAKER HEIGHTS MUNICIPAL COURT\nSHAKER SQUARE APARTMENTS LLC v. CHARLES DAVIS\n"
                    "Case No. 2026-CVG-001920\nUnpaid rent for May/June 2026 ($1,650 balance)."
                )
            },
            {
                "id": "doc-cd-2",
                "title": "Intake_Notes_Charles_Davis.txt",
                "filename": "Intake_Notes_Charles_Davis.txt",
                "source": "Intake Notes",
                "text": (
                    "INTAKE NOTES - CHARLES DAVIS\nClient started new job June 1. Seeking agreed consent judgment with stay of execution."
                )
            }
        ]
    },

    "Donna Evans": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "13405 Euclid Avenue",
            "apt_num": "Apt 510",
            "city": "East Cleveland",
            "state": "OH",
            "zip": "44112"
        },
        "adverse_party": {
            "organization_name": "East Cleveland Properties LLC",
            "relationship_type": "Landlord"
        },
        "summary": (
            "Eviction action filed against Donna Evans in East Cleveland for an alleged unauthorized occupant. "
            "Tenant states occupant is a short-term visiting relative caring for tenant after surgery. "
            "Summons copy has an illegible hearing date."
        ),
        "documents": [
            {
                "id": "doc-de-1",
                "title": "Summons_and_Complaint_Donna_Evans.txt",
                "filename": "Summons_and_Complaint_Donna_Evans.txt",
                "source": "Court Record",
                "text": (
                    "EAST CLEVELAND MUNICIPAL COURT\nEAST CLEVELAND PROPERTIES LLC v. DONNA EVANS\n"
                    "Case No. 2026-CVG-007140\nAlleged lease violation: Unauthorized guest over 14 days."
                )
            },
            {
                "id": "doc-de-2",
                "title": "Guest_Caregiver_Statement.txt",
                "filename": "Guest_Caregiver_Statement.txt",
                "source": "Witness Statement",
                "text": (
                    "STATEMENT OF MARY EVANS\n"
                    "I am Donna Evans' sister. I stayed at 13405 Euclid Ave #510 for 5 days following her knee surgery to assist her."
                )
            },
            {
                "id": "doc-de-3",
                "title": "Intake_Notes_Donna_Evans.txt",
                "filename": "Intake_Notes_Donna_Evans.txt",
                "source": "Intake Notes",
                "text": (
                    "INTAKE NOTES - DONNA EVANS\nDefenses: 1. No breach of lease (temporary medical guest). 2. Defective summons (illegible date)."
                )
            }
        ]
    },

    "Thomas Wilson": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "4810 Turney Road",
            "apt_num": "Apt 14",
            "city": "Garfield Heights",
            "state": "OH",
            "zip": "44125"
        },
        "adverse_party": {
            "organization_name": "Turney Road Management LLC",
            "relationship_type": "Landlord"
        },
        "summary": (
            "Landlord filed an eviction action against Thomas Wilson in Garfield Heights alleging property damage "
            "to window and lock. Tenant states damage was caused by an attempted burglary by an unknown intruder, "
            "supported by a police report."
        ),
        "documents": [
            {
                "id": "doc-tw-1",
                "title": "Summons_and_Complaint_Thomas_Wilson.txt",
                "filename": "Summons_and_Complaint_Thomas_Wilson.txt",
                "source": "Court Record",
                "text": (
                    "GARFIELD HEIGHTS MUNICIPAL COURT\nTURNEY ROAD MANAGEMENT LLC v. THOMAS WILSON\n"
                    "Case No. 2026-CVG-003110\nEviction for alleged waste and property damage."
                )
            },
            {
                "id": "doc-tw-2",
                "title": "Police_Incident_Report_Garfield_Heights.txt",
                "filename": "Police_Incident_Report_Garfield_Heights.txt",
                "source": "Police Department Record",
                "text": (
                    "GARFIELD HEIGHTS POLICE DEPARTMENT - INCIDENT REPORT\n"
                    "Report No. 26-09812 | Incident: Attempted Burglary / Vandalism\n"
                    "Location: 4810 Turney Rd #14 | Reporting Party: Thomas Wilson\n"
                    "Officer Notes: Unknown suspect attempted forced entry causing outer window crack and lock deformation."
                )
            },
            {
                "id": "doc-tw-3",
                "title": "Intake_Notes_Thomas_Wilson.txt",
                "filename": "Intake_Notes_Thomas_Wilson.txt",
                "source": "Intake Notes",
                "text": (
                    "INTAKE NOTES - THOMAS WILSON\nTenant is victim of crime; not liable for third-party criminal damage under lease."
                )
            }
        ]
    },

    "Patricia Taylor": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "18200 Pearl Road",
            "apt_num": "Apt 208",
            "city": "Strongsville",
            "state": "OH",
            "zip": "44136"
        },
        "adverse_party": {
            "organization_name": "Strongsville Apartments LLC",
            "relationship_type": "Landlord"
        },
        "summary": (
            "Nonpayment eviction action filed against Patricia Taylor by Strongsville Apartments LLC. "
            "Complaint was signed and filed by non-attorney property manager. Tenant has a documented disability."
        ),
        "documents": [
            {
                "id": "doc-pt-1",
                "title": "Summons_and_Complaint_Patricia_Taylor.txt",
                "filename": "Summons_and_Complaint_Patricia_Taylor.txt",
                "source": "Court Record",
                "text": (
                    "BEREA MUNICIPAL COURT\nSTRONGSVILLE APARTMENTS LLC v. PATRICIA TAYLOR\n"
                    "Case No. 2026-CVG-004810\nComplaint signed: /s/ Brenda Vance, Property Manager (non-attorney)."
                )
            },
            {
                "id": "doc-pt-2",
                "title": "Intake_Notes_Patricia_Taylor.txt",
                "filename": "Intake_Notes_Patricia_Taylor.txt",
                "source": "Intake Notes",
                "text": (
                    "INTAKE NOTES - PATRICIA TAYLOR\n"
                    "Motion to Dismiss for Unauthorized Practice of Law (UPL) as complaint was filed by non-lawyer for corporate LLC."
                )
            }
        ]
    },

    "Christopher Anderson": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "26900 Detroit Road",
            "apt_num": "Apt 115",
            "city": "Westlake",
            "state": "OH",
            "zip": "44145"
        },
        "adverse_party": {
            "organization_name": "Westlake Village Apartments LLC",
            "relationship_type": "Landlord"
        },
        "summary": (
            "Eviction action filed against Christopher Anderson in Westlake based on alleged noise complaints. "
            "Tenant asserts eviction is retaliatory following tenant's emergency call to Dominion Energy and city inspectors "
            "reporting a dangerous gas leak."
        ),
        "documents": [
            {
                "id": "doc-ca-1",
                "title": "Summons_and_Complaint_Christopher_Anderson.txt",
                "filename": "Summons_and_Complaint_Christopher_Anderson.txt",
                "source": "Court Record",
                "text": (
                    "ROCKY RIVER MUNICIPAL COURT\nWESTLAKE VILLAGE APARTMENTS LLC v. CHRISTOPHER ANDERSON\n"
                    "Case No. 2026-CVG-001840\nClaim: Lease termination for alleged noise disturbance."
                )
            },
            {
                "id": "doc-ca-2",
                "title": "Gas_Company_Inspection_Report.txt",
                "filename": "Gas_Company_Inspection_Report.txt",
                "source": "Utility Company Record",
                "text": (
                    "DOMINION ENERGY OHIO - EMERGENCY SERVICE CALL LOG\n"
                    "Date: May 19, 2026 | Address: 26900 Detroit Rd #115\n"
                    "Technician Findings: Active gas leak detected at stove supply line; gas shut off pending landlord repair."
                )
            },
            {
                "id": "doc-ca-3",
                "title": "Intake_Notes_Christopher_Anderson.txt",
                "filename": "Intake_Notes_Christopher_Anderson.txt",
                "source": "Intake Notes",
                "text": (
                    "INTAKE NOTES - CHRISTOPHER ANDERSON\nRetaliation defense under ORC 5321.02 following gas leak report."
                )
            }
        ]
    },

    "Samuel Green": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "11802 St Clair Avenue",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44108"
        },
        "adverse_party": {
            "organization_name": "Ohio Department of Medicaid",
            "relationship_type": "Agency"
        },
        "summary": (
            "Appeal of Medicaid PASSPORT waiver service termination for an elderly senior requiring home personal care. "
            "Agency claims client no longer meets intermediate level of care."
        ),
        "documents": [
            {
                "id": "doc-sg-1",
                "title": "Medicaid_Notice_of_Action.txt",
                "filename": "Medicaid_Notice_of_Action.txt",
                "source": "Agency Notice",
                "text": (
                    "OHIO DEPARTMENT OF MEDICAID - NOTICE OF ACTION\n"
                    "To: Samuel Green | Date: May 10, 2026\n"
                    "Notice: Termination of PASSPORT Waiver Personal Care Aide Hours effective June 1, 2026."
                )
            },
            {
                "id": "doc-sg-2",
                "title": "Treating_Physician_Level_of_Care_Assessment.txt",
                "filename": "Treating_Physician_Level_of_Care_Assessment.txt",
                "source": "Medical Assessment",
                "text": (
                    "CLEVELAND CLINIC - GERIATRIC MEDICINE EVALUATION\n"
                    "Patient: Samuel Green (Age 78)\n"
                    "Assessment: Patient requires assistance with 4 ADLs (bathing, dressing, mobility, medication management)."
                )
            }
        ]
    },

    "Maria Santos": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "3105 Clark Avenue",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44109"
        },
        "adverse_party": {
            "first": "Carlos",
            "last": "Santos",
            "relationship_type": "Spouse"
        },
        "summary": (
            "Representation of client in a contested divorce proceeding involving custody of two minor children "
            "and division of marital debt. Separated 14 months."
        ),
        "documents": [
            {
                "id": "doc-ms-1",
                "title": "Divorce_Complaint_Santos.txt",
                "filename": "Divorce_Complaint_Santos.txt",
                "source": "Court Record",
                "text": (
                    "CUYAHOGA COUNTY COMMON PLEAS COURT - DOMESTIC RELATIONS DIVISION\n"
                    "MARIA SANTOS v. CARLOS SANTOS\nCase No. DR-26-381902\n"
                    "Complaint for Divorce, Custody, and Equitable Division of Marital Property."
                )
            },
            {
                "id": "doc-ms-2",
                "title": "Proposed_Parenting_Plan.txt",
                "filename": "Proposed_Parenting_Plan.txt",
                "source": "Legal Document",
                "text": (
                    "PROPOSED SHARED PARENTING PLAN\nMother Maria Santos proposes primary residential parent designation."
                )
            }
        ]
    },

    "David Kowalski": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "7210 Fleet Avenue",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44105"
        },
        "adverse_party": {
            "organization_name": "Cleveland Clinic & Capital One Bank",
            "relationship_type": "Creditor"
        },
        "summary": (
            "Chapter 7 bankruptcy for debtor overwhelmed by $45,000 in medical debt and credit card liabilities "
            "following extended unemployment."
        ),
        "documents": [
            {
                "id": "doc-dk-1",
                "title": "Creditor_Balance_Sheet.txt",
                "filename": "Creditor_Balance_Sheet.txt",
                "source": "Financial Record",
                "text": (
                    "SCHEDULE OF UNSECURED CREDITORS - DAVID KOWALSKI\n"
                    "1. Cleveland Clinic Health System: $32,450.00 (Medical)\n"
                    "2. Capital One Bank: $12,800.00 (Credit Card)"
                )
            },
            {
                "id": "doc-dk-2",
                "title": "Chapter_7_Petition_Draft.txt",
                "filename": "Chapter_7_Petition_Draft.txt",
                "source": "Court Draft",
                "text": (
                    "UNITED STATES BANKRUPTCY COURT - NORTHERN DISTRICT OF OHIO\n"
                    "In re: DAVID KOWALSKI, Debtor. Chapter 7 Voluntary Petition."
                )
            }
        ]
    },

    "Aisha Jackson": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "12401 Buckeye Road",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44120"
        },
        "adverse_party": {
            "first": "Marcus",
            "last": "Jackson",
            "relationship_type": "Ex-Partner"
        },
        "summary": (
            "Representation of mother seeking modification of a custody order to restrict father's visitation "
            "due to safety concerns and substance abuse allegations."
        ),
        "documents": [
            {
                "id": "doc-aj-1",
                "title": "DUI_Arrest_Record_Excerpt.txt",
                "filename": "DUI_Arrest_Record_Excerpt.txt",
                "source": "Court Record",
                "text": (
                    "CLEVELAND MUNICIPAL COURT - CRIMINAL DIVISION\n"
                    "State of Ohio v. Marcus Jackson | Case No. 2026-TRC-011204\n"
                    "Charge: OVI / Operating Vehicle Impaired."
                )
            },
            {
                "id": "doc-aj-2",
                "title": "Motion_for_Supervised_Visitation.txt",
                "filename": "Motion_for_Supervised_Visitation.txt",
                "source": "Court Filing",
                "text": (
                    "CUYAHOGA COUNTY JUVENILE COURT\nAISHA JACKSON v. MARCUS JACKSON\n"
                    "Motion to Modify Allocation of Parental Rights and Order Supervised Visitation."
                )
            }
        ]
    },

    "Carlos Mendez": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "4210 Lorain Avenue",
            "apt_num": "Apt 2",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44113"
        },
        "adverse_party": {
            "organization_name": "El Sol Restaurant & Grill LLC",
            "relationship_type": "Employer"
        },
        "summary": (
            "Wage theft representation for a restaurant employee who was denied overtime pay and had tips withheld "
            "by the employer in violation of federal FLSA and Ohio wage laws."
        ),
        "documents": [
            {
                "id": "doc-cm-1",
                "title": "Overtime_Hours_Log.txt",
                "filename": "Overtime_Hours_Log.txt",
                "source": "Employee Log",
                "text": (
                    "CARLOS MENDEZ - WEEKLY HOURS WORKED LOG\n"
                    "Avg hours worked: 54 hours/week. Paid flat cash rate without 1.5x overtime multiplier."
                )
            },
            {
                "id": "doc-cm-2",
                "title": "FLSA_Wage_Demand_Letter.txt",
                "filename": "FLSA_Wage_Demand_Letter.txt",
                "source": "Legal Demand",
                "text": (
                    "NOTICE OF WAGE CLAIM AND DEMAND FOR PAYMENT\n"
                    "To: El Sol Restaurant & Grill LLC / Ricardo Lopez\n"
                    "Demand for unpaid overtime compensation and liquidated damages under 29 U.S.C. 207."
                )
            }
        ]
    },

    "Brenda Taylor": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "8904 Superior Avenue",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44106"
        },
        "adverse_party": {
            "organization_name": "Social Security Administration",
            "relationship_type": "Agency"
        },
        "summary": (
            "Appeal of Supplemental Security Income (SSI) benefits denial for an individual with chronic spinal "
            "stenosis and cognitive impairments. Pending ALJ hearing."
        ),
        "documents": [
            {
                "id": "doc-bt-1",
                "title": "SSA_Reconsideration_Denial.txt",
                "filename": "SSA_Reconsideration_Denial.txt",
                "source": "SSA Notice",
                "text": (
                    "SOCIAL SECURITY ADMINISTRATION - NOTICE OF RECONSIDERATION DENIAL\n"
                    "Claimant: Brenda Taylor | SSN: XXX-XX-4819\nClaim for Supplemental Security Income."
                )
            },
            {
                "id": "doc-bt-2",
                "title": "MRI_Spine_Medical_Report.txt",
                "filename": "MRI_Spine_Medical_Report.txt",
                "source": "Medical Record",
                "text": (
                    "METROHEALTH NEUROLOGY - MRI LUMBAR SPINE\n"
                    "Findings: Severe spinal stenosis L4-L5 with nerve root compression."
                )
            }
        ]
    },

    "Karen Novak": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "5410 Denison Avenue",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44102"
        },
        "adverse_party": {
            "organization_name": "Midwest Logistics Warehouse Inc.",
            "relationship_type": "Employer"
        },
        "summary": (
            "Representation of employee in an unemployment benefits appeal. Employer alleges resignation without "
            "good cause, but claimant asserts constructive discharge due to unsafe warehouse conditions."
        ),
        "documents": [
            {
                "id": "doc-kn-1",
                "title": "Resignation_Email.txt",
                "filename": "Resignation_Email.txt",
                "source": "Correspondence",
                "text": (
                    "From: Karen Novak To: HR Midwest Logistics\n"
                    "Subject: Resignation due to unaddressed safety hazards on forklift loading dock."
                )
            },
            {
                "id": "doc-kn-2",
                "title": "ODJFS_Unemployment_Appeal.txt",
                "filename": "ODJFS_Unemployment_Appeal.txt",
                "source": "Agency Appeal",
                "text": (
                    "OHIO DEPT OF JOB & FAMILY SERVICES - APPEAL TO REVIEW COMMISSION\n"
                    "Claimant Karen Novak appeals initial disallowance of benefits."
                )
            }
        ]
    },

    "Olivia Martinez": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "3502 Newark Avenue",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44109"
        },
        "adverse_party": {
            "organization_name": "Cleveland Metropolitan School District",
            "relationship_type": "School District"
        },
        "summary": (
            "IEP advocacy for a child with Autism Spectrum Disorder. Parents are disputing reduction of speech "
            "therapy hours and removal of behavioral aide."
        ),
        "documents": [
            {
                "id": "doc-om-1",
                "title": "IEP_Speech_Evaluation_Excerpt.txt",
                "filename": "IEP_Speech_Evaluation_Excerpt.txt",
                "source": "Educational Record",
                "text": (
                    "CLEVELAND METROPOLITAN SCHOOL DISTRICT - IEP EVALUATION REPORT\n"
                    "Student: Mateo Martinez (Age 8) | Diagnosis: ASD Level 2."
                )
            },
            {
                "id": "doc-om-2",
                "title": "Independent_Speech_Therapy_Assessment.txt",
                "filename": "Independent_Speech_Therapy_Assessment.txt",
                "source": "Independent Assessment",
                "text": (
                    "CLEVELAND SPEECH & HEARING CENTER\n"
                    "Recommends minimum 3 hours/week direct speech-language pathology services."
                )
            }
        ]
    },

    "Evelyn Carter": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "14208 Kinsman Road",
            "city": "Cleveland",
            "state": "OH",
            "zip": "44120"
        },
        "adverse_party": None,  # Non-adversarial estate planning
        "summary": (
            "Preparation of a simple will, Transfer on Death Affidavit, and healthcare power of attorney for a "
            "senior citizen wishing to direct transfer of her home to her grandchild."
        ),
        "documents": [
            {
                "id": "doc-ec-1",
                "title": "Will_Intake_Information.txt",
                "filename": "Will_Intake_Information.txt",
                "source": "Intake Form",
                "text": (
                    "ESTATE PLANNING INTAKE - EVELYN CARTER\n"
                    "Asset: Residence at 14208 Kinsman Rd, Cleveland OH. Beneficiary: Granddaughter Maya Carter."
                )
            },
            {
                "id": "doc-ec-2",
                "title": "Last_Will_and_Testament_Draft.txt",
                "filename": "Last_Will_and_Testament_Draft.txt",
                "source": "Draft Will",
                "text": (
                    "LAST WILL AND TESTAMENT OF EVELYN CARTER\n"
                    "I, Evelyn Carter, declare this to be my Last Will and Testament..."
                )
            }
        ]
    },

    "Daniel O'Connor": {
        "address": {
            "type": "Home",
            "primary": True,
            "street": "14102 Shaw Avenue",
            "city": "East Cleveland",
            "state": "OH",
            "zip": "44112"
        },
        "adverse_party": {
            "organization_name": "Humana Medicare Advantage",
            "relationship_type": "Insurer"
        },
        "summary": (
            "Appeal of a Medicare Part D prescription drug coverage denial for a critical cardiac medication (Entresto) "
            "prescribed by client's physician following heart failure diagnosis."
        ),
        "documents": [
            {
                "id": "doc-do-1",
                "title": "Medicare_Part_D_Denial_Notice.txt",
                "filename": "Medicare_Part_D_Denial_Notice.txt",
                "source": "Insurance Notice",
                "text": (
                    "HUMANA MEDICARE PART D - NOTICE OF DENIAL OF MEDICARE PRESCRIPTION DRUG COVERAGE\n"
                    "Enrollee: Daniel O'Connor | Drug: Entresto 97/103mg | Reason: Non-formulary."
                )
            },
            {
                "id": "doc-do-2",
                "title": "Cardiologist_Prior_Auth_Statement.txt",
                "filename": "Cardiologist_Prior_Auth_Statement.txt",
                "source": "Physician Letter",
                "text": (
                    "CLEVELAND CLINIC HEART & VASCULAR INSTITUTE\n"
                    "Re: Daniel O'Connor | Physician statement confirming formulary alternatives (ACE inhibitors) caused severe angioedema."
                )
            }
        ]
    }
}

# Generic fallback for any other test matter
GENERIC_FALLBACK = {
    "address": {
        "type": "Home",
        "primary": True,
        "street": "100 Superior Avenue",
        "city": "Cleveland",
        "state": "OH",
        "zip": "44114"
    },
    "adverse_party": {
        "organization_name": "General Landlord & Property Management LLC",
        "relationship_type": "Landlord"
    },
    "summary": "Housing dispute involving residential lease conditions, rent accounting, or notice verification."
}


def populate():
    base_url = settings.LEGALSERVER_BASE_URL.rstrip('/')
    token = settings.LEGALSERVER_API_TOKEN
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    client = LegalServerClient()
    matters = client.search_matters(limit=100)
    print(f"Found {len(matters)} matters in LegalServer.")

    for m in matters:
        muuid = m.get('matter_uuid')
        mno = m.get('matter_identification_number') or m.get('case_number')
        first = m.get('first', '')
        last = m.get('last', '')
        name = f"{first} {last}".strip() or m.get('case_title', '')
        
        print(f"\nProcessing [{mno}] UUID: {muuid} | Name: {name}")

        # Find matching definition or fallback
        match_def = None
        for key, definition in CASE_DEFINITIONS.items():
            if key.casefold() in name.casefold() or name.casefold() in key.casefold():
                match_def = definition
                break
        
        if not match_def:
            match_def = GENERIC_FALLBACK

        # 1. Populate Address in LegalServer if missing
        addrs = m.get('matter_addresses', [])
        if not addrs and match_def.get("address"):
            addr_payload = match_def["address"]
            res = requests.post(f"{base_url}/api/v1/matters/{muuid}/addresses", headers=headers, json=addr_payload)
            if res.status_code in (200, 201):
                print(f"  -> Added Address: {addr_payload['street']}, {addr_payload['city']}")
            else:
                print(f"  -> Failed to add address: {res.status_code} - {res.text}")
        else:
            print(f"  -> Address already present ({len(addrs)})")

        # 2. Populate Adverse Party in LegalServer if missing and applicable
        aps = m.get('adverse_parties', [])
        if not aps and match_def.get("adverse_party"):
            ap_data = match_def["adverse_party"]
            ap_payload = {}
            if "organization_name" in ap_data:
                ap_payload["organization_name"] = ap_data["organization_name"]
            if "first" in ap_data:
                ap_payload["first"] = ap_data["first"]
            if "last" in ap_data:
                ap_payload["last"] = ap_data["last"]
            # omit relationship_type if invalid or not specified
            rel = ap_data.get("relationship_type")
            if rel in ("Landlord", "Spouse"):
                ap_payload["relationship_type"] = rel

            res = requests.post(f"{base_url}/api/v1/matters/{muuid}/adverse_parties", headers=headers, json=ap_payload)
            if res.status_code in (200, 201):
                ap_name = ap_payload.get("organization_name") or f"{ap_payload.get('first')} {ap_payload.get('last')}"
                print(f"  -> Added Adverse Party: {ap_name}")
            else:
                print(f"  -> Failed to add adverse party: {res.status_code} - {res.text}")
        else:
            print(f"  -> Adverse Party present ({len(aps)}) or N/A")

        # 3. Update Summary in LegalServer if basic/empty
        current_summary = m.get('pro_bono_opportunity_summary') or m.get('summary') or ''
        new_summary = match_def.get("summary")
        if new_summary and (not current_summary or len(current_summary) < 30):
            res = requests.patch(f"{base_url}/api/v1/matters/{muuid}", headers=headers, json={"pro_bono_opportunity_summary": new_summary})
            if res.status_code == 200:
                print("  -> Updated LegalServer pro_bono_opportunity_summary.")

        # 4. Sync Django Matter and populate raw_payload with case documents and notes
        django_matter = Matter.objects.filter(external_id=mno).first()
        if not django_matter:
            django_matter = Matter.objects.filter(client_name__icontains=name.split()[0]).first() if name else None

        if django_matter:
            print(f"  -> Found Django Matter: {django_matter.external_id}")
            raw = django_matter.raw_payload or {}
            raw.update(m)  # merge LegalServer fields
            if new_summary:
                django_matter.summary = new_summary
            if match_def.get("documents"):
                raw["documents"] = match_def["documents"]
            if match_def.get("summary"):
                raw["case_notes"] = [match_def["summary"]]
            
            django_matter.raw_payload = raw
            django_matter.save()
            print(f"  -> Updated Django Matter {django_matter.external_id} with {len(match_def.get('documents', []))} case documents.")

    print("\nSuccessfully finished populating LegalServer test cases with realistic data!")

if __name__ == "__main__":
    populate()
