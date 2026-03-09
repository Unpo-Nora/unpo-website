import sys
from datetime import datetime
from app.database import SessionLocal
from app.models import Lead, SaleOrder, OrderItem, LeadStatus, SaleOrderStatus

db = SessionLocal()

clients_data = [
    {
        "lead": {
            "full_name": "Vanina Armeli",
            "phone": "541137697020",
            "email": "vaninaarmeli@gmail.com",
            "address": "Avenida Capitan Claudio Rosales 1372",
            "locality": "El Palomar",
            "province": "Buenos Aires",
            "zip_code": "1684",
            "product_interest": "Bazar",
            "status": LeadStatus.CLIENT,
            "seller": "julianv@unpo.com.ar",
            "lead_date": datetime(2025, 12, 1)
        },
        "orders": [
            {
                "created_at": datetime(2026, 2, 1),
                "status": SaleOrderStatus.COMPLETED,
                "total_amount": 110999.98,
                "items": [
                    {"sku": "10300026", "quantity": 4, "unit_price": 2894.00},
                    {"sku": "10300029", "quantity": 1, "unit_price": 9777.60},
                    {"sku": "10300016", "quantity": 2, "unit_price": 3064.23},
                    {"sku": "10300027", "quantity": 2, "unit_price": 4944.89},
                    {"sku": "10300030", "quantity": 4, "unit_price": 2077.74},
                    {"sku": "10300031", "quantity": 4, "unit_price": 2413.85},
                    {"sku": "10300033", "quantity": 2, "unit_price": 4539.25},
                    {"sku": "10300040", "quantity": 2, "unit_price": 12571.20},
                    {"sku": "10300014", "quantity": 2, "unit_price": 2566.62},
                    {"sku": "10300013", "quantity": 2, "unit_price": 2566.62},
                    {"sku": "10300068", "quantity": 1, "unit_price": 11174.40}
                ]
            },
            {
                "created_at": datetime(2026, 2, 10),
                "status": SaleOrderStatus.COMPLETED,
                "total_amount": 151124.04,
                "items": [
                    {"sku": "10300026", "quantity": 4, "unit_price": 2894.00},
                    {"sku": "10300016", "quantity": 4, "unit_price": 3064.23},
                    {"sku": "10300027", "quantity": 1, "unit_price": 4944.89},
                    {"sku": "10300015", "quantity": 2, "unit_price": 2894.00},
                    {"sku": "10600018", "quantity": 2, "unit_price": 2612.63},
                    {"sku": "10300033", "quantity": 2, "unit_price": 4539.25},
                    {"sku": "10300040", "quantity": 2, "unit_price": 12571.20},
                    {"sku": "10300020", "quantity": 1, "unit_price": 5729.06},
                    {"sku": "10300028", "quantity": 5, "unit_price": 2681.25},
                    {"sku": "10300070", "quantity": 1, "unit_price": 11174.40},
                    {"sku": "10300071", "quantity": 1, "unit_price": 11174.40},
                    {"sku": "10900079", "quantity": 1, "unit_price": 16813.98},
                    {"sku": "10900080", "quantity": 1, "unit_price": 16813.98},
                    {"sku": "10700085", "quantity": 10, "unit_price": 200.00}
                ]
            }
        ]
    },
    {
        "lead": {
            "full_name": "Debora Romina Pereyra",
            "dni_cuit": "32554310",
            "phone": "541160342974",
            "email": "deborapereyra@gmail.com",
            "address": "Avenida de Mayo 783",
            "locality": "Ramos Mejía",
            "province": "Buenos Aires",
            "zip_code": "1704",
            "product_interest": "Bebe",
            "status": LeadStatus.CLIENT,
            "seller": "julianv@unpo.com.ar",
            "lead_date": datetime(2026, 1, 15)
        },
        "orders": [
            {
                "created_at": datetime(2026, 1, 20),
                "status": SaleOrderStatus.COMPLETED,
                "total_amount": 100884.00,
                "items": [
                    {"sku": "10900081", "quantity": 7, "unit_price": 14412.00}
                ]
            }
        ]
    },
    {
        "lead": {
            "full_name": "Juan Pedro Stefanello",
            "phone": "541123457257",
            "email": "juanpstefanello@hotmail.com",
            "address": "Pasaje Marcos seguin 2550",
            "locality": "CABA",
            "province": "Buenos Aires",
            "zip_code": "1400",
            "product_interest": "Humidificadores",
            "status": LeadStatus.CLIENT,
            "seller": "julianv@unpo.com.ar",
            "lead_date": datetime(2026, 1, 10)
        },
        "orders": [
            {
                "created_at": datetime(2026, 1, 25),
                "status": SaleOrderStatus.COMPLETED,
                "total_amount": 18720594.54,
                "items": [
                    {"sku": "20600041", "quantity": 194, "unit_price": 7944.30},
                    {"sku": "20600042", "quantity": 224, "unit_price": 7944.30},
                    {"sku": "20600043", "quantity": 248, "unit_price": 8860.95},
                    {"sku": "20600044", "quantity": 234, "unit_price": 8860.95},
                    {"sku": "20600046", "quantity": 146, "unit_price": 13793.40},
                    {"sku": "20600047", "quantity": 206, "unit_price": 13793.40},
                    {"sku": "20600045", "quantity": 231, "unit_price": 10388.70},
                    {"sku": "20600050", "quantity": 11, "unit_price": 13601.34},
                    {"sku": "20600049", "quantity": 316, "unit_price": 11785.50}
                ]
            }
        ]
    }
]

for cd in clients_data:
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
            existing_lead.seller = lead_data['seller']
            db.commit()
            print(f"Lead already exists: {lead.full_name} (ID: {lead.id})")

        for order_data in cd['orders']:
            existing_order = db.query(SaleOrder).filter(
                SaleOrder.lead_id == lead.id,
                SaleOrder.total_amount == order_data['total_amount']
            ).first()

            if not existing_order:
                new_order = SaleOrder(
                    lead_id=lead.id,
                    created_at=order_data['created_at'],
                    status=order_data['status'],
                    total_amount=order_data['total_amount']
                )
                db.add(new_order)
                db.commit()
                db.refresh(new_order)

                for item_data in order_data['items']:
                    order_item = OrderItem(
                        order_id=new_order.id,
                        product_sku=item_data['sku'],
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                        total_price=item_data['quantity'] * item_data['unit_price']
                    )
                    db.add(order_item)
                db.commit()
                print(f"Created SaleOrder ID {new_order.id} for Lead {lead.full_name} ({order_data['total_amount']})")
            else:
                print(f"SaleOrder already exists for Lead {lead.full_name} ({order_data['total_amount']})")
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()

db.close()
