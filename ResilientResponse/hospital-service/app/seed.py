"""
Development seed: creates sample hospitals and police stations if they don't exist.
Idempotent — safe to run multiple times.
"""
import asyncio
from datetime import datetime
from app.database import get_db, close_db


SAMPLE_HOSPITALS = [
    {
        "name": "City General Hospital",
        "registration_number": "HOS-001",
        "phone": "+1-555-0101",
        "emergency_phone": "+1-555-0911",
        "email": "info@citygeneralhospital.example",
        "address": "1, Ansari Road",
        "city": "New Delhi",
        "state": "Delhi",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "emergency_capacity": 200,
        "available_beds": 45,
        "icu_beds": 20,
        "status": "ACTIVE",
    },
    {
        "name": "Copper Hospital",
        "registration_number": "HOS-002",
        "phone": "+1-555-0202",
        "emergency_phone": "+1-555-0922",
        "email": "copper@hospital.example",
        "address": "Dr E Moses Road",
        "city": "Mumbai",
        "state": "Maharashtra",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "emergency_capacity": 150,
        "available_beds": 30,
        "icu_beds": 10,
        "status": "ACTIVE",
    },
    {
        "name": "Eastview Trauma Center",
        "registration_number": "HOS-003",
        "phone": "+1-555-0303",
        "emergency_phone": "+1-555-0933",
        "email": None,
        "address": "Hosur Road",
        "city": "Bengaluru",
        "state": "Karnataka",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "emergency_capacity": 80,
        "available_beds": 12,
        "icu_beds": 8,
        "status": "ACTIVE",
    },
    {
        "name": "Chennai Coastal Medical Center", "registration_number": "HOS-004",
        "phone": "+91-044-4004004", "emergency_phone": "+91-044-108",
        "email": "chennai@hospital.example", "address": "Marina Beach Road",
        "city": "Chennai", "state": "Tamil Nadu", "latitude": 13.0827, "longitude": 80.2707,
        "emergency_capacity": 180, "available_beds": 55, "icu_beds": 16, "status": "ACTIVE",
    },
    {
        "name": "Kolkata River Hospital", "registration_number": "HOS-005",
        "phone": "+91-033-4004005", "emergency_phone": "+91-033-108",
        "email": "kolkata@hospital.example", "address": "Hooghly River Road",
        "city": "Kolkata", "state": "West Bengal", "latitude": 22.5726, "longitude": 88.3639,
        "emergency_capacity": 160, "available_beds": 40, "icu_beds": 14, "status": "ACTIVE",
    },
    {
        "name": "Hyderabad Emergency Hospital", "registration_number": "HOS-006",
        "phone": "+91-040-4004006", "emergency_phone": "+91-040-108",
        "email": "hyderabad@hospital.example", "address": "HITEC City Road",
        "city": "Hyderabad", "state": "Telangana", "latitude": 17.3850, "longitude": 78.4867,
        "emergency_capacity": 220, "available_beds": 65, "icu_beds": 22, "status": "ACTIVE",
    },
    {
        "name": "Pune Hills Trauma Hospital", "registration_number": "HOS-007",
        "phone": "+91-020-4004007", "emergency_phone": "+91-020-108",
        "email": "pune@hospital.example", "address": "Sinhagad Road",
        "city": "Pune", "state": "Maharashtra", "latitude": 18.5204, "longitude": 73.8567,
        "emergency_capacity": 140, "available_beds": 35, "icu_beds": 12, "status": "ACTIVE",
    },
    {
        "name": "Ahmedabad Civil Emergency Center", "registration_number": "HOS-008",
        "phone": "+91-079-4004008", "emergency_phone": "+91-079-108",
        "email": "ahmedabad@hospital.example", "address": "Sabarmati Riverfront",
        "city": "Ahmedabad", "state": "Gujarat", "latitude": 23.0225, "longitude": 72.5714,
        "emergency_capacity": 200, "available_beds": 50, "icu_beds": 18, "status": "ACTIVE",
    },
    {
        "name": "Guwahati Regional Hospital", "registration_number": "HOS-009",
        "phone": "+91-0361-4004009", "emergency_phone": "+91-0361-108",
        "email": "guwahati@hospital.example", "address": "Brahmaputra Riverfront",
        "city": "Guwahati", "state": "Assam", "latitude": 26.1445, "longitude": 91.7362,
        "emergency_capacity": 130, "available_beds": 28, "icu_beds": 10, "status": "ACTIVE",
    },
    {
        "name": "Kochi Coastal Hospital", "registration_number": "HOS-010",
        "phone": "+91-0484-4004010", "emergency_phone": "+91-0484-108",
        "email": "kochi@hospital.example", "address": "Vembanad Lake Road",
        "city": "Kochi", "state": "Kerala", "latitude": 9.9312, "longitude": 76.2673,
        "emergency_capacity": 150, "available_beds": 42, "icu_beds": 13, "status": "ACTIVE",
    },
    {
        "name": "Jaipur Pink City Emergency Hospital", "registration_number": "HOS-011",
        "phone": "+91-0141-4004011", "emergency_phone": "+91-0141-108",
        "email": "jaipur@hospital.example", "address": "MI Road, Near City Palace",
        "city": "Jaipur", "state": "Rajasthan", "latitude": 26.9124, "longitude": 75.7873,
        "emergency_capacity": 170, "available_beds": 48, "icu_beds": 15, "status": "ACTIVE",
    },
    {
        "name": "Lucknow Gomti Medical Center", "registration_number": "HOS-012",
        "phone": "+91-0522-4004012", "emergency_phone": "+91-0522-108",
        "email": "lucknow@hospital.example", "address": "Gomti Nagar",
        "city": "Lucknow", "state": "Uttar Pradesh", "latitude": 26.8467, "longitude": 80.9462,
        "emergency_capacity": 190, "available_beds": 52, "icu_beds": 17, "status": "ACTIVE",
    },
    {
        "name": "Srinagar Valley Hospital", "registration_number": "HOS-013",
        "phone": "+91-0194-4004013", "emergency_phone": "+91-0194-108",
        "email": "srinagar@hospital.example", "address": "Dal Lake Road",
        "city": "Srinagar", "state": "Jammu & Kashmir", "latitude": 34.0837, "longitude": 74.7973,
        "emergency_capacity": 120, "available_beds": 25, "icu_beds": 9, "status": "ACTIVE",
    },
    {
        "name": "Bhubaneswar Kalinga Medical Center", "registration_number": "HOS-014",
        "phone": "+91-0674-4004014", "emergency_phone": "+91-0674-108",
        "email": "bhubaneswar@hospital.example", "address": "Janpath, Khandagiri",
        "city": "Bhubaneswar", "state": "Odisha", "latitude": 20.2961, "longitude": 85.8245,
        "emergency_capacity": 160, "available_beds": 38, "icu_beds": 14, "status": "ACTIVE",
    },
    {
        "name": "Bengaluru Whitefield Emergency Hospital", "registration_number": "HOS-015",
        "phone": "+91-080-4004015", "emergency_phone": "+91-080-108",
        "email": "whitefield@hospital.example", "address": "ITPL Main Road",
        "city": "Bengaluru", "state": "Karnataka", "latitude": 12.9698, "longitude": 77.7500,
        "emergency_capacity": 210, "available_beds": 58, "icu_beds": 20, "status": "ACTIVE",
    },
    {
        "name": "Chandigarh PGI Emergency Wing", "registration_number": "HOS-016",
        "phone": "+91-0172-4004016", "emergency_phone": "+91-0172-108",
        "email": "chandigarh@hospital.example", "address": "Sector 12",
        "city": "Chandigarh", "state": "Chandigarh", "latitude": 30.7333, "longitude": 76.7794,
        "emergency_capacity": 250, "available_beds": 70, "icu_beds": 25, "status": "ACTIVE",
    },
    {
        "name": "Nagpur Central Trauma Center", "registration_number": "HOS-017",
        "phone": "+91-0712-4004017", "emergency_phone": "+91-0712-108",
        "email": "nagpur@hospital.example", "address": "Civil Lines",
        "city": "Nagpur", "state": "Maharashtra", "latitude": 21.1458, "longitude": 79.0882,
        "emergency_capacity": 175, "available_beds": 44, "icu_beds": 16, "status": "ACTIVE",
    },
    {
        "name": "Visakhapatnam Port Hospital", "registration_number": "HOS-018",
        "phone": "+91-0891-4004018", "emergency_phone": "+91-0891-108",
        "email": "vizag@hospital.example", "address": "Beach Road, RK Beach",
        "city": "Visakhapatnam", "state": "Andhra Pradesh", "latitude": 17.6868, "longitude": 83.2185,
        "emergency_capacity": 185, "available_beds": 50, "icu_beds": 18, "status": "ACTIVE",
    },
    {
        "name": "Thiruvananthapuram Medical College Hospital", "registration_number": "HOS-019",
        "phone": "+91-0471-4004019", "emergency_phone": "+91-0471-108",
        "email": "trivandrum@hospital.example", "address": "Medical College Road",
        "city": "Thiruvananthapuram", "state": "Kerala", "latitude": 8.5241, "longitude": 76.9366,
        "emergency_capacity": 200, "available_beds": 55, "icu_beds": 19, "status": "ACTIVE",
    },
    {
        "name": "Bhopal Hamidia Emergency Hospital", "registration_number": "HOS-020",
        "phone": "+91-0755-4004020", "emergency_phone": "+91-0755-108",
        "email": "bhopal@hospital.example", "address": "Upper Lake Road",
        "city": "Bhopal", "state": "Madhya Pradesh", "latitude": 23.2599, "longitude": 77.4126,
        "emergency_capacity": 165, "available_beds": 36, "icu_beds": 12, "status": "ACTIVE",
    },
    {
        "name": "Patna AIIMS Emergency Center", "registration_number": "HOS-021",
        "phone": "+91-0612-4004021", "emergency_phone": "+91-0612-108",
        "email": "patna@hospital.example", "address": "Ganga Riverfront",
        "city": "Patna", "state": "Bihar", "latitude": 25.5941, "longitude": 85.1376,
        "emergency_capacity": 230, "available_beds": 62, "icu_beds": 22, "status": "ACTIVE",
    },
    {
        "name": "Indore MY Hospital Emergency Wing", "registration_number": "HOS-022",
        "phone": "+91-0731-4004022", "emergency_phone": "+91-0731-108",
        "email": "indore@hospital.example", "address": "Rajwada Square",
        "city": "Indore", "state": "Madhya Pradesh", "latitude": 22.7196, "longitude": 75.8577,
        "emergency_capacity": 155, "available_beds": 33, "icu_beds": 11, "status": "ACTIVE",
    },
    {
        "name": "Amritsar Guru Nanak Emergency Hospital", "registration_number": "HOS-023",
        "phone": "+91-0183-4004023", "emergency_phone": "+91-0183-108",
        "email": "amritsar@hospital.example", "address": "Golden Temple Road",
        "city": "Amritsar", "state": "Punjab", "latitude": 31.6340, "longitude": 74.8723,
        "emergency_capacity": 145, "available_beds": 40, "icu_beds": 14, "status": "ACTIVE",
    },
    {
        "name": "Dehradun Himalayan Trauma Center", "registration_number": "HOS-024",
        "phone": "+91-0135-4004024", "emergency_phone": "+91-0135-108",
        "email": "dehradun@hospital.example", "address": "Mussoorie Road",
        "city": "Dehradun", "state": "Uttarakhand", "latitude": 30.3165, "longitude": 78.0322,
        "emergency_capacity": 110, "available_beds": 22, "icu_beds": 8, "status": "ACTIVE",
    },
]

SAMPLE_POLICE_STATIONS = [
    {
        "name": "Central Police Station",
        "station_code": "CPSD-01",
        "phone": "+1-555-0401",
        "emergency_phone": "+1-555-0100",
        "email": "central@police.example",
        "address": "Parliament Street",
        "city": "New Delhi",
        "state": "Delhi",
        "latitude": 28.6138,
        "longitude": 77.2091,
        "status": "ACTIVE",
    },
    {
        "name": "Juhu Police Station",
        "station_code": "NSPD-02",
        "phone": "+1-555-0402",
        "emergency_phone": "+1-555-0100",
        "email": "jhu@police.example",
        "address": "Andheri West, Juhu Beach",
        "city": "Mumbai",
        "state": "Maharashtra",
        "latitude": 19.0761,
        "longitude": 72.8778,
        "status": "ACTIVE",
    },
    {
        "name": "Chennai Coastal Police Station", "station_code": "CPSD-03", "phone": "+91-044-1003",
        "emergency_phone": "+91-044-100", "email": "chennai.police@example",
        "address": "Marina Beach Road", "city": "Chennai", "state": "Tamil Nadu",
        "latitude": 13.0828, "longitude": 80.2708, "status": "ACTIVE",
    },
    {
        "name": "Kolkata River Police Station", "station_code": "WBPD-04", "phone": "+91-033-1004",
        "emergency_phone": "+91-033-100", "email": "kolkata.police@example",
        "address": "Hooghly River Road", "city": "Kolkata", "state": "West Bengal",
        "latitude": 22.5727, "longitude": 88.3640, "status": "ACTIVE",
    },
    {
        "name": "Hyderabad Cyberabad Police Station", "station_code": "HYDP-05", "phone": "+91-040-1005",
        "emergency_phone": "+91-040-100", "email": "hyderabad.police@example",
        "address": "HITEC City Road", "city": "Hyderabad", "state": "Telangana",
        "latitude": 17.3851, "longitude": 78.4868, "status": "ACTIVE",
    },
    {
        "name": "Pune Hills Police Station", "station_code": "PUPD-06", "phone": "+91-020-1006",
        "emergency_phone": "+91-020-100", "email": "pune.police@example",
        "address": "Sinhagad Road", "city": "Pune", "state": "Maharashtra",
        "latitude": 18.5205, "longitude": 73.8568, "status": "ACTIVE",
    },
    {
        "name": "Ahmedabad River Police Station", "station_code": "GJPD-07", "phone": "+91-079-1007",
        "emergency_phone": "+91-079-100", "email": "ahmedabad.police@example",
        "address": "Sabarmati Riverfront", "city": "Ahmedabad", "state": "Gujarat",
        "latitude": 23.0226, "longitude": 72.5715, "status": "ACTIVE",
    },
    {
        "name": "Guwahati River Police Station", "station_code": "ASPD-08", "phone": "+91-0361-1008",
        "emergency_phone": "+91-0361-100", "email": "guwahati.police@example",
        "address": "Brahmaputra Riverfront", "city": "Guwahati", "state": "Assam",
        "latitude": 26.1446, "longitude": 91.7363, "status": "ACTIVE",
    },
    {
        "name": "Kochi Coastal Police Station", "station_code": "KLPD-09", "phone": "+91-0484-1009",
        "emergency_phone": "+91-0484-100", "email": "kochi.police@example",
        "address": "Vembanad Lake Road", "city": "Kochi", "state": "Kerala",
        "latitude": 9.9313, "longitude": 76.2674, "status": "ACTIVE",
    },
    {
        "name": "Bengaluru City Police Station", "station_code": "BLRPD-10", "phone": "+91-080-1010",
        "emergency_phone": "+91-080-100", "email": "bengaluru.police@example",
        "address": "MG Road", "city": "Bengaluru", "state": "Karnataka",
        "latitude": 12.9717, "longitude": 77.5947, "status": "ACTIVE",
    },
    {
        "name": "Jaipur Pink City Police Station", "station_code": "JPD-11", "phone": "+91-0141-1011",
        "emergency_phone": "+91-0141-100", "email": "jaipur.police@example",
        "address": "MI Road, Near City Palace", "city": "Jaipur", "state": "Rajasthan",
        "latitude": 26.9125, "longitude": 75.7874, "status": "ACTIVE",
    },
    {
        "name": "Lucknow Hazratganj Police Station", "station_code": "LKPD-12", "phone": "+91-0522-1012",
        "emergency_phone": "+91-0522-100", "email": "lucknow.police@example",
        "address": "Hazratganj", "city": "Lucknow", "state": "Uttar Pradesh",
        "latitude": 26.8468, "longitude": 80.9463, "status": "ACTIVE",
    },
    {
        "name": "Srinagar Lal Chowk Police Station", "station_code": "SKPD-13", "phone": "+91-0194-1013",
        "emergency_phone": "+91-0194-100", "email": "srinagar.police@example",
        "address": "Lal Chowk", "city": "Srinagar", "state": "Jammu & Kashmir",
        "latitude": 34.0838, "longitude": 74.7974, "status": "ACTIVE",
    },
    {
        "name": "Bhubaneswar Capital Police Station", "station_code": "ORPD-14", "phone": "+91-0674-1014",
        "emergency_phone": "+91-0674-100", "email": "bhubaneswar.police@example",
        "address": "Janpath, Khandagiri", "city": "Bhubaneswar", "state": "Odisha",
        "latitude": 20.2962, "longitude": 85.8246, "status": "ACTIVE",
    },
    {
        "name": "Chandigarh Sector 17 Police Station", "station_code": "CHPD-15", "phone": "+91-0172-1015",
        "emergency_phone": "+91-0172-100", "email": "chandigarh.police@example",
        "address": "Sector 17 Plaza", "city": "Chandigarh", "state": "Chandigarh",
        "latitude": 30.7334, "longitude": 76.7795, "status": "ACTIVE",
    },
    {
        "name": "Nagpur Central Police Station", "station_code": "NGPD-16", "phone": "+91-0712-1016",
        "emergency_phone": "+91-0712-100", "email": "nagpur.police@example",
        "address": "Civil Lines", "city": "Nagpur", "state": "Maharashtra",
        "latitude": 21.1459, "longitude": 79.0883, "status": "ACTIVE",
    },
    {
        "name": "Visakhapatnam Coastal Police Station", "station_code": "VKPD-17", "phone": "+91-0891-1017",
        "emergency_phone": "+91-0891-100", "email": "vizag.police@example",
        "address": "Beach Road, RK Beach", "city": "Visakhapatnam", "state": "Andhra Pradesh",
        "latitude": 17.6869, "longitude": 83.2186, "status": "ACTIVE",
    },
    {
        "name": "Thiruvananthapuram City Police Station", "station_code": "TVMPD-18", "phone": "+91-0471-1018",
        "emergency_phone": "+91-0471-100", "email": "trivandrum.police@example",
        "address": "Medical College Road", "city": "Thiruvananthapuram", "state": "Kerala",
        "latitude": 8.5242, "longitude": 76.9367, "status": "ACTIVE",
    },
    {
        "name": "Bhopal Upper Lake Police Station", "station_code": "BPPD-19", "phone": "+91-0755-1019",
        "emergency_phone": "+91-0755-100", "email": "bhopal.police@example",
        "address": "Upper Lake Road", "city": "Bhopal", "state": "Madhya Pradesh",
        "latitude": 23.2600, "longitude": 77.4127, "status": "ACTIVE",
    },
    {
        "name": "Patna Ganga River Police Station", "station_code": "PNPD-20", "phone": "+91-0612-1020",
        "emergency_phone": "+91-0612-100", "email": "patna.police@example",
        "address": "Ganga Riverfront", "city": "Patna", "state": "Bihar",
        "latitude": 25.5942, "longitude": 85.1377, "status": "ACTIVE",
    },
    {
        "name": "Indore Rajwada Police Station", "station_code": "INPD-21", "phone": "+91-0731-1021",
        "emergency_phone": "+91-0731-100", "email": "indore.police@example",
        "address": "Rajwada Square", "city": "Indore", "state": "Madhya Pradesh",
        "latitude": 22.7197, "longitude": 75.8578, "status": "ACTIVE",
    },
    {
        "name": "Amritsar Golden Temple Police Station", "station_code": "AMPD-22", "phone": "+91-0183-1022",
        "emergency_phone": "+91-0183-100", "email": "amritsar.police@example",
        "address": "Golden Temple Road", "city": "Amritsar", "state": "Punjab",
        "latitude": 31.6341, "longitude": 74.8724, "status": "ACTIVE",
    },
    {
        "name": "Dehradun Mussoorie Road Police Station", "station_code": "DDNPD-23", "phone": "+91-0135-1023",
        "emergency_phone": "+91-0135-100", "email": "dehradun.police@example",
        "address": "Mussoorie Road", "city": "Dehradun", "state": "Uttarakhand",
        "latitude": 30.3166, "longitude": 78.0323, "status": "ACTIVE",
    },
]


async def seed():
    db = get_db()
    now = datetime.utcnow()

    for hospital in SAMPLE_HOSPITALS:
        await db.hospitals.update_one(
            {"registration_number": hospital["registration_number"]},
            {"$set": {**hospital, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    print(f"[seed] Upserted {len(SAMPLE_HOSPITALS)} India hospital records")

    for station in SAMPLE_POLICE_STATIONS:
        await db.police_stations.update_one(
            {"station_code": station["station_code"]},
            {"$set": {**station, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    print(f"[seed] Upserted {len(SAMPLE_POLICE_STATIONS)} India police records")

    await close_db()


if __name__ == "__main__":
    asyncio.run(seed())
