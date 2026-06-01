"""
simulate_pos.py

Generates realistic Point-of-Sale (POS) dummy transactions to populate the dashboard's
Conversion Funnel.

It works by scanning the database for recent 'BILLING_QUEUE_JOIN' events and,
for 70% of them (simulating a 70% billing queue conversion rate), generating
a mock transaction timestamped 1-3 minutes after they joined the queue.
"""

import asyncio
import random
import uuid
from datetime import timedelta

import asyncpg

from app.database import DatabaseSettings


async def main():
    settings = DatabaseSettings()
    dsn = (
        f"postgresql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}"
        f"/{settings.db_name}"
    )

    print(f"Connecting to database at {settings.db_host}...")
    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:
        print(f"Failed to connect to the database: {e}")
        print("Please ensure your PostgreSQL database (or Docker container) is running.")
        return

    print("Fetching visitors who joined the billing queue...")
    
    # Get recent unique visitors who entered the billing queue, and their earliest join time
    queue_events = await conn.fetch(
        """
        SELECT visitor_id, MIN(timestamp) as join_time 
        FROM events 
        WHERE event_type = 'BILLING_QUEUE_JOIN'
        GROUP BY visitor_id
        """
    )

    if not queue_events:
        print("No billing queue events found. Run the detection pipeline first to generate CCTV events.")
        await conn.close()
        return

    products = [
        ("SKU-100", "Purplle Matte Lipstick", "Purplle", "Makeup", "Lips", 499.0),
        ("SKU-205", "Hydrating Face Serum", "Good Vibes", "Skincare", "Face", 350.0),
        ("SKU-312", "Charcoal Face Wash", "Faces Canada", "Skincare", "Face", 250.0),
        ("SKU-440", "Volumizing Mascara", "Maybelline", "Makeup", "Eyes", 550.0),
        ("SKU-501", "SPF 50 Sunscreen", "DermDoc", "Skincare", "Suncare", 400.0)
    ]

    inserted_count = 0

    for event in queue_events:
        visitor_id = event["visitor_id"]
        join_time = event["join_time"]

        # Only 70% of people in the queue actually complete a purchase (30% drop-off)
        if random.random() > 0.70:
            continue
            
        # Simulate them checking out 1 to 3 minutes after joining the queue
        checkout_delay = timedelta(seconds=random.randint(60, 180))
        checkout_time = join_time + checkout_delay

        # Pick 1-3 random products
        num_items = random.randint(1, 3)
        cart = random.sample(products, num_items)
        
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        invoice = f"INV-{random.randint(10000, 99999)}"

        for item in cart:
            sku, prod_name, brand, dept, subcat, price = item
            
            await conn.execute(
                """
                INSERT INTO pos_transactions (
                    order_id, invoice_number, store_id, order_date, order_time,
                    timestamp, customer_name, sku, product_name, brand_name,
                    department, sub_category, qty, gmv, nmv, total_amount,
                    salesperson_id, salesperson_name
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18
                )
                """,
                order_id,
                invoice,
                "ST1008",
                checkout_time.date(),
                checkout_time.time(),
                checkout_time,
                f"Customer_{visitor_id[-4:]}",
                sku,
                prod_name,
                brand,
                dept,
                subcat,
                1,
                price,
                price,
                price,
                "EMP-01",
                "Store Cashier"
            )
        inserted_count += 1

    await conn.close()
    print(f"Success! Generated POS transactions for {inserted_count} visitors.")
    print("Refresh your dashboard to see the populated Conversion Funnel and Drop-off stats.")

if __name__ == "__main__":
    asyncio.run(main())
