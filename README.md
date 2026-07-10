# 🏥 Monitor Health | AI-Powered Patient Health Monitoring System

A graduation project submitted to the **Jordan University of Science and Technology (JUST)**. This system aims to assist doctors and nurses in monitoring patients' conditions with high accuracy by integrating a traditional patient registration management system with AI-driven facial emotion and expression analysis.

---

## 📋 About the Project

Built using the **Django** framework, **Monitor Health** provides an integrated dashboard for medical staff (doctors and nurses) to manage patient records and track both their physical and emotional states in real-time. By utilizing camera feeds, the system analyzes facial expressions to detect early indicators of pain, distress, discomfort, or anxiety.

---

## ✨ Key Features

*   🩺 **Comprehensive Patient Management System**: Easily register, update, and manage medical files and appointments.
*   🎥 **Real-Time Facial Emotion Recognition (FER)**: Continuously monitor the patient's emotional and psychological state via a live camera feed.
*   👨‍⚕️ **Dedicated Medical Staff Interfaces**: A user-friendly, optimized dashboard tailored specifically for the daily workflows of doctors and nurses.
*   📊 **Condition Tracking & Analytics**: Log, document, and track patient monitoring metrics and trends over time.

---

## 🛠️ Tech Stack & Architecture

| Technology | Role / Usage |
| :--- | :--- |
| **Python / Django** | Backend Logic & System Administration |
| **OpenCV** | Video Processing & Live Camera Management |
| **Deep Learning (FER Model)** | Facial Emotion Recognition & Analysis |
| **HTML5 / CSS3** | Frontend User Interface |
| **SQLite / PostgreSQL** | Database Management |

---

## 📁 Project Structure
project-two/
├── core/                  # التطبيق الأساسي (Views, Models, Migrations)
│   ├── management/
│   │   └── commands/      # أوامر مخصصة (run_camera)
│   └── services/          # خدمات المعالجة (tracking، إلخ)
├── monitor_health/        # إعدادات مشروع Django الرئيسية
├── static/                 # ملفات CSS / JS / صور ثابتة
├── templates/               # صفحات HTML
├── tests/                    # اختبارات المشروع
├── db_scripts/                # سكربتات قاعدة البيانات
├── fer_model.py                # نموذج تحليل مشاعر الوجه
├── manage.py
└── requirements.txt





⚙️ Local Setup & Installation
Follow these steps to get the project up and running on your local machine:

Bash
# 1. Clone the repository
git clone [https://github.com/Hebatullah03/project-two.git](https://github.com/Hebatullah03/project-two.git)
cd project-two

# 2. Create and activate a virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# 3. Install the required dependencies
pip install -r requirements.txt

# 4. Apply database migrations
python manage.py migrate

# 5. Run the development server
python manage.py runserver
Once the server is running, open your browser and navigate to: http://127.0.0.1:8000

🎥 Running the Emotion Recognition System (Camera Feed)
To trigger the AI-driven facial expression and analysis module independently, execute the following command:

Bash
python manage.py run_camera
👩‍💻 Project Credits
Graduation Project - Jordan University of Science and Technology (JUST).




## 🐘 Database Setup (PostgreSQL via Docker)

This project relies on **PostgreSQL** running inside a Docker container for its data storage.

### Configuration Steps (Using Docker Desktop):

1. Ensure that [Docker Desktop](https://www.docker.com/products/docker-desktop/) is installed and running on your machine.
2. From Docker Desktop, search for the official `postgres` image and run it with the following configuration settings:
   * **Database Name:** `monitor_health`
   * **Username:** `postgres`
   * **Port Mapping:** `5434` (Host Port) → `5432` (Container Port)
3. Create a `.env` file in the root directory of the project and define your environment variables as follows:

```env
DB_Password=your_database_password_here
DB_Host=localhost

4. Database Migration & Running the Server
Once the database container is up, execute the following commands to apply migrations and start the development server:

Bash
python manage.py migrate
python manage.py runserver



