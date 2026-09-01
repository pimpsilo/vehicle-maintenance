from typing import Dict, Any, List
from sqlmodel import Session, select
from app.models.vehicle import Vehicle
from app.models.consumable import ConsumableSpecification
from app.models.reference_doc import ReferenceDocument
from app.models.vehicle_knowledge import VehicleKnowledge, KnowledgeCategory, ComponentSystem, SeverityLevel
from app.services.nhtsa_service import NHTSAService
from app.services.community_crawler import CommunityCrawler

class FleetIntelligenceService:
    @staticmethod
    def auto_discover_vehicle(session: Session, vehicle_id: int) -> Dict[str, Any]:
        """
        Executes multi-source fleet intelligence & auto-discovery for a specific vehicle:
        1. Decodes VIN (NHTSA VPIC).
        2. Scans open safety recalls (NHTSA Recalls API).
        3. Mines enthusiast forums, Reddit, and YouTube DIY guides.
        4. Auto-populates Consumables, Reference Manuals, and Knowledge Quirks in SQLite.
        """
        vehicle = session.get(Vehicle, vehicle_id)
        if not vehicle:
            return {"success": False, "message": "Vehicle not found."}

        vin_data = NHTSAService.decode_vin(vehicle.vin)
        recalls = NHTSAService.get_recalls_by_vin(vehicle.vin)

        # Update vehicle trim / engine specs if discovered and not already set
        if vin_data.get("trim") and not vehicle.trim:
            vehicle.trim = vin_data["trim"]
        if vin_data.get("engine_summary"):
            notes_append = f"Engine: {vin_data['engine_summary']}"
            if not vehicle.notes:
                vehicle.notes = notes_append
            elif notes_append not in vehicle.notes:
                vehicle.notes += f" | {notes_append}"
        
        session.add(vehicle)

        # Match technical & community profile
        profile = CommunityCrawler.match_knowledge_profile(
            make=vehicle.make,
            model=vehicle.model,
            engine_desc=vin_data.get("engine_summary") or "",
            trim=vehicle.trim or ""
        )

        counts = {
            "consumables_added": 0,
            "guides_added": 0,
            "quirks_added": 0,
            "recalls_found": len(recalls)
        }

        # 1. Populate Consumables
        existing_consumables = session.exec(
            select(ConsumableSpecification).where(ConsumableSpecification.vehicle_id == vehicle.id)
        ).all()
        existing_categories = {c.category for c in existing_consumables}

        for spec in profile.get("consumables", []):
            if spec["category"] not in existing_categories:
                new_c = ConsumableSpecification(
                    vehicle_id=vehicle.id,
                    category=spec["category"],
                    item_name=spec["item_name"],
                    specification=spec["specification"],
                    oem_part_number=spec.get("oem_part_number"),
                    aftermarket_alternatives=spec.get("aftermarket_alternatives"),
                    replacement_interval_summary=spec.get("replacement_interval_summary"),
                )
                session.add(new_c)
                counts["consumables_added"] += 1

        # 2. Populate DIY Guides & Manuals
        existing_guides = session.exec(
            select(ReferenceDocument).where(ReferenceDocument.vehicle_id == vehicle.id)
        ).all()
        existing_guide_titles = {g.title.lower() for g in existing_guides}

        for g in profile.get("guides", []):
            if g["title"].lower() not in existing_guide_titles:
                new_g = ReferenceDocument(
                    vehicle_id=vehicle.id,
                    title=g["title"],
                    doc_category=g.get("doc_category"),
                    difficulty=g.get("difficulty"),
                    source_name_or_url=g.get("source_name_or_url", "Community Forums"),
                    tools_required=g.get("tools_required"),
                    estimated_hours=g.get("estimated_hours"),
                    step_by_step_instructions=g["step_by_step_instructions"],
                    early_service_community_tips=g.get("early_service_community_tips"),
                    tags=g.get("tags"),
                )
                session.add(new_g)
                counts["guides_added"] += 1

        # 3. Populate Community Quirks & Knowledge
        existing_quirks = session.exec(
            select(VehicleKnowledge).where(VehicleKnowledge.vehicle_id == vehicle.id)
        ).all()
        existing_quirk_titles = {q.title.lower() for q in existing_quirks}

        for q in profile.get("quirks", []):
            if q["title"].lower() not in existing_quirk_titles:
                new_q = VehicleKnowledge(
                    vehicle_id=vehicle.id,
                    title=q["title"],
                    category=q.get("category", KnowledgeCategory.KNOWN_QUIRK),
                    component_system=q.get("component_system", ComponentSystem.ENGINE),
                    severity=q.get("severity", SeverityLevel.WATCH_ITEM),
                    description=q["description"],
                    recommended_action=q.get("recommended_action"),
                )
                session.add(new_q)
                counts["quirks_added"] += 1

        # 4. If recalls exist, add them as HIGH SEVERITY knowledge entries
        for r in recalls:
            recall_title = f"NHTSA Safety Recall #{r['campaign_number']}: {r['component']}"
            if recall_title.lower() not in existing_quirk_titles:
                recall_q = VehicleKnowledge(
                    vehicle_id=vehicle.id,
                    title=recall_title,
                    category=KnowledgeCategory.COMMON_FAILURE_POINT,
                    component_system=ComponentSystem.GENERAL,
                    severity=SeverityLevel.CRITICAL_REPAIR,
                    description=f"NHTSA Campaign: {r['campaign_number']}\nComponent: {r['component']}\n\nSummary:\n{r['summary']}",
                    recommended_action=f"Remedy: {r['remedy']}\nCheck with authorized dealer for free recall repair.",
                )
                session.add(recall_q)
                counts["quirks_added"] += 1

        session.commit()
        session.refresh(vehicle)

        youtube_links = CommunityCrawler.generate_youtube_repair_links(
            year=vehicle.year,
            make=vehicle.make,
            model=vehicle.model,
            engine_desc=vin_data.get("engine_summary") or ""
        )
        forum_sources = CommunityCrawler.generate_forum_sources(vehicle.make, vehicle.model)

        return {
            "success": True,
            "vehicle_id": vehicle.id,
            "vehicle_name": f"{vehicle.year} {vehicle.make} {vehicle.model}",
            "vin": vehicle.vin,
            "decoded_specs": vin_data,
            "recalls": recalls,
            "counts": counts,
            "community_sources": {
                "youtube_guides": youtube_links,
                "forums": forum_sources,
            }
        }
