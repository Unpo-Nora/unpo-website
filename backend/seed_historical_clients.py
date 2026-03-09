import sys
from datetime import datetime
from app.database import SessionLocal
from app.models import Lead, SaleOrder, OrderItem, LeadStatus, SaleOrderStatus
import traceback

db = SessionLocal()

clients_data = [
    {
        "lead": {
            "full_name": "Leonardo Abalsamo",
            "phone": "5491164601440",
            "email": "leonardodanielabalsamo@gmail.com",
            "address": "Gral Posadas 2653",
            "locality": "Ituzaingo",
            "province": "Buenos Aires",
            "zip_code": "1714",
            "product_interest": "bazar principalmente",
            "status": LeadStatus.CLIENT,
            "lead_date": datetime(2025, 11, 24)
        },
        "order": {
            "created_at": datetime(2026, 1, 31),
            "status": SaleOrderStatus.COMPLETED,
            "total_amount": 361422.00,
            "items": [
                {"sku": "20600041", "quantity": 10, "unit_price": 8076.71}, # PIPE CLARO
                {"sku": "20600042", "quantity": 10, "unit_price": 8076.71}, # PIPE OSCURO
                {"sku": "10300013", "quantity": 10, "unit_price": 2994.39}, # DISPENSER BLANCO
                {"sku": "10300014", "quantity": 10, "unit_price": 2994.39}, # DISPENSER NEGRO
                {"sku": "20600043", "quantity": 5, "unit_price": 9000.00},  # LONG NECK CLARO
                {"sku": "20600044", "quantity": 5, "unit_price": 9000.00},  # LONG NECK OSCURO
                {"sku": "20600045", "quantity": 5, "unit_price": 10000.00}   # MOON 120
            ]
        }
    },
    {
        "lead": {
            "full_name": "Lucrecia Andrea Carino",
            "phone": "542224505765",
            "email": "carinolucrecia@gmail.com",
            "address": "Rodolfo whash 453",
            "locality": "San Vicente",
            "province": "Buenos Aires",
            "zip_code": "1865",
            "product_interest": "humidificador",
            "status": LeadStatus.CLIENT,
            "lead_date": datetime(2026, 1, 16)
        },
        "order": {
            "created_at": datetime(2026, 1, 16),
            "status": SaleOrderStatus.COMPLETED,
            "total_amount": 137600.00,
            "items": [
                {"sku": "10200007", "quantity": 43, "unit_price": 3200.00} # PELOTA 150
            ]
        }
    },
    {
        "lead": {
            "full_name": "Marcela Alejandra Matias",
            "dni_cuit": "21649021",
            "phone": "542246587360",
            "email": "matiasmarcelaalejan@gmail.com",
            "address": "Calle 36 número 684",
            "locality": "Santa Teresita",
            "province": "Buenos Aires",
            "zip_code": "7107",
            "product_interest": "Difusores",
            "status": LeadStatus.CLIENT,
            "lead_date": datetime(2026, 1, 22)
        },
        "order": {
            "created_at": datetime(2026, 1, 22),
            "status": SaleOrderStatus.COMPLETED,
            "total_amount": 311686.26,
            "items": [
                {"sku": "20600041", "quantity": 3, "unit_price": 10592.40}, 
                {"sku": "20600042", "quantity": 3, "unit_price": 10542.40}, 
                {"sku": "20600044", "quantity": 2, "unit_price": 11814.60}, 
                {"sku": "20600044", "quantity": 2, "unit_price": 11814.60}, 
                {"sku": "20600046", "quantity": 3, "unit_price": 18851.20}, 
                {"sku": "10200007", "quantity": 3, "unit_price": 3585.12},  
                {"sku": "20600045", "quantity": 2, "unit_price": 13851.60}, 
                {"sku": "20600049", "quantity": 2, "unit_price": 15714.00}, 
                {"sku": "20600047", "quantity": 1, "unit_price": 19555.20}, 
                {"sku": "20600050", "quantity": 2, "unit_price": 18135.12}, 
                {"sku": "10300015", "quantity": 1, "unit_price": 3858.66},  
                {"sku": "10300070", "quantity": 1, "unit_price": 14899.20}  
            ]
        }
    },
    {
        "lead": {
            "full_name": "Silvana Sonzogni",
            "dni_cuit": "23826529",
            "phone": "543424098755",
            "email": "pupi_soni@hotmail.com",
            "address": "Gualeguaychu 68",
            "locality": "Parana",
            "province": "Entre Rios",
            "zip_code": "3100",
            "product_interest": "En varios",
            "status": LeadStatus.CLIENT,
            "lead_date": datetime(2026, 2, 10)
        },
        "order": {
            "created_at": datetime(2026, 2, 10),
            "status": SaleOrderStatus.COMPLETED,
            "total_amount": 208248.80,
            "items": [
                {"sku": "10300030", "quantity": 10, "unit_price": 2077.74}, 
                {"sku": "10300031", "quantity": 18, "unit_price": 2413.85}, 
                {"sku": "10300014", "quantity": 6, "unit_price": 2566.62},  
                {"sku": "10300013", "quantity": 6, "unit_price": 2566.62},  
                {"sku": "10700075", "quantity": 6, "unit_price": 10537.11}, 
                {"sku": "10300040", "quantity": 5, "unit_price": 10000.00}  
            ]
        }
    }
]

for cd in clients_data:
    print(f"--- STARTING: {cd['lead']['full_name']} ---")
    try:
        lead_data = cd['lead']
        existing_lead = db.query(Lead).filter(Lead.phone == lead_data['phone']).first()
        if not existing_lead:
            lead = Lead(**lead_data)
            db.add(lead)
            db.commit()
            db.refresh(lead)
            print(f"Created Lead: {lead.full_name} (ID: {lead.id})")
        else:
            lead = existing_lead
            existing_lead.status = LeadStatus.CLIENT
            db.commit()
            print(f"Lead already exists: {lead.full_name} (ID: {lead.id})")

        print(f"Checking existing order for lead {lead.id} with amount {cd['order']['total_amount']}")
        existing_order = db.query(SaleOrder).filter(
            SaleOrder.lead_id == lead.id,
            SaleOrder.total_amount == cd['order']['total_amount']
        ).first()

        if not existing_order:
            print("Creating new order...")
            new_order = SaleOrder(
                lead_id=lead.id,
                created_at=cd['order']['created_at'],
                status=cd['order']['status'],
                total_amount=cd['order']['total_amount']
            )
            db.add(new_order)
            db.commit()
            db.refresh(new_order)
            print(f"Added order {new_order.id}, now adding items...")

            for item_data in cd['order']['items']:
                print(f"Adding item SKU {item_data['sku']}")
                order_item = OrderItem(
                    order_id=new_order.id,
                    product_sku=item_data['sku'],
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    total_price=item_data['quantity'] * item_data['unit_price']
                )
                db.add(order_item)
            db.commit()
            print(f"Created SaleOrder ID {new_order.id} for Lead {lead.full_name}")
        else:
            print(f"SaleOrder already exists for Lead {lead.full_name}")
    except Exception as e:
        db.rollback()
        print(f"CRITICAL ERROR processing {cd['lead']['full_name']}:", file=sys.stderr)
        traceback.print_exc()

db.close()
