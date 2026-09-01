import urllib.parse
from typing import Dict, Any, List, Optional
from app.models.consumable import ConsumableCategory
from app.models.reference_doc import DocCategory, DifficultyRating
from app.models.vehicle_knowledge import KnowledgeCategory, ComponentSystem, SeverityLevel

# Comprehensive OEM & Community Knowledge Profiles for Fleet Vehicles
VEHICLE_KNOWLEDGE_PROFILES = {
    "toyota_2gr_fe": {
        "identifiers": ["2GR-FE", "2GRFE", "AVALON 3.5", "CAMRY 3.5", "RAV4 3.5", "HIGHLANDER 3.5", "SIENNA 3.5", "ES350", "RX350"],
        "consumables": [
            {
                "category": ConsumableCategory.ENGINE_OIL,
                "item_name": "Engine Motor Oil",
                "specification": "SAE 0W-20 Full Synthetic (6.4 Quarts with filter)",
                "oem_part_number": "00279-0WQTE-01",
                "aftermarket_alternatives": "Mobil 1 Advanced Fuel Economy 0W-20, Pennzoil Platinum 0W-20",
                "replacement_interval_summary": "Every 10,000 miles / 12 months (5,000 mi for severe/city duty)"
            },
            {
                "category": ConsumableCategory.OIL_FILTER,
                "item_name": "Oil Filter Element",
                "specification": "Cartridge Style Oil Filter with O-Ring & Drain Adapter",
                "oem_part_number": "04152-YZZA1",
                "aftermarket_alternatives": "Wix 57060, Mobil 1 M1C-251A, Fram Ultra Synthetic XG9972",
                "replacement_interval_summary": "Replace every oil change (10,000 mi / 12 mo)"
            },
            {
                "category": ConsumableCategory.SPARK_PLUGS,
                "item_name": "Iridium Spark Plugs (Set of 6)",
                "specification": "0.044 inch (1.1mm) Pre-gapped Long-Life Iridium",
                "oem_part_number": "90919-01247 (Denso FK20HR11)",
                "aftermarket_alternatives": "NGK Laser Iridium 93385 (DILFR6D11), NGK Ruthenium",
                "replacement_interval_summary": "Every 120,000 miles / 10 years"
            },
            {
                "category": ConsumableCategory.TRANSMISSION_FLUID,
                "item_name": "Automatic Transmission Fluid (WS)",
                "specification": "Toyota Genuine ATF WS (World Standard) Low Viscosity - Drain & Fill ~2.2 - 2.5 Quarts",
                "oem_part_number": "00289-ATFWS",
                "aftermarket_alternatives": "Aisin ATF-0WS, Idemitsu TLS-LV",
                "replacement_interval_summary": "Every 60,000 miles (drain & fill) for transmission longevity"
            },
            {
                "category": ConsumableCategory.COOLANT,
                "item_name": "Super Long Life Engine Coolant (SLLC)",
                "specification": "Toyota Pink 50/50 Pre-Diluted Ethylene Glycol Super Long Life",
                "oem_part_number": "00272-SLLC2",
                "aftermarket_alternatives": "Zerex Asian Red/Pink, Valvoline Multi-Vehicle Asian",
                "replacement_interval_summary": "Initial at 100,000 miles, every 50,000 miles thereafter"
            },
            {
                "category": ConsumableCategory.ENGINE_AIR_FILTER,
                "item_name": "Engine Air Intake Filter",
                "specification": "High-Efficiency Pleated Paper Air Cleaner Element",
                "oem_part_number": "17801-YZZ06 (or 17801-31090)",
                "aftermarket_alternatives": "Wix 49017, Denso 143-3011, K&N 33-2326",
                "replacement_interval_summary": "Every 30,000 miles / 36 months (inspect every 15,000 mi)"
            },
            {
                "category": ConsumableCategory.CABIN_AIR_FILTER,
                "item_name": "Cabin Air Pollen Filter",
                "specification": "Glove Box Drop-in Carbon/Baking Soda Activated Filter",
                "oem_part_number": "87139-YZZ20",
                "aftermarket_alternatives": "EPAuto CP285, Bosch HEPA 6055C, Fram Fresh Breeze CF10285",
                "replacement_interval_summary": "Every 15,000 - 20,000 miles / 12 months"
            },
            {
                "category": ConsumableCategory.WIPER_BLADES,
                "item_name": "Front Windshield Wiper Blades",
                "specification": "Driver: 26 Inches (650mm) / Passenger: 18 Inches (450mm) Top-Lock/Hook",
                "oem_part_number": "85222-06130 (Driver) / 85212-06130 (Pass)",
                "aftermarket_alternatives": "Bosch ICON 26A / 18A, Rain-X Latitude Water Repellency",
                "replacement_interval_summary": "Every 6 - 12 months or upon streaking"
            }
        ],
        "guides": [
            {
                "title": "2GR-FE Spark Plug Replacement & Intake Plenum Removal Guide",
                "doc_category": DocCategory.COMMUNITY_DIY_GUIDE,
                "difficulty": DifficultyRating.INTERMEDIATE,
                "source_name_or_url": "ToyotaNation & The Car Care Nut",
                "tools_required": "10mm, 12mm, 14mm sockets, 5/8 spark plug socket with rubber insert, 6-inch swivel extension, torque wrench, pliers for vacuum hoses",
                "estimated_hours": 2.5,
                "step_by_step_instructions": "1. Disconnect negative battery terminal.\n2. Unclip mass airflow sensor and remove air filter box and intake duct.\n3. Remove 10mm bolts holding the throttle body to plenum (can leave coolant lines attached to set aside).\n4. Remove rear stay brackets holding upper intake manifold.\n5. Unbolt upper intake plenum (6 bolts/nuts) and lift away to expose rear 3 ignition coils.\n6. Remove 10mm coil pack bolts, pull coils, and replace spark plugs (torque to 15 ft-lbs / 20 Nm).\n7. Clean mating surface, install new OEM intake plenum gasket (17176-0P020), and torque plenum bolts in crisscross sequence to 15 ft-lbs.\n8. Reattach all vacuum hoses, throttle body, and battery.",
                "early_service_community_tips": "ToyotaNation master mechanics strongly recommend replacing the intake plenum gasket (Toyota 17176-0P020, ~$15) whenever replacing spark plugs. Also clean the throttle body plate carbon deposits while it is accessible.",
                "tags": "spark-plugs, 2gr-fe, intake-plenum, v6, toyota, maintenance"
            },
            {
                "title": "U660E 6-Speed Automatic Transmission Drain & Fill Procedure",
                "doc_category": DocCategory.COMMUNITY_DIY_GUIDE,
                "difficulty": DifficultyRating.INTERMEDIATE,
                "source_name_or_url": "The Car Care Nut / ClubLexus",
                "tools_required": "6mm hex bit (overflow tube), 10mm hex (fill plug on side), 24mm / 15/16 socket, fluid transfer pump, OBD2 scan tool or Toyota temperature jumper",
                "estimated_hours": 1.5,
                "step_by_step_instructions": "1. Ensure vehicle is level on 4 jack stands.\n2. Remove transmission drain plug with 6mm hex; let initial fluid drain (~1.5 qt).\n3. Insert 6mm hex into drain hole to unscrew the plastic fluid level overflow tube, allowing remaining fluid to drain (~0.8 qt total ~2.3 qt).\n4. Reinstall plastic overflow tube snugly by hand (do not overtighten; ~1.7 Nm).\n5. Remove driver side wheel/fender liner to access 10mm hex 'WS' fill plug.\n6. Pump in ~2.5 - 2.8 quarts of Toyota Genuine ATF WS fluid until a trickle exits overflow tube, then loosely install drain plug.\n7. Start engine, cycle through P-R-N-D gear positions, let transmission warm to 104°F - 113°F (40°C - 45°C).\n8. Remove drain plug with engine idling in Park; let excess stream turn into a thin trickle, then torque drain plug to 29 ft-lbs with new crush washer.",
                "early_service_community_tips": "Do not believe 'Lifetime Fluid' claims. Enthusiast consensus is doing a 2.5 quart drain & fill every 50k-60k miles prevents shift flare and solenoid sticking.",
                "tags": "transmission, atf-ws, u660e, fluid-change, 6-speed"
            }
        ],
        "quirks": [
            {
                "title": "Brief 1-2 Second Camshaft VVT-i Gear Cold Start Rattle",
                "category": KnowledgeCategory.KNOWN_QUIRK,
                "component_system": ComponentSystem.ENGINE,
                "severity": SeverityLevel.WATCH_ITEM,
                "description": "On cold morning starts after sitting overnight, a brief 1-2 second metallic rattling or clatter noise can be heard as oil pressure builds in the VVT-i intake camshaft phasers.",
                "recommended_action": "Generally harmless if it disappears in under 2 seconds. Use high-quality synthetic 0W-20 oil with OEM Toyota filter anti-drainback valves. If the rattle lasts longer than 3 seconds or triggers a CEL, inspect the VVT-i gear lock pins."
            },
            {
                "title": "All-Metal Engine Oil Cooler Line Upgrade (TSB-0081-11)",
                "category": KnowledgeCategory.COMMON_FAILURE_POINT,
                "component_system": ComponentSystem.ENGINE,
                "severity": SeverityLevel.MODERATE_RISK,
                "description": "Earlier 2GR-FE engines had a rubber center section on the external oil cooler pipe that degraded and caused catastrophic oil loss. Later models (2013+) have the updated all-metal pipe from the factory.",
                "recommended_action": "Visually inspect the front lower engine area behind the radiator. Verify that your oil cooler line is solid metal without rubber hose crimps."
            },
            {
                "title": "Front MacPherson Strut Mount Rubber Creak / Pop at Low Speeds",
                "category": KnowledgeCategory.KNOWN_QUIRK,
                "component_system": ComponentSystem.SUSPENSION,
                "severity": SeverityLevel.INFO,
                "description": "At low speeds when turning into driveways or parking spots over bumps, a slight rubber creak or pop can occur from the upper strut mount bearings.",
                "recommended_action": "Inspect front sway bar end links and upper strut mounts during routine tire rotations. Harmless unless excessive play or knocking develops."
            },
            {
                "title": "Real-World Highway Fuel Economy vs. EPA Rating",
                "category": KnowledgeCategory.REAL_WORLD_PERFORMANCE,
                "component_system": ComponentSystem.ENGINE,
                "severity": SeverityLevel.INFO,
                "description": "Community data confirms the 2GR-FE V6 easily achieves 31-34 MPG on flat highway cruising at 65-70 MPH, exceeding its official 31 MPG EPA highway rating on regular 87 octane fuel.",
                "recommended_action": "Keep tire pressure at 33-35 PSI and use full synthetic 0W-20 oil to maximize highway range (~500+ miles per tank)."
            }
        ]
    }
}

class CommunityCrawler:
    @staticmethod
    def generate_youtube_repair_links(year: int, make: str, model: str, engine_desc: str = "") -> List[Dict[str, str]]:
        """
        Generates targeted YouTube master technician DIY repair walkthrough searches and links.
        """
        queries = [
            f"{year} {make} {model} spark plug replacement tutorial",
            f"{year} {make} {model} oil change filter location",
            f"{year} {make} {model} transmission fluid drain and fill",
            f"{year} {make} {model} front brake pads rotors replacement",
            f"{year} {make} {model} cabin air filter replacement",
            f"{year} {make} {model} top 5 common problems The Car Care Nut"
        ]
        
        links = []
        for q in queries:
            encoded = urllib.parse.quote(q)
            links.append({
                "query": q,
                "url": f"https://www.youtube.com/results?search_query={encoded}",
                "channel_recommendations": "The Car Care Nut, ChrisFix, South Main Auto, 1A Auto"
            })
        return links

    @staticmethod
    def generate_forum_sources(make: str, model: str) -> List[Dict[str, str]]:
        """
        Generates dedicated enthusiast automotive forum communities based on make & model.
        """
        make_lower = make.lower()
        model_lower = model.lower()
        
        forums = [
            {"name": "Bob Is The Oil Guy (BITOG)", "url": "https://bobistheoilguy.com/forums/", "focus": "Oil analysis, fluid specs, filter teardowns"},
            {"name": "Reddit r/MechanicAdvice", "url": "https://www.reddit.com/r/MechanicAdvice/", "focus": "Professional mechanic diagnostics & triage"},
            {"name": "Reddit r/Cartalk", "url": "https://www.reddit.com/r/Cartalk/", "focus": "Community automotive troubleshooting"},
        ]

        if "toyota" in make_lower or "lexus" in make_lower:
            forums.insert(0, {"name": "ToyotaNation Forums", "url": f"https://www.toyota-nation.com/search/?q={urllib.parse.quote(model)}", "focus": "Official DIY master threads, part numbers, owner walkthroughs"})
            forums.insert(1, {"name": "ClubLexus Community", "url": f"https://www.clublexus.com/forums/search.php?query={urllib.parse.quote(model)}", "focus": "V6 2GR-FE & Hybrid technical discussions"})
        elif "honda" in make_lower or "acura" in make_lower:
            forums.insert(0, {"name": "Drive Accord / CivicX Forums", "url": "https://www.driveaccord.net/", "focus": "Honda enthusiast technical repair guides"})
            forums.insert(1, {"name": "Acurazine", "url": "https://acurazine.com/", "focus": "Acura & Honda powertrain maintenance"})
        elif "ford" in make_lower:
            forums.insert(0, {"name": "F150Forum / FordTrucks", "url": "https://www.f150forum.com/", "focus": "EcoBoost & V8 maintenance walkthroughs"})
        elif "subaru" in make_lower:
            forums.insert(0, {"name": "SubaruForester / Outback Forums", "url": "https://www.subaruoutback.org/", "focus": "Boxer engine, CVT fluid, head gasket guides"})
        else:
            forums.insert(0, {"name": f"{make} Owners Club", "url": f"https://www.google.com/search?q={urllib.parse.quote(make + ' ' + model + ' enthusiast forum')}", "focus": "Community model discussions"})

        return forums

    @staticmethod
    def match_knowledge_profile(make: str, model: str, engine_desc: str = "", trim: str = "") -> Optional[Dict[str, Any]]:
        """
        Matches a vehicle against curated technical profiles to auto-populate consumables, guides, and quirks.
        """
        combined = f"{make} {model} {engine_desc} {trim}".upper()
        for key, profile in VEHICLE_KNOWLEDGE_PROFILES.items():
            for idf in profile["identifiers"]:
                if idf in combined or idf.replace(' ', '') in combined.replace(' ', ''):
                    return profile
        
        # Generic fallback profile synthesized from make/model
        return {
            "consumables": [
                {
                    "category": ConsumableCategory.ENGINE_OIL,
                    "item_name": "Engine Motor Oil",
                    "specification": "SAE 0W-20 or 5W-30 Full Synthetic",
                    "replacement_interval_summary": "Every 7,500 - 10,000 miles"
                },
                {
                    "category": ConsumableCategory.OIL_FILTER,
                    "item_name": "Engine Oil Filter",
                    "specification": "OEM Spec Filter",
                    "replacement_interval_summary": "Replace every oil change"
                },
                {
                    "category": ConsumableCategory.ENGINE_AIR_FILTER,
                    "item_name": "Engine Air Filter",
                    "specification": "High-Efficiency Pleated Paper Filter",
                    "replacement_interval_summary": "Every 30,000 miles"
                },
                {
                    "category": ConsumableCategory.CABIN_AIR_FILTER,
                    "item_name": "Cabin Pollen Filter",
                    "specification": "Glovebox Replacement Filter",
                    "replacement_interval_summary": "Every 15,000 - 20,000 miles"
                },
                {
                    "category": ConsumableCategory.WIPER_BLADES,
                    "item_name": "Windshield Wiper Blades",
                    "specification": "Front Driver & Passenger Pair",
                    "replacement_interval_summary": "Every 12 months"
                }
            ],
            "guides": [
                {
                    "title": f"{make} {model} Routine Oil & Filter Service Procedure",
                    "doc_category": DocCategory.COMMUNITY_DIY_GUIDE,
                    "difficulty": DifficultyRating.BEGINNER,
                    "source_name_or_url": "YouTube / Community Forum",
                    "step_by_step_instructions": "1. Warm engine slightly.\n2. Raise vehicle safely on ramps/stands.\n3. Drain oil into pan and replace crush washer.\n4. Replace oil filter.\n5. Fill with specified viscosity and check dipstick level.",
                    "tags": f"oil-change, {make.lower()}, {model.lower()}"
                }
            ],
            "quirks": [
                {
                    "title": f"{make} {model} High Mileage Preventative Care",
                    "category": KnowledgeCategory.COMMUNITY_WISDOM,
                    "component_system": ComponentSystem.ENGINE,
                    "severity": SeverityLevel.INFO,
                    "description": f"Community reports for {year if 'year' in locals() else ''} {make} {model} recommend inspecting rubber suspension bushings, serpentine belts, and cooling hoses past 100k miles.",
                    "recommended_action": "Check fluid levels monthly and perform drain-and-fill services before factory maximum limits."
                }
            ]
        }
