import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import csv
import os
import time
import schedule
from datetime import datetime
import threading # To run schedule in background

# --- Hardware Specific Imports ---
try:
    from gpiozero import Servo
    from gpiozero.pins.pigpio import PiGPIOFactory # For stable PWM
    RPI_HW_AVAILABLE = False
except ImportError:
    RPI_HW_AVAILABLE = False
    print("WARNING: gpiozero library not found. Servo control will be simulated.")

try:
    import cv2
    import numpy as np
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False
    print("WARNING: OpenCV library not found. Camera functionality will be simulated.")

# --- Configuration ---
CONFIG_FILE = 'medication_schedule.csv'
# Define GPIO pins for your servos
SERVO_PIN_COMPARTMENT_1 = 17
SERVO_PIN_COMPARTMENT_2 = 27

# Servo angles (0.0 is center, -1.0 is min, 1.0 is max for gpiozero)
# These will likely need calibration for your specific servos and lid mechanism
SERVO_OPEN_ANGLE = 0.8  # Example: 80% towards max rotation
SERVO_CLOSE_ANGLE = -0.8 # Example: 80% towards min rotation
SERVO_INIT_DELAY = 1 # Seconds to wait for servo to reach position

# Camera settings
CAMERA_INDEX = 0 # 0 for default built-in/USB, or specific index if multiple
IMAGE_CAPTURE_DELAY = 5 # Seconds after opening lid to wait before taking "after" image
DETECTION_THRESHOLD = 0.02 # Percentage of image difference to consider "medication taken"

# --- Global Variables ---
servo1 = None
servo2 = None
camera = None
app_running = True # Flag to control the scheduler thread
scheduler_thread = None

# --- Hardware Initialization ---
def init_hardware():
    global servo1, servo2, camera

    if RPI_HW_AVAILABLE:
        try:
            # Use pigpio factory for more stable servo control
            factory = PiGPIOFactory()
            servo1 = Servo(SERVO_PIN_COMPARTMENT_1, pin_factory=factory)
            servo2 = Servo(SERVO_PIN_COMPARTMENT_2, pin_factory=factory)
            # Initialize to closed position
            servo1.value = SERVO_CLOSE_ANGLE
            servo2.value = SERVO_CLOSE_ANGLE
            time.sleep(SERVO_INIT_DELAY)
            servo1.detach() # Detach to save power and reduce jitter
            servo2.detach()
            print("Servos initialized.")
        except Exception as e:
            print(f"Error initializing servos: {e}")
            messagebox.showerror("Hardware Error", f"Could not initialize servos: {e}")
            # Fallback to simulation if hardware init fails
            globals()['RPI_HW_AVAILABLE'] = False


    if CAMERA_AVAILABLE:
        try:
            camera = cv2.VideoCapture(CAMERA_INDEX)
            if not camera.isOpened():
                raise ValueError(f"Cannot open camera at index {CAMERA_INDEX}")
            print("Camera initialized.")
        except Exception as e:
            print(f"Error initializing camera: {e}")
            messagebox.showerror("Hardware Error", f"Could not initialize camera: {e}")
            # Fallback to simulation if camera init fails
            globals()['CAMERA_AVAILABLE'] = False


def cleanup_hardware():
    global servo1, servo2, camera, app_running
    print("Cleaning up hardware...")
    app_running = False # Signal scheduler thread to stop

    if scheduler_thread and scheduler_thread.is_alive():
        print("Waiting for scheduler thread to finish...")
        scheduler_thread.join(timeout=5) # Wait for the thread to exit
        if scheduler_thread.is_alive():
            print("Scheduler thread did not terminate gracefully.")

    if RPI_HW_AVAILABLE and servo1 and servo2:
        servo1.value = SERVO_CLOSE_ANGLE # Ensure lids are closed
        servo2.value = SERVO_CLOSE_ANGLE
        time.sleep(SERVO_INIT_DELAY)
        servo1.detach()
        servo2.detach()
        print("Servos detached.")
    if CAMERA_AVAILABLE and camera:
        camera.release()
        print("Camera released.")
    cv2.destroyAllWindows() # Close any OpenCV windows
    print("Cleanup complete.")

# --- Servo Control Functions ---
def control_lid(compartment_num, action="open"):
    servo = servo1 if compartment_num == 1 else servo2
    target_angle = SERVO_OPEN_ANGLE if action == "open" else SERVO_CLOSE_ANGLE

    if RPI_HW_AVAILABLE and servo:
        print(f"Compartment {compartment_num}: {action}ing lid (Angle: {target_angle}).")
        servo.value = target_angle
        time.sleep(SERVO_INIT_DELAY) # Give servo time to move
        if action == "close": # Detach after closing to save power
            servo.detach()
    else:
        print(f"SIMULATING: Compartment {compartment_num} lid {action}.")

# --- Camera Detection Function (Simplified) ---
def capture_image(filename="debug_capture.jpg"):
    if CAMERA_AVAILABLE and camera and camera.isOpened():
        ret, frame = camera.read()
        if ret:
            cv2.imwrite(filename, frame)
            print(f"Image captured: {filename}")
            return frame
        else:
            print("Failed to capture image.")
            return None
    print("SIMULATING: Image capture.")
    # Return a dummy black image for simulation
    return np.zeros((480, 640, 3), dtype=np.uint8)


def detect_medication_taken(compartment_num):
    """
    A very simplified detection mechanism.
    Compares an image before (assumed clear or reference) and after lid interaction.
    This is highly sensitive to lighting and exact setup.
    """
    if not CAMERA_AVAILABLE:
        print("SIMULATING: Medication detection - Assuming taken.")
        return True # Simulate success if no camera

    print(f"Attempting to detect if medication taken from compartment {compartment_num}...")

    # For a real system, you might take a 'before' image when the lid opens.
    # Here, we'll take one image and simulate a change or have a reference.
    # For simplicity, let's just take one image after a delay and assume if it's different
    # from a hypothetical "empty" state (which we don't have a reference for here).
    # A more robust approach:
    # 1. Capture image_before_opening (or just after opening).
    # 2. Wait.
    # 3. Capture image_after_taking.
    # 4. Compare specific ROI.

    # Simplified: Capture one image and do a basic check
    # This is where you'd define a Region of Interest (ROI) for each compartment
    # For now, we'll use the whole image.
    time.sleep(IMAGE_CAPTURE_DELAY) # Wait for user to potentially take medication
    img_after = capture_image(f"compartment_{compartment_num}_after.jpg")

    if img_after is None:
        print("Could not get 'after' image for detection.")
        return False # Cannot determine

    # --- Rudimentary Change Detection ---
    # This is a placeholder for more sophisticated logic.
    # A simple approach: compare to a known "empty" image, or look for significant pixel changes.
    # For this example, let's just assume any significant activity means it was taken.
    # This could be improved by:
    # - Taking a 'before' image when the lid opens.
    # - Defining a Region of Interest (ROI) for the compartment.
    # - Using background subtraction or comparing to a reference 'empty' image.

    # Example: Convert to grayscale and calculate mean pixel intensity.
    # If you had a reference "empty" image:
    # img_empty_gray = cv2.cvtColor(img_empty_reference, cv2.COLOR_BGR2GRAY)
    # img_after_gray = cv2.cvtColor(img_after, cv2.COLOR_BGR2GRAY)
    # diff = cv2.absdiff(img_empty_gray, img_after_gray)
    # non_zero_count = np.count_nonzero(diff > 30) # Count pixels with significant difference
    # percentage_changed = non_zero_count / diff.size
    # if percentage_changed > DETECTION_THRESHOLD:
    #    print(f"Significant change detected ({percentage_changed:.2%}). Assuming medication taken.")
    #    return True
    # else:
    #    print(f"No significant change detected ({percentage_changed:.2%}). Assuming medication NOT taken.")
    #    return False

    # Fallback for this example:
    print("Simplified detection: Assuming medication taken if lid opened and camera worked.")
    # In a real scenario, you would return based on actual image analysis.
    return True # Placeholder

# --- Scheduled Job ---
def dispense_medication_job(compartment_num, medicine_name):
    print(f"\n--- MEDICATION ALERT ---")
    print(f"Time to take: {medicine_name} from Compartment {compartment_num}")
    messagebox.showinfo("Medication Reminder", f"Time for your {medicine_name} from Compartment {compartment_num}!")

    control_lid(compartment_num, "open")

    # Wait for a bit or for user interaction before checking
    # This duration can be configured or made interactive
    duration_open_seconds = simpledialog.askinteger(
        "Medication Access",
        f"{medicine_name} from Compartment {compartment_num} is accessible.\n"
        "How many seconds do you need the lid open? (e.g., 30-120)",
        initialvalue=60, minvalue=10, maxvalue=300
    )
    if duration_open_seconds is None: # User cancelled
        duration_open_seconds = 30 # Default fallback
        print("User cancelled duration input, defaulting to 30s.")

    print(f"Lid {compartment_num} will remain open for {duration_open_seconds} seconds.")
    time.sleep(duration_open_seconds) # Lid stays open

    taken = detect_medication_taken(compartment_num) # This now includes its own delay

    if taken:
        print(f"Medication '{medicine_name}' likely taken from compartment {compartment_num}.")
        # Log this event, perhaps with a timestamp
    else:
        print(f"Medication '{medicine_name}' may NOT have been taken from compartment {compartment_num}.")
        # Log this, perhaps send a notification to a caregiver
        messagebox.showwarning("Medication Not Taken?", f"It seems {medicine_name} from Compartment {compartment_num} was not taken. Please check.")

    control_lid(compartment_num, "close")
    print(f"--- END MEDICATION ALERT ({medicine_name}) ---\n")

# --- Configuration Load/Save ---
def load_config():
    config = [{}, {}] # Default empty config for two compartments
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, mode='r', newline='') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i < 2: # Only load up to 2 compartments
                        config[i] = {'name': row.get('medicine_name', ''), 'time': row.get('time_hhmm', '')}
        except Exception as e:
            print(f"Error loading config: {e}")
            messagebox.showerror("Config Error", f"Could not load {CONFIG_FILE}: {e}")
    return config

def save_config(med1_name, med1_time, med2_name, med2_time):
    try:
        with open(CONFIG_FILE, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['compartment_id', 'medicine_name', 'time_hhmm'])
            writer.writerow([1, med1_name, med1_time])
            writer.writerow([2, med2_name, med2_time])
        messagebox.showinfo("Success", "Configuration saved!")
        # After saving, reload schedules
        setup_schedules()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save configuration: {e}")

# --- Scheduler Setup ---
def setup_schedules():
    schedule.clear() # Clear existing jobs before loading new ones
    config_data = load_config()
    loaded_jobs = 0

    # Compartment 1
    if config_data[0].get('name') and config_data[0].get('time'):
        try:
            schedule.every().day.at(config_data[0]['time']).do(
                dispense_medication_job,
                compartment_num=1,
                medicine_name=config_data[0]['name']
            ).tag('compartment1', 'medication')
            print(f"Scheduled: Comp 1 - {config_data[0]['name']} at {config_data[0]['time']}")
            loaded_jobs +=1
        except Exception as e:
            print(f"Error scheduling Comp 1 ({config_data[0]['time']}): {e}")
            messagebox.showerror("Scheduling Error", f"Invalid time format for Compartment 1: {config_data[0]['time']}\nUse HH:MM (24-hour). Error: {e}")


    # Compartment 2
    if config_data[1].get('name') and config_data[1].get('time'):
        try:
            schedule.every().day.at(config_data[1]['time']).do(
                dispense_medication_job,
                compartment_num=2,
                medicine_name=config_data[1]['name']
            ).tag('compartment2', 'medication')
            print(f"Scheduled: Comp 2 - {config_data[1]['name']} at {config_data[1]['time']}")
            loaded_jobs +=1
        except Exception as e:
            print(f"Error scheduling Comp 2 ({config_data[1]['time']}): {e}")
            messagebox.showerror("Scheduling Error", f"Invalid time format for Compartment 2: {config_data[1]['time']}\nUse HH:MM (24-hour). Error: {e}")


    if loaded_jobs == 0:
        print("No valid schedules found in config or config is empty.")
    else:
        print(f"Total jobs scheduled: {len(schedule.jobs)}")


def run_scheduler():
    global app_running
    print("Scheduler thread started.")
    setup_schedules() # Load schedules initially
    while app_running:
        schedule.run_pending()
        time.sleep(1) # Check every second
    print("Scheduler thread stopped.")


# --- GUI Application ---
class MedBoxApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Medication Box Configurator")
        # self.root.geometry("450x300") # Adjust as needed

        # Load initial config
        self.config_data = load_config()

        # --- Styling ---
        style = ttk.Style()
        style.configure("TLabel", padding=5, font=('Helvetica', 10))
        style.configure("TEntry", padding=5, font=('Helvetica', 10))
        style.configure("TButton", padding=5, font=('Helvetica', 10, 'bold'))
        style.configure("TFrame", padding=10)
        style.configure("Header.TLabel", font=('Helvetica', 14, 'bold'))

        main_frame = ttk.Frame(root_window, padding="10 10 10 10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        root_window.columnconfigure(0, weight=1)
        root_window.rowconfigure(0, weight=1)

        # --- Compartment 1 ---
        ttk.Label(main_frame, text="Compartment 1", style="Header.TLabel").grid(row=0, column=0, columnspan=2, pady=(0,10), sticky=tk.W)
        ttk.Label(main_frame, text="Medicine Name:").grid(row=1, column=0, sticky=tk.W)
        self.med1_name_var = tk.StringVar(value=self.config_data[0].get('name', ''))
        self.med1_name_entry = ttk.Entry(main_frame, textvariable=self.med1_name_var, width=30)
        self.med1_name_entry.grid(row=1, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Time (HH:MM 24h):").grid(row=2, column=0, sticky=tk.W)
        self.med1_time_var = tk.StringVar(value=self.config_data[0].get('time', ''))
        self.med1_time_entry = ttk.Entry(main_frame, textvariable=self.med1_time_var, width=10)
        self.med1_time_entry.grid(row=2, column=1, sticky=tk.W)

        # --- Compartment 2 ---
        ttk.Label(main_frame, text="Compartment 2", style="Header.TLabel").grid(row=3, column=0, columnspan=2, pady=(10,10), sticky=tk.W)
        ttk.Label(main_frame, text="Medicine Name:").grid(row=4, column=0, sticky=tk.W)
        self.med2_name_var = tk.StringVar(value=self.config_data[1].get('name', ''))
        self.med2_name_entry = ttk.Entry(main_frame, textvariable=self.med2_name_var, width=30)
        self.med2_name_entry.grid(row=4, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Time (HH:MM 24h):").grid(row=5, column=0, sticky=tk.W)
        self.med2_time_var = tk.StringVar(value=self.config_data[1].get('time', ''))
        self.med2_time_entry = ttk.Entry(main_frame, textvariable=self.med2_time_var, width=10)
        self.med2_time_entry.grid(row=5, column=1, sticky=tk.W)

        # --- Buttons ---
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=(20,0))

        self.save_button = ttk.Button(button_frame, text="Save Configuration", command=self.save_gui_config)
        self.save_button.pack(side=tk.LEFT, padx=5)

        self.test_c1_button = ttk.Button(button_frame, text="Test Comp. 1", command=lambda: self.test_compartment(1))
        self.test_c1_button.pack(side=tk.LEFT, padx=5)
        self.test_c2_button = ttk.Button(button_frame, text="Test Comp. 2", command=lambda: self.test_compartment(2))
        self.test_c2_button.pack(side=tk.LEFT, padx=5)

        # Make columns in main_frame responsive
        main_frame.columnconfigure(1, weight=1)

        # Status bar (optional)
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(root_window, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.update_status()

        # Start scheduler in a separate thread
        global scheduler_thread
        if not scheduler_thread or not scheduler_thread.is_alive(): # Ensure only one scheduler thread
            scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
            scheduler_thread.start()
        else:
            print("Scheduler thread already running.")

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_status(self):
        jobs = schedule.get_jobs()
        if jobs:
            next_run_times = []
            for job in jobs:
                if job.next_run: # Check if job has a next_run time
                    next_run_times.append(job.next_run.strftime('%Y-%m-%d %H:%M:%S'))
            if next_run_times:
                status_text = "Next runs: " + ", ".join(next_run_times)
            else:
                status_text = "No jobs scheduled or all jobs past."
        else:
            status_text = "No jobs scheduled."
        self.status_var.set(status_text)
        self.root.after(5000, self.update_status) # Update status every 5 seconds


    def save_gui_config(self):
        med1_name = self.med1_name_var.get()
        med1_time = self.med1_time_var.get()
        med2_name = self.med2_name_var.get()
        med2_time = self.med2_time_var.get()

        # Basic time validation (HH:MM)
        try:
            if med1_time: datetime.strptime(med1_time, '%H:%M')
            if med2_time: datetime.strptime(med2_time, '%H:%M')
        except ValueError:
            messagebox.showerror("Invalid Time", "Please use HH:MM format for time (e.g., 08:30 or 17:00).")
            return

        save_config(med1_name, med1_time, med2_name, med2_time)
        self.update_status() # Refresh status after saving and reloading schedules

    def test_compartment(self, compartment_num):
        med_name = self.med1_name_var.get() if compartment_num == 1 else self.med2_name_var.get()
        if not med_name: med_name = f"Test Med {compartment_num}"

        # Run dispense job in a new thread to avoid freezing GUI
        test_thread = threading.Thread(target=dispense_medication_job, args=(compartment_num, f"[TEST] {med_name}"), daemon=True)
        test_thread.start()


    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit? This will stop medication reminders."):
            cleanup_hardware()
            self.root.destroy()

# --- Main Execution ---
if __name__ == "__main__":
    init_hardware()

    root = tk.Tk()
    app = MedBoxApp(root)
    try:
        root.mainloop()
    finally:
        # This ensures cleanup happens even if mainloop exits unexpectedly,
        # though on_closing should ideally handle graceful exits.
        if app_running: # If on_closing wasn't called (e.g. forceful exit)
            cleanup_hardware()