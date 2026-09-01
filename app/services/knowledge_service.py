from typing import List, Optional
from sqlmodel import Session, select, or_
from app.models.reference_doc import ReferenceDocument, DocCategory, DifficultyRating
from app.models.vehicle_knowledge import (
    VehicleKnowledge,
    KnowledgeCategory,
    ComponentSystem,
    SeverityLevel,
)

class KnowledgeService:
    @staticmethod
    def search_reference_docs(
        session: Session,
        query: Optional[str] = None,
        vehicle_id: Optional[int] = None,
        category: Optional[DocCategory] = None,
        difficulty: Optional[DifficultyRating] = None,
    ) -> List[ReferenceDocument]:
        stmt = select(ReferenceDocument)

        if vehicle_id is not None:
            stmt = stmt.where(or_(ReferenceDocument.vehicle_id == vehicle_id, ReferenceDocument.vehicle_id == None))  # noqa: E711
        if category is not None:
            stmt = stmt.where(ReferenceDocument.doc_category == category)
        if difficulty is not None:
            stmt = stmt.where(ReferenceDocument.difficulty == difficulty)

        if query:
            search_pattern = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    ReferenceDocument.title.ilike(search_pattern),
                    ReferenceDocument.step_by_step_instructions.ilike(search_pattern),
                    ReferenceDocument.early_service_community_tips.ilike(search_pattern),
                    ReferenceDocument.tags.ilike(search_pattern),
                    ReferenceDocument.tools_required.ilike(search_pattern),
                )
            )

        return session.exec(stmt.order_by(ReferenceDocument.created_at.desc())).all()

    @staticmethod
    def search_vehicle_knowledge(
        session: Session,
        query: Optional[str] = None,
        vehicle_id: Optional[int] = None,
        category: Optional[KnowledgeCategory] = None,
        component_system: Optional[ComponentSystem] = None,
        severity: Optional[SeverityLevel] = None,
    ) -> List[VehicleKnowledge]:
        stmt = select(VehicleKnowledge)

        if vehicle_id is not None:
            stmt = stmt.where(or_(VehicleKnowledge.vehicle_id == vehicle_id, VehicleKnowledge.vehicle_id == None))  # noqa: E711
        if category is not None:
            stmt = stmt.where(VehicleKnowledge.category == category)
        if component_system is not None:
            stmt = stmt.where(VehicleKnowledge.component_system == component_system)
        if severity is not None:
            stmt = stmt.where(VehicleKnowledge.severity == severity)

        if query:
            search_pattern = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    VehicleKnowledge.title.ilike(search_pattern),
                    VehicleKnowledge.description.ilike(search_pattern),
                    VehicleKnowledge.real_world_data.ilike(search_pattern),
                    VehicleKnowledge.recommended_action.ilike(search_pattern),
                )
            )

        return session.exec(stmt.order_by(VehicleKnowledge.created_at.desc())).all()
