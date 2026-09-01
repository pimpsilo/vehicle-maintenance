from datetime import date, timedelta
from sqlmodel import Session, select
from app.database import engine, init_db
from app.models.vehicle import Vehicle
from app.models.document import VehicleDocument, DocumentType
from app.models.maintenance import (
    ServiceDefinition,
    ServiceRecord,
    PerformedByType,
)
from app.models.consumable import ConsumableSpecification, ConsumableCategory
from app.models.external_service import (
    ServiceShop,
    ExternalServiceOrder,
    PartSourcing,
    WorkOrderStatus,
    PartOrderStatus,
)
from app.models.reference_doc import (
    ReferenceDocument,
    DocCategory,
    DifficultyRating,
)
from app.models.vehicle_knowledge import (
    VehicleKnowledge,
    KnowledgeCategory,
    ComponentSystem,
    SeverityLevel,
)

def seed_database():
    init_db()
    with Session(engine) as session:
        # Check if already seeded
        existing_vehicle = session.exec(select(Vehicle).where(Vehicle.vin == "4T1BK1EB5EU123456")).first()
        if existing_vehicle:
            print("2014 Toyota Avalon already exists in database.")
            return existing_vehicle.id

        today = date.today()

        # 1. Create Vehicle
        avalon = Vehicle(
            vin="4T1BK1EB5EU123456",
            year=2014,
            make="Toyota",
            model="Avalon",
            trim="XLE Touring 3.5L V6",
            license_plate="7TYT882",
            ezpass_transponder="02214988210",
            current_mileage=105000,
            estimated_annual_mileage=12000,
            purchase_date=today - timedelta(days=1200),
            notes="3.5L 2GR-FE V6 engine, 6-speed automatic transmission. Excellent mechanical condition."
        )
        session.add(avalon)
        session.commit()
        session.refresh(avalon)
        vehicle_id = avalon.id
        print(f"Created vehicle: 2014 Toyota Avalon (ID: {vehicle_id})")

        # 2. Service Definitions (Factory Maintenance Schedules)
        sdef_oil = ServiceDefinition(
            service_name="Engine Oil & Filter Change (0W-20)",
            description="Replace 0W-20 full synthetic engine oil (6.4 US qt) and cartridge filter element.",
            interval_miles=10000,
            interval_months=12,
            is_recurring=True,
            severe_duty_interval_miles=5000,
            severe_duty_interval_months=6,
            category="LUBRICATION"
        )
        sdef_tire = ServiceDefinition(
            service_name="Tire Rotation & Brake Inspection",
            description="Rotate all 4 tires, check tire tread depth, inspect brake pad thickness and slide pins.",
            interval_miles=5000,
            interval_months=6,
            is_recurring=True,
            category="TIRES_BRAKES"
        )
        sdef_filters = ServiceDefinition(
            service_name="Engine Air & Cabin Microfilter Replacement",
            description="Replace pleated engine air intake filter and cabin pollen/carbon microfilter.",
            interval_miles=30000,
            interval_months=36,
            is_recurring=True,
            category="FILTERS"
        )
        sdef_brake_fluid = ServiceDefinition(
            service_name="Brake Fluid Exchange (DOT 3 / DOT 4)",
            description="Full flush and bleed of brake hydraulic fluid to prevent moisture build-up.",
            interval_miles=30000,
            interval_months=36,
            is_recurring=True,
            category="FLUIDS"
        )
        sdef_trans_fluid = ServiceDefinition(
            service_name="Automatic Transmission Fluid Drain & Fill (Toyota WS)",
            description="Drain and fill approximately 2.5 quarts of Toyota Genuine ATF WS with temperature overflow check.",
            interval_miles=60000,
            interval_months=72,
            is_recurring=True,
            category="FLUIDS"
        )
        sdef_spark_plugs = ServiceDefinition(
            service_name="Iridium Spark Plug Replacement (Denso FK20HR11)",
            description="Replace 6 long-life Iridium spark plugs (requires removing upper intake plenum for bank 1 rear plugs).",
            interval_miles=120000,
            interval_months=144,
            is_recurring=False,
            category="IGNITION"
        )

        session.add_all([sdef_oil, sdef_tire, sdef_filters, sdef_brake_fluid, sdef_trans_fluid, sdef_spark_plugs])
        session.commit()
        session.refresh(sdef_oil)
        session.refresh(sdef_tire)
        session.refresh(sdef_filters)
        session.refresh(sdef_brake_fluid)
        session.refresh(sdef_trans_fluid)
        session.refresh(sdef_spark_plugs)

        # 3. Past Completed Service Records
        rec_oil = ServiceRecord(
            vehicle_id=vehicle_id,
            service_definition_id=sdef_oil.id,
            service_name=sdef_oil.service_name,
            completed_date=today - timedelta(days=120),
            completed_mileage=100000,
            performed_by_type=PerformedByType.DIY,
            total_cost=42.50,
            labor_cost=0.0,
            parts_cost=42.50,
            notes="Used Mobil 1 Advanced Fuel Economy 0W-20 and Toyota OEM filter cartridge 04152-YZZA1."
        )
        rec_tire = ServiceRecord(
            vehicle_id=vehicle_id,
            service_definition_id=sdef_tire.id,
            service_name=sdef_tire.service_name,
            completed_date=today - timedelta(days=120),
            completed_mileage=100000,
            performed_by_type=PerformedByType.DIY,
            total_cost=0.0,
            notes="Rotated front-to-back cross. Adjusted pressures to 33 PSI cold."
        )
        rec_filters = ServiceRecord(
            vehicle_id=vehicle_id,
            service_definition_id=sdef_filters.id,
            service_name=sdef_filters.service_name,
            completed_date=today - timedelta(days=365),
            completed_mileage=90000,
            performed_by_type=PerformedByType.DIY,
            total_cost=38.00,
            notes="Replaced engine filter with Wix 49017 and cabin filter with EPAuto CP285."
        )
        session.add_all([rec_oil, rec_tire, rec_filters])
        session.commit()

        # 4. Consumable Specifications
        consumables = [
            ConsumableSpecification(
                vehicle_id=vehicle_id,
                category=ConsumableCategory.WIPER_BLADES,
                item_name="Driver Side Wiper Blade",
                specification="26 Inches (650mm) - Top Lock / Pinch Tab / J-Hook",
                oem_part_number="85222-06130",
                aftermarket_alternatives="Bosch ICON 26A / Rain-X Latitude 26\"",
                replacement_interval_summary="Inspect every 6 months / replace annually",
                notes="OE blade insert rubber can be replaced separately with Toyota OEM 85214-06140."
            ),
            ConsumableSpecification(
                vehicle_id=vehicle_id,
                category=ConsumableCategory.WIPER_BLADES,
                item_name="Passenger Side Wiper Blade",
                specification="18 Inches (450mm) - Top Lock / Pinch Tab / J-Hook",
                oem_part_number="85212-06150",
                aftermarket_alternatives="Bosch ICON 18A / Rain-X Latitude 18\"",
                replacement_interval_summary="Inspect every 6 months / replace annually"
            ),
            ConsumableSpecification(
                vehicle_id=vehicle_id,
                category=ConsumableCategory.ENGINE_AIR_FILTER,
                item_name="Engine Air Intake Filter",
                specification="High-efficiency pleated panel filter",
                oem_part_number="17801-YZZ11",
                aftermarket_alternatives="Wix 49017 / Fram Extra Guard CA10171 / K&N 33-2326",
                replacement_interval_summary="30,000 miles / 36 months",
                notes="Located in airbox on driver side of engine bay. Requires no tools to open clips."
            ),
            ConsumableSpecification(
                vehicle_id=vehicle_id,
                category=ConsumableCategory.CABIN_AIR_FILTER,
                item_name="Cabin HVAC Microfilter",
                specification="Pollen / Activated Carbon Air Filter",
                oem_part_number="87139-YZZ20",
                aftermarket_alternatives="EPAuto CP285 / Fram Fresh Breeze CF10285",
                replacement_interval_summary="20,000 - 30,000 miles / 24-36 months",
                notes="Located behind the glove box compartment. Dampener arm slides off easily."
            ),
            ConsumableSpecification(
                vehicle_id=vehicle_id,
                category=ConsumableCategory.TIRES,
                item_name="All-Season Tires (Stock Fitment)",
                specification="215/55R17 94V (Optional Touring 18\": 225/45R18 91V)",
                aftermarket_alternatives="Michelin Defender 2 / Continental PureContact LS / Pirelli Cinturato P7",
                replacement_interval_summary="Rotate every 5,000 miles, replace at 4/32\" tread"
            ),
            ConsumableSpecification(
                vehicle_id=vehicle_id,
                category=ConsumableCategory.TIRE_PRESSURE,
                item_name="Cold Tire Inflation Pressure",
                specification="33 PSI Front / 33 PSI Rear (Compact Spare: 60 PSI)",
                notes="Check when cold before driving. Door jamb sticker recommends 33 PSI cold."
            ),
            ConsumableSpecification(
                vehicle_id=vehicle_id,
                category=ConsumableCategory.ENGINE_OIL,
                item_name="Engine Motor Oil",
                specification="0W-20 Full Synthetic (API SP / ILSAC GF-6A)",
                oem_part_number="00279-0W201-01",
                capacity_or_size="6.4 US Quarts (6.1 Liters) with filter replacement",
                aftermarket_alternatives="Mobil 1 Advanced Fuel Economy 0W-20 / Pennzoil Platinum 0W-20",
                replacement_interval_summary="10,000 miles / 12 months (5,000 mi severe)",
                notes="Drain plug torque: 30 ft-lbs (41 Nm). Replace crush washer OEM 90430-12031."
            ),
            ConsumableSpecification(
                vehicle_id=vehicle_id,
                category=ConsumableCategory.OIL_FILTER,
                item_name="Cartridge Oil Filter Element",
                specification="Cartridge filter kit including 2 rubber O-rings and plastic drain tube",
                oem_part_number="04152-YZZA1",
                aftermarket_alternatives="Mobil 1 M1C-251A / Wix 57047 / Bosch 3300",
                replacement_interval_summary="Replace at every oil change",
                notes="Oil filter housing cap torque: 18 ft-lbs (25 Nm). Use 64mm 14-flute filter wrench tool."
            ),
            ConsumableSpecification(
                vehicle_id=vehicle_id,
                category=ConsumableCategory.FUEL_GRADE,
                item_name="Fuel Grade & Capacity",
                specification="87 Octane Regular Unleaded (AKI (R+M)/2 87 or higher)",
                capacity_or_size="17.0 US Gallons (64.3 Liters)",
                notes="Top Tier detergent gasoline recommended. E15 max acceptable."
            ),
            ConsumableSpecification(
                vehicle_id=vehicle_id,
                category=ConsumableCategory.SPARK_PLUGS,
                item_name="Iridium Long-Life Spark Plugs",
                specification="Denso FK20HR11 / Gap: 0.043 in (1.1 mm)",
                oem_part_number="90919-01247",
                aftermarket_alternatives="NGK DILFR6D11",
                replacement_interval_summary="120,000 miles",
                notes="Qty 6 required. Torque to 13 ft-lbs (18 Nm). Do not adjust pre-gapped iridium tip."
            ),
            ConsumableSpecification(
                vehicle_id=vehicle_id,
                category=ConsumableCategory.TRANSMISSION_FLUID,
                item_name="Automatic Transmission Fluid",
                specification="Toyota Genuine ATF WS (World Standard Low-Viscosity)",
                oem_part_number="00289-ATFWS",
                capacity_or_size="Drain & Fill: ~2.5 US Qts (Dry Fill: 6.9 Qts)",
                aftermarket_alternatives="Aisin ATF-0WS",
                replacement_interval_summary="60,000 miles / 72 months",
                notes="Sealed transmission without dipstick. Check level via overflow plug at 104°F–113°F (40°C–45°C)."
            ),
            ConsumableSpecification(
                vehicle_id=vehicle_id,
                category=ConsumableCategory.COOLANT,
                item_name="Engine Coolant",
                specification="Toyota Super Long Life Coolant (50/50 Pre-diluted Pink)",
                oem_part_number="00272-SLLC2",
                capacity_or_size="9.7 US Quarts (9.2 Liters)",
                aftermarket_alternatives="Valvoline Zerex Asian Pink",
                replacement_interval_summary="Initial: 100,000 miles / 10 years, then every 50,000 mi / 5 yrs"
            ),
        ]
        session.add_all(consumables)
        session.commit()

        # 5. Vehicle Documents
        doc_reg = VehicleDocument(
            vehicle_id=vehicle_id,
            doc_type=DocumentType.REGISTRATION,
            document_number="REG-2014-TYT-882",
            issuer="Department of Motor Vehicles (DMV)",
            effective_date=today - timedelta(days=320),
            expiration_date=today + timedelta(days=45),
            lead_alert_days=30,
            notes="Annual vehicle registration and road tax renewal."
        )
        doc_ins = VehicleDocument(
            vehicle_id=vehicle_id,
            doc_type=DocumentType.INSURANCE,
            document_number="GEICO-POL-9842100",
            issuer="GEICO Casualty Insurance Co.",
            effective_date=today - timedelta(days=35),
            expiration_date=today + timedelta(days=145),
            lead_alert_days=30,
            notes="Comprehensive & Collision coverage with $500 deductible and roadside assistance."
        )
        session.add_all([doc_reg, doc_ins])
        session.commit()

        # 6. Service Shop & External Service Work Order
        shop = ServiceShop(
            name="Apex Japanese Auto Care",
            contact_name="Kenji Takahashi",
            phone="(408) 555-0199",
            email="service@apexautocare.com",
            address="1420 Commercial St, San Jose, CA 95112",
            hourly_labor_rate=145.00,
            specialties="Toyota / Lexus Master Technician Certified, Genuine OEM parts specialist",
            rating=4.9,
            notes="Trusted specialist for 2GR-FE intake plenum and transmission fluid services."
        )
        session.add(shop)
        session.commit()
        session.refresh(shop)

        order = ExternalServiceOrder(
            vehicle_id=vehicle_id,
            shop_id=shop.id,
            service_summary="120k Spark Plug Replacement & Transmission Drain/Fill Service",
            scheduled_date=today + timedelta(days=14),
            status=WorkOrderStatus.PLANNED,
            quoted_labor_cost=290.00,
            mechanic_notes="Customer sourcing OEM Denso Spark Plugs and Toyota ATF WS fluid. Shop providing intake plenum gasket set."
        )
        session.add(order)
        session.commit()
        session.refresh(order)

        part1 = PartSourcing(
            work_order_id=order.id,
            vehicle_id=vehicle_id,
            part_name="Denso Iridium Long-Life Spark Plugs (Set of 6)",
            oem_part_number="90919-01247",
            supplier="RockAuto",
            order_status=PartOrderStatus.DELIVERED,
            tracking_number="1Z9999999999999999",
            unit_cost=9.85,
            quantity=6,
            order_date=today - timedelta(days=7),
            actual_delivery_date=today - timedelta(days=2),
            notes="Denso FK20HR11 in original Denso packaging. Verified genuine."
        )
        part2 = PartSourcing(
            work_order_id=order.id,
            vehicle_id=vehicle_id,
            part_name="Toyota Genuine ATF WS Fluid (4 Quarts)",
            oem_part_number="00289-ATFWS",
            supplier="Toyota OEM Parts Direct",
            order_status=PartOrderStatus.DELIVERED,
            tracking_number="9400111899223344556677",
            unit_cost=11.50,
            quantity=4,
            order_date=today - timedelta(days=7),
            actual_delivery_date=today - timedelta(days=2),
            notes="Factory sealed bottles."
        )
        session.add_all([part1, part2])
        session.commit()

        # 7. Reference Documents & Community DIY Guides
        ref_manual = ReferenceDocument(
            vehicle_id=vehicle_id,
            service_definition_id=sdef_oil.id,
            title="2014 Toyota Avalon Factory Scheduled Maintenance & Specifications Guide",
            doc_category=DocCategory.OFFICIAL_MANUAL,
            source_name_or_url="Toyota Technical Information System (TIS)",
            difficulty=DifficultyRating.BEGINNER,
            tools_required="14mm wrench, 64mm oil filter housing wrench, funnel, oil drain pan",
            estimated_hours=0.5,
            step_by_step_instructions=(
                "1. Warm engine to normal operating temperature.\n"
                "2. Raise vehicle and secure on jack stands.\n"
                "3. Remove 14mm oil pan drain bolt and drain oil into pan.\n"
                "4. Remove 3/8 drive metal center plug from oil filter cap and insert drain tube.\n"
                "5. Unscrew oil filter housing with 64mm 14-flute tool.\n"
                "6. Replace inner paper cartridge element and large rubber O-ring (lubricate with fresh oil).\n"
                "7. Torque filter cap to 18 ft-lbs (25 Nm) and pan bolt to 30 ft-lbs (41 Nm) with new crush washer.\n"
                "8. Fill with 6.4 US Quarts 0W-20 full synthetic motor oil. Verify level on dipstick."
            ),
            early_service_community_tips="Owners who operate in severe stop-and-go city traffic report cleaner VVT-i oil passages by changing oil every 5,000 miles instead of 10,000 miles.",
            tags="oil-change, 2gr-fe, maintenance, specifications"
        )
        ref_spark = ReferenceDocument(
            vehicle_id=vehicle_id,
            service_definition_id=sdef_spark_plugs.id,
            title="2GR-FE V6 Rear Spark Plug & Intake Plenum Removal Walkthrough (Community DIY)",
            doc_category=DocCategory.COMMUNITY_DIY_GUIDE,
            source_name_or_url="ToyotaNation / ClubLexus DIY Forums",
            difficulty=DifficultyRating.INTERMEDIATE,
            tools_required="10mm & 12mm sockets, 5/8 spark plug socket, 3/8 locking extensions, swivel ratchet, E8 Torx socket, new intake plenum gasket (Toyota 17176-0P020)",
            estimated_hours=2.5,
            step_by_step_instructions=(
                "1. Disconnect negative battery terminal.\n"
                "2. Remove windshield wiper arms, cowl clips, and upper windshield plastic cowl tray for generous rear clearance.\n"
                "3. Disconnect throttle body electrical connector, vacuum hoses, PCV hose, and EVAP purge line.\n"
                "4. Remove the three rear intake manifold support bracket bolts (12mm and 14mm on firewall side - use swivel ratchet).\n"
                "5. Unbolt the upper intake plenum bolts (10mm) and remove plenum, exposing Bank 1 (cylinders 1, 3, 5).\n"
                "6. Cover open intake runners with clean microfiber towels.\n"
                "7. Unbolt ignition coil pack bolts (10mm), remove coils, and extract old spark plugs with 5/8 magnetic socket.\n"
                "8. Hand thread new Denso FK20HR11 plugs and torque to 13 ft-lbs (18 Nm).\n"
                "9. Reinstall coils, clean mating surface, install new plenum gasket (17176-0P020), and torque plenum bolts to 15 ft-lbs."
            ),
            early_service_community_tips="Several owners complete this at 100k miles when doing coolant service. Removing the wiper cowl adds 20 minutes upfront but saves hours of frustration reaching the rear firewall bracket bolts.",
            tags="spark-plugs, 2gr-fe, plenum-removal, intake-gasket, community-diy"
        )
        ref_trans = ReferenceDocument(
            vehicle_id=vehicle_id,
            service_definition_id=sdef_trans_fluid.id,
            title="Toyota U660E 6-Speed Automatic Transmission Fluid WS Drain, Fill & Level Check Procedure",
            doc_category=DocCategory.COMMUNITY_DIY_GUIDE,
            source_name_or_url="ToyotaNation Community Knowledge Base",
            difficulty=DifficultyRating.ADVANCED,
            tools_required="10mm hex / 6mm hex bit, 24mm fill plug socket, fluid transfer pump, OBD-II scanner / jumper wire for ATF temp mode",
            estimated_hours=1.5,
            step_by_step_instructions=(
                "1. Ensure car is level on 4 jack stands.\n"
                "2. Remove front driver wheel and plastic splash shield to access 24mm ATF fill plug.\n"
                "3. Remove bottom 6mm hex overflow check plug, then 10mm hex plastic standpipe to drain ~2.5 quarts of fluid.\n"
                "4. Reinstall plastic standpipe hand tight, then bottom drain plug.\n"
                "5. Pump 3.0 quarts of fresh Toyota Genuine ATF WS through the 24mm side fill port.\n"
                "6. Start engine and shift through P-R-N-D-S holding each gear for 3 seconds.\n"
                "7. Enter ATF Temperature Detection Mode using OBD scanner (or bridging DLC3 pins 4 & 13).\n"
                "8. When D indicator stays solid (temperature is between 104°F - 113°F / 40°C - 45°C), open the 6mm overflow plug with engine idling.\n"
                "9. Allow excess fluid to stream out until it turns into a thin trickle. Reinstall overflow plug with new crush washer."
            ),
            early_service_community_tips="Toyota labels WS fluid as 'lifetime', but transmission engineers and forum consensus heavily advise drain-and-fills every 50k-60k miles to ensure smooth 200k+ mile longevity without valve body solenoid sticking.",
            tags="transmission, u660e, atf-ws, drain-and-fill, fluid-level"
        )
        session.add_all([ref_manual, ref_spark, ref_trans])
        session.commit()

        # 8. Vehicle Knowledge Base & Quirks
        k1 = VehicleKnowledge(
            vehicle_id=vehicle_id,
            category=KnowledgeCategory.KNOWN_QUIRK,
            component_system=ComponentSystem.ENGINE,
            title="Cold Start VVT-i Camshaft Gear Rattle (2GR-FE 3.5L V6)",
            description="A brief 1-2 second metallic rattling noise occurring on cold morning engine starts. Caused by oil draining out of the intake variable valve timing actuator gear lock pin over prolonged parking.",
            mileage_onset_range="70,000 - 130,000 miles",
            severity=SeverityLevel.WATCH_ITEM,
            real_world_data="Extremely common across Toyota/Lexus 2GR-FE vehicles (Avalon, Camry V6, RAV4 V6, Lexus ES350/RX350). Observed in over 40% of high-mileage units.",
            recommended_action="Always use genuine OEM Toyota oil filters (04152-YZZA1) and high-quality 0W-20 synthetic oil with strong anti-drainback protection. If noise clears within 1-2 seconds and oil pressure light turns off immediately, engine damage is negligible.",
            source_community="ToyotaNation & ClubLexus V6 Registry"
        )
        k2 = VehicleKnowledge(
            vehicle_id=vehicle_id,
            category=KnowledgeCategory.COMMON_FAILURE_POINT,
            component_system=ComponentSystem.ENGINE,
            title="Rubber Oil Cooler Line Weeping / Replacement with All-Metal Pipe",
            description="Early 2GR-FE oil cooler lines used a two-piece metal tube with a flexible rubber hose section in the center. Over years of heat cycling, the rubber section can weep or abruptly rupture, spraying engine oil.",
            mileage_onset_range="80,000 - 150,000 miles",
            severity=SeverityLevel.MODERATE_RISK,
            real_world_data="Subject of Toyota Technical Service Bulletins and warranty enhancement campaigns on 2GR engines equipped with tow/heavy-duty cooling packages.",
            recommended_action="Inspect oil cooler line located near oil filter housing. If rubber center is present, replace with Toyota OEM updated 100% all-metal oil cooler pipe assembly (Part # 04004-29131) and two new metal gaskets.",
            source_community="Toyota TSB & Community Advisory"
        )
        k3 = VehicleKnowledge(
            vehicle_id=vehicle_id,
            category=KnowledgeCategory.REAL_WORLD_PERFORMANCE,
            component_system=ComponentSystem.ENGINE,
            title="Real-World Fuel Economy Performance (EPA 21 City / 31 Highway)",
            description="Real-world observed fuel economy metrics collected from Avalon owners across mixed driving conditions on 87 octane regular unleaded.",
            mileage_onset_range="All mileages",
            severity=SeverityLevel.INFO,
            real_world_data="City driving (stop-and-go): 20.5 - 22.0 MPG. Highway cruising at 70 MPH: 30.5 - 32.5 MPG. Combined long-term average: 24.8 MPG. Range per 17-gallon tank: approx 410 - 450 miles.",
            recommended_action="Maintain 33 PSI cold tire pressures and clean engine air filter every 20k miles for optimal MPG.",
            source_community="Fuelly & Owner Log Data"
        )
        k4 = VehicleKnowledge(
            vehicle_id=vehicle_id,
            category=KnowledgeCategory.KNOWN_QUIRK,
            component_system=ComponentSystem.SUSPENSION,
            title="Front Strut Mount Creak / Groan During Low-Speed Parking Turns",
            description="A low-frequency groaning or creaking sound from front suspension when turning steering wheel lock-to-lock at parking lot speeds.",
            mileage_onset_range="60,000 - 110,000 miles",
            severity=SeverityLevel.WATCH_ITEM,
            real_world_data="Caused by dry upper strut mount bearing friction in the rubber isolator under the front shock towers.",
            recommended_action="Not a structural failure. Can be mitigated by lubricating the upper bearing spring seat with silicone lubricant, or replacing upper strut mounts when replacing struts.",
            source_community="Avalon Owners Club"
        )
        session.add_all([k1, k2, k3, k4])
        session.commit()

        print("2014 Toyota Avalon successfully seeded with factory schedules, consumables, repair guides, and knowledge base!")
        return vehicle_id

if __name__ == "__main__":
    seed_database()
