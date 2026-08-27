import time
from datetime import datetime

try:
    from ultralytics import YOLO
    import cv2
except ImportError:
    print("Please install requirements: pip install -r requirements.txt")
    exit(1)

import database_setup

# 1. Load your friend's trained model here
MODEL_PATH = "best.pt"  # Place the .pt file from your friend in the same folder

# 2. Map YOLO class IDs to your dashboard's hazard classes
# You MUST update this mapping based on how your friend trained the model!
# Ask them: "Which class ID corresponds to pothole, waterlogging, etc.?"
CLASS_MAP = {
    0: "pothole",
    1: "waterlogged_road",
    2: "drain_overflow",
    3: "damaged_footpath"
}

def run_inference(source="0"):
    """
    Run YOLOv8 inference on a source (webcam '0' or video file path)
    and save detections to the SQLite database.
    """
    try:
        model = YOLO(MODEL_PATH)
        print(f"✅ Loaded model {MODEL_PATH}")
    except Exception as e:
        print(f"❌ Could not load model. Make sure {MODEL_PATH} is in the directory! Error: {e}")
        return

    conn = database_setup.get_connection()
    database_setup.create_table(conn)
    
    print(f"🎥 Starting inference on source: {source}")
    
    # Run YOLO inference (stream=True processes frame by frame)
    results = model(source, stream=True)
    
    for result in results:
        annotated_frame = result.plot()
        # Loop through all detections in the current frame
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            confidence = box.conf[0].item()
            
            # Get the string label for the class, default to unknown
            hazard_class = CLASS_MAP.get(class_id, "unknown")
            
            # Optional: Filter out low confidence detections
            if confidence < 0.5:
                continue
            
            # Calculate a mock severity score (you can make this more complex later)
            severity = min(confidence * 1.2, 1.0) 
            
            timestamp = datetime.now().isoformat(timespec="seconds")
            zone = "Camera 1 - Hosur Road" # You can hardcode or set this dynamically
            
            # Save the detection to the database so Streamlit can show it
            try:
                incident_id = database_setup.insert_incident(
                    conn=conn,
                    timestamp=timestamp,
                    zone=zone,
                    hazard_class=hazard_class,
                    confidence_score=confidence,
                    severity_score=severity,
                    thumbnail_path=f"tmp/frame_{timestamp.replace(':', '')}_{class_id}.jpg",
                    status="Open"
                )
                
                # Save the frame to disk so the dashboard can display it
                cv2.imwrite(f"tmp/frame_{timestamp.replace(':', '')}_{class_id}.jpg", annotated_frame)
                
                print(f"🚨 Detected {hazard_class} ({confidence*100:.1f}%) -> Logged as incident #{incident_id}")
            except Exception as e:
                print(f"Failed to save to DB: {e}")
                
                
        # Run headless so it doesn't pop up a window and disrupt the user
        # cv2.imshow("ELCIA Live Camera Feed (Press 'q' to quit)", result.plot())
        # if cv2.waitKey(1) & 0xFF == ord("q"):
        #    break
            
        # Small delay to prevent spamming the database too fast on high-fps video
        time.sleep(0.5)
        
    cv2.destroyAllWindows() 

if __name__ == "__main__":
    # Running the real demonstration on test_video11.mp4
    run_inference("test_video11.mp4")
