"""
Seed data — pre-populate memory_entries with warehouse inventory, routes,
and logistics data so ResourceAgent gets real context from knowledge_lookup.

Run once on startup. Skips if data already exists.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SEED_ENTRIES = [
    # ── Odisha / Bhubaneswar ──────────────────────────────
    {
        "content": (
            "Bhubaneswar Regional Depot inventory as of April 2026: "
            "dry rations 1,200 units, rice 25 MT, wheat 18 MT, tarpaulin 800 sheets, "
            "medical kits 350, water purification tablets 5,000, blankets 1,500. "
            "Cold storage capacity: 40 MT (currently 60% utilized). "
            "Loading dock: 6 bays, can handle 12 trucks/day."
        ),
        "entry_type": "resource",
        "metadata": {"region": "odisha", "depot": "bhubaneswar", "type": "inventory"},
    },
    {
        "content": (
            "Odisha flood zone logistics: Primary route Bhubaneswar to Puri via NH-16 (95 km, ~2h). "
            "Alternate route via NH-59 through Khurda (adds 45 km, ~3.5h). "
            "Cuttack Distribution Center: 15 km from Bhubaneswar, secondary staging point. "
            "Last-mile access to Jagatsinghpur and Kendrapara requires boat transport during heavy flooding."
        ),
        "entry_type": "resource",
        "metadata": {"region": "odisha", "type": "route"},
    },
    {
        "content": (
            "Odisha truck fleet: 8 heavy-duty trucks (10 MT each) at Bhubaneswar depot, "
            "4 medium trucks (5 MT) at Cuttack. Fuel reserve: 3,200 liters diesel. "
            "Driver availability: 14 drivers on roster, 10 active. "
            "GPS tracking active on all vehicles."
        ),
        "entry_type": "resource",
        "metadata": {"region": "odisha", "type": "fleet"},
    },
    {
        "content": (
            "Kolkata backup warehouse: 2,500 units dry rations, 40 MT rice. "
            "Distance to Odisha flood zone: ~450 km via NH-16, 8-10h by road. "
            "Air freight option: Kolkata IAF base to Bhubaneswar, 1.5h flight, "
            "capacity 15 MT per sortie. Cost: 3.2x road transport."
        ),
        "entry_type": "resource",
        "metadata": {"region": "odisha", "depot": "kolkata_backup", "type": "inventory"},
    },

    # ── Chennai ───────────────────────────────────────────
    {
        "content": (
            "Chennai Central Depot inventory: medical supplies 2,100 kits, "
            "emergency shelters 600, bottled water 25,000 liters, "
            "tarpaulin 1,200 sheets, generator sets 8 (5 kW each). "
            "Warehouse capacity: 500 MT. Cold chain for vaccines: 2 MT."
        ),
        "entry_type": "resource",
        "metadata": {"region": "chennai", "depot": "chennai_central", "type": "inventory"},
    },
    {
        "content": (
            "Chennai coastal logistics: Primary staging at Vellore (130 km inland, safe from storm surge). "
            "Route Chennai to Vellore via NH-48 (~2.5h). "
            "Bangalore backup depot: 350 km via NH-44 (~6h). "
            "Marina Beach to Neelankarai coastal belt: last-mile requires 4x4 vehicles post-cyclone."
        ),
        "entry_type": "resource",
        "metadata": {"region": "chennai", "type": "route"},
    },
    {
        "content": (
            "Tamil Nadu fleet allocation: 12 trucks at Chennai depot (mix of 10 MT and 5 MT), "
            "6 ambulances on standby. Fuel: 4,500 liters. "
            "Helicopter access: IAF Tambaram base, 2 Mi-17 available for emergency airlift."
        ),
        "entry_type": "resource",
        "metadata": {"region": "chennai", "type": "fleet"},
    },

    # ── Gujarat ───────────────────────────────────────────
    {
        "content": (
            "Ahmedabad Emergency Depot: emergency shelters 900, blankets 3,000, "
            "water 40,000 liters, dry rations 800 units, medical kits 500. "
            "Bhuj sub-depot: shelters 200, water 8,000 liters (closer to Kutch seismic zone). "
            "Total warehouse capacity: 300 MT across both locations."
        ),
        "entry_type": "resource",
        "metadata": {"region": "gujarat", "depot": "ahmedabad", "type": "inventory"},
    },
    {
        "content": (
            "Gujarat earthquake response routes: Ahmedabad to Bhuj 330 km via NH-27 (~5.5h). "
            "Ahmedabad to Rajkot 215 km (~3.5h). "
            "Risk: NH-27 bridge at Samakhiali is seismically vulnerable. "
            "Alternate: via Surendranagar adds 60 km but avoids bridge."
        ),
        "entry_type": "resource",
        "metadata": {"region": "gujarat", "type": "route"},
    },

    # ── Rajasthan ─────────────────────────────────────────
    {
        "content": (
            "Jaipur Central Water Reserve: 120,000 liters potable water, "
            "200 water tankers (5,000 liters each) on contract. "
            "Jodhpur sub-depot: 50,000 liters, 80 tankers. "
            "Barmer forward base: 15,000 liters (drought-prone tehsils). "
            "Total daily distribution capacity: 400,000 liters."
        ),
        "entry_type": "resource",
        "metadata": {"region": "rajasthan", "depot": "jaipur", "type": "inventory"},
    },
    {
        "content": (
            "Rajasthan drought logistics: Jaipur to Barmer 590 km via NH-15 (~9h). "
            "Jaipur to Jaisalmer 560 km (~8.5h). "
            "Water train: Western Railway runs special rakes, 50,000 liters per rake, "
            "Jaipur to Barmer in 12h. Cost-effective for bulk transport."
        ),
        "entry_type": "resource",
        "metadata": {"region": "rajasthan", "type": "route"},
    },

    # ── Uttarakhand ───────────────────────────────────────
    {
        "content": (
            "Dehradun Emergency Depot: dry rations 500 units, medical kits 200, "
            "tents 150, blankets 800, rope/rescue gear 50 sets. "
            "Rishikesh forward staging: rations 120, medical 80. "
            "Mule train capacity: 2 MT per convoy for mountain last-mile."
        ),
        "entry_type": "resource",
        "metadata": {"region": "uttarakhand", "depot": "dehradun", "type": "inventory"},
    },
    {
        "content": (
            "Uttarakhand mountain routes: Dehradun to Kedarnath 250 km (~10h, road + trek). "
            "NH-10 Rishikesh-Joshimath is landslide-prone during monsoon. "
            "Alternate: airlift from Jolly Grant Airport to Gauchar airstrip (40 min). "
            "BRO maintains alternate paths, status updates via radio check."
        ),
        "entry_type": "resource",
        "metadata": {"region": "uttarakhand", "type": "route"},
    },

    # ── Mumbai ────────────────────────────────────────────
    {
        "content": (
            "Mumbai Central Warehouse: rice 150 MT, wheat 80 MT, "
            "cooking oil 20,000 liters, sugar 30 MT, dal 25 MT. "
            "Routine restock cycle: weekly from Navi Mumbai grain terminal. "
            "Current fill: 72% capacity. Next scheduled restock: Thursday."
        ),
        "entry_type": "resource",
        "metadata": {"region": "mumbai", "depot": "mumbai_central", "type": "inventory"},
    },
    {
        "content": (
            "Mumbai logistics network: Navi Mumbai grain terminal to Central Warehouse 35 km (~1.5h). "
            "JNPT port for bulk imports. Western Express Highway for north-bound distribution. "
            "Fleet: 20 trucks, 8 refrigerated vans. Fuel depot on-site, 10,000 liters."
        ),
        "entry_type": "resource",
        "metadata": {"region": "mumbai", "type": "route"},
    },

    # ── Cross-cutting: disaster history ───────────────────
    {
        "content": (
            "Historical response times: Odisha Cyclone Fani (2019) — 72h to full deployment. "
            "Chennai floods (2015) — 48h first response, 5 days full coverage. "
            "Gujarat earthquake (2001) — 24h military response, 96h civilian logistics. "
            "Key lesson: pre-positioning within 200 km cuts response time by 40%."
        ),
        "entry_type": "context",
        "metadata": {"type": "historical"},
    },
    {
        "content": (
            "Standard operating procedure: crisis severity thresholds — "
            "Critical (>300 units demand): activate all depots + backup + airlift. "
            "Moderate (100-300 units): primary depot + one backup. "
            "Low (<100 units): primary depot only, standard dispatch. "
            "All dispatches require GPS tracking confirmation within 30 min of departure."
        ),
        "entry_type": "context",
        "metadata": {"type": "sop"},
    },
]


async def seed_knowledge_base() -> int:
    """Insert seed data into memory_entries with vector embeddings.

    Uses Gemini embedding model for semantic search via pgvector.
    Skips if data already exists. Returns number of entries inserted.
    """
    from app.db.database import async_session_factory
    from app.db.models import MemoryEntry
    from app.db.repositories import MemoryRepository

    async with async_session_factory() as session:
        repo = MemoryRepository(session)

        existing = await repo.search("Bhubaneswar Regional Depot inventory", limit=1)
        if existing:
            logger.info(f"[seed] Knowledge base already seeded")
            return 0

        # Generate embeddings for all entries
        embeddings = []
        try:
            from app.llm.embeddings import generate_embedding
            logger.info(f"[seed] Generating embeddings for {len(SEED_ENTRIES)} entries...")
            for entry in SEED_ENTRIES:
                emb = await generate_embedding(entry["content"][:500])
                embeddings.append(emb)
            logger.info(f"[seed] Embeddings generated successfully")
        except Exception as e:
            logger.warning(f"[seed] Embedding generation failed: {e}, seeding without vectors")
            embeddings = [None] * len(SEED_ENTRIES)

        count = 0
        for i, entry in enumerate(SEED_ENTRIES):
            mem = MemoryEntry(
                content=entry["content"],
                entry_type=entry["entry_type"],
                metadata_=entry.get("metadata"),
                embedding=embeddings[i],
            )
            session.add(mem)
            count += 1

        await session.commit()
        logger.info(f"[seed] Inserted {count} knowledge base entries with embeddings")
        return count
