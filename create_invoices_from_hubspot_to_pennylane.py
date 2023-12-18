from datetime import date, timedelta
import json
import hubspot
import requests
import os
from hubspot.crm.companies import SimplePublicObjectInput

# Initialization for local usage
hubspot_access_token = os.getenv('hunteo_hubspot')

client = hubspot.Client(access_token=hubspot_access_token)

input_deal_id = "10007002325"
deal = client.crm.deals.basic_api.get_by_id(
    deal_id=input_deal_id, 
    properties=
    [
        "dealname", 
        "hs_object_id", 
        "type_de_facturation", 
        "delai_de_reglement",
        "consultant",
        "quantite_assessment",
        "quantite_d_annonce",
        "montant_de_la_formation",
        "montant_du_conseil",
        "montant_autre_prestation",
        "accompte",
        "d_accompte",
        "montant_du_forfait",
        "montant_des_honoraires_calcules"
        ])
  
event = {
    "inputFields": {
        "dealname": deal.properties["dealname"],
        "hs_object_id": deal.properties["hs_object_id"],
        "type_de_facturation": deal.properties["type_de_facturation"],
        "delai_de_reglement": deal.properties["delai_de_reglement"],
        "consultant": deal.properties["consultant"],
        "quantite_assessment": deal.properties["quantite_assessment"],
        "quantite_d_annonce": deal.properties["quantite_d_annonce"],
        "montant_de_la_formation": deal.properties["montant_de_la_formation"],
        "montant_du_conseil": deal.properties["montant_du_conseil"],
        "montant_autre_prestation": deal.properties["montant_autre_prestation"],
        "accompte": deal.properties["accompte"],
        "d_accompte": deal.properties["d_accompte"],
        "montant_du_forfait": deal.properties["montant_du_forfait"],
        "montant_des_honoraires_calcules": deal.properties["montant_des_honoraires_calcules"]
    }
}

# End of ininitialization for local usage

client = hubspot.Client(access_token=os.getenv('hubspot_private_app_token'))
pennylane_token = os.getenv('hunteo_pennylane')

headers = { "Authorization": "Bearer " + pennylane_token, "accept": "application/json", "content-type": "application/json" }

# deal infos
deal_name = event["inputFields"]["dealname"]
deal_id = event["inputFields"]["hs_object_id"]
billing_type = event["inputFields"]["type_de_facturation"]
payment_term = event["inputFields"]["delai_de_reglement"]
consultantTrigram = event["inputFields"]["consultant"]
data = client.crm.properties.core_api.get_by_name(object_type="deal", property_name="consultant", archived=False)
consultantNameList = data.options
consultantName = ""

for item in consultantNameList:
    if item.value == consultantTrigram:
        consultantName = item.label

# options
amount_assesment = int(event["inputFields"]["quantite_assessment"])
amount_announce = int(event["inputFields"]["quantite_d_annonce"])
amount_training = int(event["inputFields"]["montant_de_la_formation"])
amount_consulting = int(event["inputFields"]["montant_du_conseil"])
amount_other_delivery = int(event["inputFields"]["montant_autre_prestation"])

# Acompte
deposit_percentage = 0
if (event["inputFields"]["accompte"] == "Oui"):
    deposit = True
    deposit_percentage = float(event["inputFields"]["d_accompte"])
else:
    deposit = False

# Forfait
amount_plan = int(event["inputFields"]["montant_du_forfait"])

# %
amount_percentage = int(event["inputFields"]["montant_des_honoraires_calcules"])

today = date.today()
pennylane_customer_id = None

invoice_payloads = []
line_items_deposit_invoice = []
line_items_last_invoice = []

payment_terms_conversion = {
    "30 jours": 30,
    "45 jours": 45,
    "60 jours": 60,
    "90 jours": 90
}

# client
companiesResponse = client.crm.deals.associations_api.get_all(deal_id=deal_id, to_object_type="companies")

companiesAssociatedList = companiesResponse.results

companyId = companiesAssociatedList[0].to_object_id

company = client.crm.companies.basic_api.get_by_id(
    companyId, 
    properties = [
        "name", 
        "adresse_de_facturation", 
        "code_postal_de_facturation", 
        "ville_de_facturation",
        "destinataire_de_facturation",
        "email_de_facturation",
        "entite_a_facturer",
        "telephone_de_facturation",
        "country", 
        "pennylane_customer_id", 
        "siren"
        ]
    )

pennylane_customer_id = company.properties.get("pennylane_customer_id", "")

if (pennylane_customer_id == "" or pennylane_customer_id == None):
    new_customer = { 
        "customer_type": "company",
        "name": company.properties["entite_a_facturer"],
        "address": company.properties["adresse_de_facturation"],
        "postal_code": company.properties["code_postal_de_facturation"],
        "city": company.properties["ville_de_facturation"],
        "country_alpha2": "FR",
        "source_id": company.id
    }
    if company.properties.get("siren") : new_customer["reg_no"] = company.properties["siren"]
    if company.properties.get("email_de_facturation") : new_customer["emails"] = [ company.properties["email_de_facturation"] ]
    if company.properties.get("telephone_de_facturation") : new_customer["phone"] = company.properties["telephone_de_facturation"]
    if company.properties.get("destinataire_de_facturation") : new_customer["recipient"] = "A l'attention de " + str(company.properties["destinataire_de_facturation"])

    url = "https://app.pennylane.com/api/external/v1/customers"
    payload = { "customer": new_customer }
    response = requests.post(url, json=payload, headers=headers)
    print("Create customer response:" + str(response))

    pennylane_customer = json.loads(response.text)
    pennylane_customer_id = pennylane_customer["customer"]["source_id"]
    simple_public_object_input = SimplePublicObjectInput(
        properties={
            "pennylane_customer_id": pennylane_customer_id
        }
    )
    client.crm.companies.basic_api.update(company_id=companyId, simple_public_object_input=simple_public_object_input)
    
print("Customer source_id: " + pennylane_customer_id)

# Lignes produits
line_item_recruitment_deposit = {
    "quantity": 1
}

line_item_recruitment_last_invoice = {
    "quantity": 1
}

if (deposit):
    recruitement_amount_deposit = 0.0
    if (billing_type == "Forfait"):
        recruitement_amount_deposit = round((amount_plan * ( deposit_percentage / 100 )) * 1.2)
    if (billing_type == "%"):
        recruitement_amount_deposit = round(amount_percentage * (deposit_percentage / 100) * 1.2)
    line_item_recruitment_deposit["label"] = "Prestation de recrutement - Acompte"
    line_item_recruitment_deposit["product"] = {
        "source_id": "recrutement",
        "price": recruitement_amount_deposit,
        "vat_rate": "FR_200"
    }
    line_items_deposit_invoice.append(line_item_recruitment_deposit)

recruitement_amount = 0.0
if (billing_type == "Forfait"):
    recruitment_amount = round((amount_plan * ( (100 - deposit_percentage) / 100 )) * 1.2)
if (billing_type == "%"):
    recruitment_amount = round(amount_percentage * ((100 - deposit_percentage) / 100 ) * 1.2)
line_item_recruitment_last_invoice["label"] = "Prestation de recrutement - Solde"
line_item_recruitment_last_invoice["product"] = {
        "source_id": "recrutement",
        "price": recruitment_amount,
        "vat_rate": "FR_200"
    }
line_items_last_invoice.append(line_item_recruitment_last_invoice)

# Options de service
if (amount_assesment > 0):    
    assesment_line_item = {
        "quantity": 1,
        "section_rank": 2,
        "label": "Assesment",
        "product": {
            "source_id": "assesment",
            "price": round(amount_assesment * 1.2),
            "vat_rate": "FR_200"
        }
    }
    line_items_last_invoice.append(assesment_line_item)

if (amount_announce > 0):
    announce_line_item = {
        "quantity": 1,
        "section_rank": 3,
        "label": "Publication d'annonces",
        "product": {
            "source_id": "annonces",
            "price": round(amount_announce * 1.2),
            "vat_rate": "FR_200"
        }
    }
    line_items_deposit_invoice.append(announce_line_item)

if (amount_consulting > 0):
    consulting_line_item = {
        "quantity": 1,
        "section_rank": 3,
        "label": "Conseil",
        "product": {
            "source_id": "conseil",
            "price": round(amount_consulting * 1.2),
            "vat_rate": "FR_200"
        }
    }
    line_items_last_invoice.append(consulting_line_item)

if (amount_training > 0):
    training_line_item = {
        "quantity": 1,
        "section_rank": 3,
        "label": "Formation",
        "product": {
            "source_id": "formation",
            "price": round(amount_training * 1.2),
            "vat_rate": "FR_200"
        }
    }
    line_items_last_invoice.append(training_line_item)

if (amount_other_delivery > 0):
    other_delivery_line_item = {
        "quantity": 1,
        "section_rank": 4,
        "label": "Autres prestations",
        "product": {
            "source_id": "autres_prestations",
            "price": round(amount_other_delivery * 1.2),
            "vat_rate": "FR_200"
        }
    }
    line_items_last_invoice.append(other_delivery_line_item)

invoice_deposit_payload = {}

deposit_details = "Consultant : " + consultantName

invoice_subject_prefix = (consultantTrigram + " - " + deal_name)[:40]

# Si facture d'acompte
if (deposit):
    invoice_deposit_payload = {
        "create_customer": False,
        "create_products": True,
        "update_customer": True,
        "invoice": {
            "pdf_invoice_subject": invoice_subject_prefix + " - Acompte",
            "pdf_invoice_free_text": deposit_details,
            "special_mention": "Numéro de transaction : " + deal_id,
            "date": today.isoformat(),
            "deadline": (today + timedelta(days = payment_terms_conversion[payment_term])).isoformat(),
            "draft": True,
            "customer": { "source_id": pennylane_customer_id },
            "line_items": line_items_deposit_invoice
        }
    }

if(deposit):
    deposit_details_amount = 0
    for line_item in line_items_deposit_invoice:
        deposit_details_amount = deposit_details_amount + line_item['product']['price']
    deposit_details = deposit_details + "\nDéjà réglé : " + str(deposit_details_amount) + "€TTC"

invoice_main_payload = {
        "create_customer": False,
        "create_products": True,
        "update_customer": True,
        "invoice": {
            "pdf_invoice_subject": invoice_subject_prefix + " - Solde",
            "pdf_invoice_free_text": deposit_details,
            "special_mention": "Numéro de transaction : " + deal_id,
            "date": today.isoformat(),
            "deadline": (today + timedelta(days = payment_terms_conversion[payment_term] + 30)).isoformat(),
            "draft": True,
            "customer": { "source_id": pennylane_customer_id },
            "line_items": line_items_last_invoice
        }
}

create_invoice_url = "https://app.pennylane.com/api/external/v1/customer_invoices"

json_object = json.dumps(invoice_deposit_payload)

if (deposit): deposit_response = requests.post(create_invoice_url, json=invoice_deposit_payload, headers=headers)
last_invoice_response = requests.post(create_invoice_url, json=invoice_main_payload, headers=headers)

last_invoice_reponse_json = json.loads(last_invoice_response.text)
print(last_invoice_reponse_json)
