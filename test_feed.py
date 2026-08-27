import time
import random
from datetime import datetime
import database_setup

def run_simulation():
    print("Starting simulated live feed... (Press Ctrl+C to stop)")
    conn = database_setup.get_connection()
    database_setup.create_table(conn)
    
    hazards = ["pothole", "waterlogged_road", "drain_overflow", "damaged_footpath"]
    zones = ["Hosur Road Sector A", "Silk Board Underpass", "Koramangala 5th Block", "Jayanagar 4th Block"]
    
    try:
        while True:
            # Pick a random hazard and zone
            hazard = random.choice(hazards)
            zone = random.choice(zones)
            confidence = random.uniform(0.65, 0.98)
            severity = random.uniform(0.20, 0.95)
            timestamp = datetime.now().isoformat(timespec="seconds")
            
            # Insert into database
            incident_id = database_setup.insert_incident(
                conn=conn,
                timestamp=timestamp,
                zone=zone,
                hazard_class=hazard,
                confidence_score=confidence,
                severity_score=severity,
                status="Open"
            )
            
            print(f"🚨 [SIMULATION] Detected {hazard} in {zone} ({confidence*100:.1f}%) -> Logged as #{incident_id}")
            
            # Wait for 3 seconds before the next detection
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\nSimulation stopped.")

if __name__ == "__main__":
    run_simulation()
