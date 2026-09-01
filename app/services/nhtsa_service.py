import httpx
from typing import Dict, Any, List, Optional

VPIC_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{vin}?format=json"
RECALLS_URL = "https://api.nhtsa.gov/recalls/recallsByVin?vin={vin}"
COMPLAINTS_URL = "https://api.nhtsa.gov/complaints/complaintsByVehicle?make={make}&model={model}&modelYear={year}"

class NHTSAService:
    @staticmethod
    def decode_vin(vin: str) -> Dict[str, Any]:
        """
        Decodes a 17-character VIN using the official NHTSA VPIC API.
        Extracts year, make, model, engine specs, cylinders, trim, and plant details.
        """
        clean_vin = vin.strip().upper()
        url = VPIC_URL.format(vin=clean_vin)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("Results", [])
                    extracted = {}
                    for item in results:
                        var_name = item.get("Variable")
                        val = item.get("Value")
                        if var_name and val:
                            extracted[var_name] = val
                    
                    year = int(extracted.get("Model Year")) if extracted.get("Model Year", "").isdigit() else None
                    make = extracted.get("Make", "").title()
                    model = extracted.get("Model", "").title()
                    displacement = extracted.get("Displacement (L)")
                    cylinders = extracted.get("Engine Number of Cylinders")
                    engine_model = extracted.get("Engine Model")
                    trim = extracted.get("Trim") or extracted.get("Series")
                    drive_type = extracted.get("Drive Type")
                    plant_country = extracted.get("Plant Country")

                    engine_desc = []
                    if displacement:
                        engine_desc.append(f"{displacement}L")
                    if cylinders:
                        engine_desc.append(f"V{cylinders}" if cylinders == "6" or cylinders == "8" else f"I{cylinders}")
                    if engine_model:
                        engine_desc.append(f"({engine_model})")

                    return {
                        "vin": clean_vin,
                        "valid": bool(year and make and model),
                        "year": year,
                        "make": make,
                        "model": model,
                        "trim": trim,
                        "displacement_l": float(displacement) if displacement and displacement.replace('.', '', 1).isdigit() else None,
                        "cylinders": int(cylinders) if cylinders and cylinders.isdigit() else None,
                        "engine_model": engine_model,
                        "engine_summary": " ".join(engine_desc) if engine_desc else None,
                        "drive_type": drive_type,
                        "plant_country": plant_country,
                        "raw_data": extracted,
                    }
        except Exception:
            pass

        # Offline / fallback heuristic decoder if network is offline
        return {
            "vin": clean_vin,
            "valid": len(clean_vin) == 17,
            "year": None,
            "make": None,
            "model": None,
            "trim": None,
            "engine_summary": None,
            "raw_data": {},
        }

    @staticmethod
    def get_recalls_by_vin(vin: str) -> List[Dict[str, Any]]:
        """
        Retrieves active safety recalls from the NHTSA Safety Recalls API for a specific VIN.
        """
        clean_vin = vin.strip().upper()
        url = RECALLS_URL.format(vin=clean_vin)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    raw_recalls = data.get("results", []) or data.get("Results", [])
                    recalls = []
                    for r in raw_recalls:
                        recalls.append({
                            "campaign_number": r.get("NHTSACampaignNumber") or r.get("CampaignNumber") or "UNKNOWN",
                            "component": r.get("Component", "General Safety"),
                            "summary": r.get("Summary", ""),
                            "remedy": r.get("Remedy", "Contact authorized dealer for free inspection/repair."),
                            "notes": r.get("Notes", ""),
                        })
                    return recalls
        except Exception:
            pass
        return []

    @staticmethod
    def get_complaint_highlights(year: int, make: str, model: str) -> List[Dict[str, Any]]:
        """
        Retrieves common safety defect complaints and trends from the NHTSA Complaints API.
        """
        url = COMPLAINTS_URL.format(year=year, make=make.upper(), model=model.upper())
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("results", []) or data.get("Results", [])
                    complaints = []
                    for c in results[:10]: # Top 10 trends
                        complaints.append({
                            "component": c.get("components", "Various Components"),
                            "summary": c.get("summary", ""),
                            "crash": c.get("crash", False),
                            "fire": c.get("fire", False),
                            "date": c.get("dateComplaintFiled", ""),
                        })
                    return complaints
        except Exception:
            pass
        return []
