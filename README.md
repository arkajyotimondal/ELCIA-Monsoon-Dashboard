<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-FF0000?style=for-the-badge&logo=YOLO&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=SQLite&logoColor=white)

</div>

# 🌧️ ELCIA Monsoon & Civic Infrastructure Dashboard

**VarunDuth: Real-Time Infrastructure Intelligence**

This repository contains the command-center dashboard and AI pipeline for the **ELCIA Smart City Drone-AI Challenge**. It provides a real-time, operator-focused workspace designed to track, review, and manage civic infrastructure hazards (like potholes, waterlogging, drain overflows, and damaged footpaths) detected dynamically during monsoon conditions.

---

## ✨ Features

- **Real-Time Command Center**: A sleek, dark-themed Streamlit dashboard with auto-refresh functionality, ensuring operators see the latest detections instantly.
- **AI-Powered Hazard Detection**: Integrates directly with a YOLOv8 vision model to process drone/camera feeds and log infrastructure hazards in real-time.
- **Smart Prioritization**: Dynamically calculates and assigns **severity scores** based on confidence and historical data, classifying alerts into *Critical*, *High*, *Watch*, and *Low*.
- **Incident Management**: Operators can filter incidents by zone, severity, hazard class, or status (Open, Acknowledged, Resolved) and receive actionable mitigation recommendations.
- **Embedded Database**: Utilizes a lightweight SQLite architecture (`events.db`) for robust local logging, decoupled perfectly from the inference engine for high concurrency.

---

## 📂 Project Structure

- **`app.py`**: The core Streamlit application. Renders the interactive command-center dashboard, data visualizations, and live event queue.
- **`run_inference.py`**: The AI vision pipeline. Loads the `best.pt` YOLOv8 model, processes video streams (or webcams), and writes detections into the database.
- **`database_setup.py`**: Schema definition and database initialization for the `incidents` table. Includes functions to create, read, update, and seed the database.
- **`seed_db.py`**: A utility script to quickly populate the database with realistic sample data (great for UI testing and demos).
- **`requirements.txt`**: Standard dependencies list (Streamlit, Ultralytics YOLO, OpenCV, Pandas, Altair).
- **`best.pt`** *(Expected)*: The trained YOLOv8 model weights file (to be provided by your ML training pipeline).

---

## 🚀 Installation & Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/arkajyotimondal/ELCIA-Monsoon-Dashboard.git
   cd ELCIA-Monsoon-Dashboard
   ```

2. **Set up a Virtual Environment (Recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Add the Model**
   Place your trained YOLOv8 weights file (`best.pt`) directly into the root directory.

---

## 💻 Usage Instructions

The system is decoupled into two independent processes: the **Inference Pipeline** (which looks for hazards) and the **Dashboard** (which displays them).

### 1. Test Data Initialization (Optional)
If you want to view the dashboard without running a live video feed, you can seed the database with mock historical data:
```bash
python database_setup.py --reset
# OR for a larger, randomized dataset:
python seed_db.py
```

### 2. Run the AI Inference Pipeline
To start analyzing video feeds and logging new incidents:
```bash
python run_inference.py
```
*(Note: Edit `run_inference.py` to point to your specific video file source or use `"0"` for webcam feed).*

### 3. Launch the Dashboard
In a new terminal window, start the Streamlit application:
```bash
streamlit run app.py
```
The dashboard will open automatically in your browser (default: `http://localhost:8501`). It is configured to auto-refresh and pull the newest detections logged by the inference script.

---

## 🛠️ Configuration

- **Hazard Classes**: If your trained YOLOv8 model outputs different class IDs, ensure you update the `CLASS_MAP` in `run_inference.py` to match the exact names:
  - `0`: pothole
  - `1`: waterlogged_road
  - `2`: drain_overflow
  - `3`: damaged_footpath
- **Database Reset**: You can wipe the `events.db` clean at any point by running `python database_setup.py --reset`.

---

<div align="center">
  <i>Developed for the ELCIA Monsoon, Roads & Civic Infrastructure Intelligence Track.</i>
</div>
