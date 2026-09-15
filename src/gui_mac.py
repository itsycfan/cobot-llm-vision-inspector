#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
GUI Application - Motion Claude Vision System + Cobot Controller
Mac OS Compatible Version
=============================================================================
Features:
- Cross-platform GUI using tkinter
- Integration with Vision System
- Integration with Cobot Controller
- Mac OS specific optimizations

Platform: macOS
Date: 2025-10-30
=============================================================================
"""

import os
import sys
import cv2
import threading
import json
import importlib.util
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import queue
import platform


# Add current folder to Python path
sys.path.insert(0, str(Path(__file__).parent))


# ===== Configuration Utilities =====
class ConfigLoader:
    """Load configuration from JSON file"""
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
    
    def _load_config(self, config_path: str):
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {"video": {"folder": "VideoExample"}, "robot": {}}
        except:
            return {"video": {"folder": "VideoExample"}, "robot": {}}


class PlatformUtils:
    """Platform utilities"""
    @staticmethod
    def resolve_path(path_str: str) -> Path:
        """Resolve path, handling special characters"""
        return Path(path_str).expanduser().resolve()


# ===== Module Imports =====
try:
    from MAC_CobotController import CobotController
    COBOT_IMPORTED = True
except Exception as e:
    print(f"[WARN] Cobot import error: {e}")
    COBOT_IMPORTED = False

try:
    from MAC_MotionClaudeVisionSystem import DetectionSystem, Config, find_video, get_latest_video
    SYSTEM_IMPORTED = True
    print("[OK] Vision system imported successfully")
except Exception as e:
    print(f"[WARN] Vision system import error: {e}")
    SYSTEM_IMPORTED = False


# ===== Platform Detection =====
PLATFORM = platform.system()  # 'Windows', 'Darwin' (macOS), 'Linux'
IS_MAC = PLATFORM == 'Darwin'
IS_WINDOWS = PLATFORM == 'Windows'

print(f"[INFO] Running on {PLATFORM}")


# =============================================================================
# VIDEO RECORDER
# =============================================================================

class VideoRecorder:
    """Cross-platform video recorder using OpenCV"""
    
    def __init__(self, output_path: str, fps: int = 30, resolution: tuple = (1280, 720)):
        self.output_path = output_path
        self.fps = fps
        self.resolution = resolution
        self.is_recording = False
        self.cap = None
        self.out = None
    
    def start_recording(self) -> bool:
        """Start recording from webcam"""
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                return False
            
            # Use platform-specific codec
            if IS_MAC:
                fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264 for macOS
            else:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Standard for Windows
            
            self.out = cv2.VideoWriter(
                self.output_path, fourcc, self.fps, self.resolution
            )
            
            if not self.out.isOpened():
                return False
            
            self.is_recording = True
            return True
        except Exception as e:
            print(f"[ERROR] Recording start failed: {e}")
            return False
    
    def stop_recording(self):
        """Stop recording"""
        self.is_recording = False
        if self.out:
            self.out.release()
        if self.cap:
            self.cap.release()
    
    def record_loop(self):
        """Recording loop (runs in thread)"""
        while self.is_recording:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.resize(frame, self.resolution)
                self.out.write(frame)
            else:
                break


# =============================================================================
# MAIN GUI APPLICATION
# =============================================================================

class VisionSystemGUI:
    """Main GUI Application (Mac Compatible)"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Motion Claude Vision System + Cobot Controller")
        self.root.geometry("1200x900")
        self.root.configure(bg="#f0f0f0")
        
        # System initialization
        self.config = None
        self.vision_config = None
        self.vision_system = None
        self.recorder = None
        self.cobot = None
        self.is_recording = False
        self.result_queue = queue.Queue()
        self.cobot_queue = queue.Queue()
        
        # Load configuration
        try:
            config_loader = ConfigLoader()
            self.config = config_loader.config
        except Exception as e:
            print(f"[ERROR] Config load failed: {e}")
            self.config = {"video": {"folder": "VideoExample"}, "robot": {}}
        
        # Initialize Vision System if available
        if SYSTEM_IMPORTED:
            try:
                self.vision_config = Config()
                self.vision_system = DetectionSystem(self.vision_config)
                print("[OK] Vision system initialized")
            except Exception as e:
                print(f"[ERROR] Vision system init failed: {e}")
        
        # Initialize Cobot if available
        if COBOT_IMPORTED:
            try:
                self.cobot = CobotController(simulation_mode=True)
            except Exception as e:
                print(f"[ERROR] Cobot init failed: {e}")
        
        # Build GUI
        self.setup_ui()
        self.update_video_list()
    
    def setup_ui(self):
        """Setup the user interface"""
        
        # Main container with notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # TAB 1: VISION SYSTEM
        vision_frame = ttk.Frame(notebook, padding="10")
        notebook.add(vision_frame, text="Vision Analysis")
        self.setup_vision_tab(vision_frame)
        
        # TAB 2: COBOT CONTROL
        cobot_frame = ttk.Frame(notebook, padding="10")
        notebook.add(cobot_frame, text="Cobot Control")
        self.setup_cobot_tab(cobot_frame)
        
        # TAB 3: SYSTEM INFO
        info_frame = ttk.Frame(notebook, padding="10")
        notebook.add(info_frame, text="System Info")
        self.setup_info_tab(info_frame)
    
    def setup_vision_tab(self, parent):
        """Setup vision analysis tab"""
        
        # Title
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = ttk.Label(
            title_frame,
            text="Motion Claude Vision System",
            font=("Arial", 18, "bold")
        )
        title_label.pack(side=tk.LEFT)
        
        status_label = ttk.Label(
            title_frame,
            text="Ready",
            font=("Arial", 10),
            foreground="green"
        )
        status_label.pack(side=tk.RIGHT)
        self.vision_status = status_label
        
        # Video selection
        video_frame = ttk.LabelFrame(parent, text="Video Selection", padding="10")
        video_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(video_frame, text="Video File:").pack(side=tk.LEFT, padx=5)
        
        self.video_var = tk.StringVar()
        video_combo = ttk.Combobox(video_frame, textvariable=self.video_var, state="readonly", width=40)
        video_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.video_combo = video_combo
        
        ttk.Button(video_frame, text="Refresh", command=self.update_video_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(video_frame, text="Browse", command=self.browse_video).pack(side=tk.LEFT, padx=5)
        
        # Analysis buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.analyze_btn = ttk.Button(button_frame, text="Analyze Video", command=self.analyze_video)
        self.analyze_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Latest Video", command=self.analyze_latest).pack(side=tk.LEFT, padx=5)
        
        # Results display
        result_frame = ttk.LabelFrame(parent, text="Analysis Results", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.result_text = tk.Text(result_frame, height=20, width=120, wrap=tk.WORD)
        self.result_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_text.config(yscrollcommand=scrollbar.set)
    
    def setup_cobot_tab(self, parent):
        """Setup cobot control tab"""
        
        # Title
        title_label = ttk.Label(parent, text="Cobot UR10 Control", font=("Arial", 18, "bold"))
        title_label.pack(pady=10)
        
        # Connection section
        conn_frame = ttk.LabelFrame(parent, text="Connection", padding="10")
        conn_frame.pack(fill=tk.X, pady=10)
        
        self.cobot_status = ttk.Label(conn_frame, text="Disconnected", foreground="red", font=("Arial", 12, "bold"))
        self.cobot_status.pack(side=tk.LEFT, padx=10)
        
        self.cobot_connect_btn = ttk.Button(conn_frame, text="Connect", command=self.cobot_connect)
        self.cobot_connect_btn.pack(side=tk.LEFT, padx=5)
        
        self.cobot_disconnect_btn = ttk.Button(conn_frame, text="Disconnect", command=self.cobot_disconnect, state=tk.DISABLED)
        self.cobot_disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(conn_frame, text="Status", command=self.cobot_get_status).pack(side=tk.LEFT, padx=5)
        
        # Control section
        control_frame = ttk.LabelFrame(parent, text="Control", padding="10")
        control_frame.pack(fill=tk.X, pady=10)
        
        self.cobot_sequence_btn = ttk.Button(control_frame, text="Execute Sequence", command=self.cobot_execute_sequence, state=tk.DISABLED)
        self.cobot_sequence_btn.pack(side=tk.LEFT, padx=5)
        
        self.cobot_home_btn = ttk.Button(control_frame, text="Home Position", command=self.cobot_return_home, state=tk.DISABLED)
        self.cobot_home_btn.pack(side=tk.LEFT, padx=5)
        
        self.cobot_stop_btn = ttk.Button(control_frame, text="Emergency Stop", command=self.cobot_emergency_stop, state=tk.DISABLED)
        self.cobot_stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Progress
        progress_frame = ttk.Frame(parent)
        progress_frame.pack(fill=tk.X, pady=10)
        
        self.cobot_progress_var = tk.IntVar()
        self.cobot_progress = ttk.Progressbar(progress_frame, variable=self.cobot_progress_var, maximum=100)
        self.cobot_progress.pack(fill=tk.X, padx=10)
        
        self.cobot_progress_label = ttk.Label(progress_frame, text="Ready", foreground="blue")
        self.cobot_progress_label.pack()
        
        # Log display
        log_frame = ttk.LabelFrame(parent, text="Robot Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.cobot_log_text = tk.Text(log_frame, height=15, width=120, wrap=tk.WORD)
        self.cobot_log_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.cobot_log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.cobot_log_text.config(yscrollcommand=scrollbar.set)
    
    def setup_info_tab(self, parent):
        """Setup system info tab"""
        
        info_frame = ttk.LabelFrame(parent, text="System Information", padding="20")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        info_text = tk.Text(info_frame, height=25, width=100, wrap=tk.WORD)
        info_text.pack(fill=tk.BOTH, expand=True)
        
        system_info = f"""
SYSTEM INFORMATION
{'='*60}

Platform: {PLATFORM}
Python Version: {sys.version}
Working Directory: {Path.cwd()}

MODULES STATUS
{'='*60}
Vision System: {'[OK]' if SYSTEM_IMPORTED else '[NOT AVAILABLE]'}
Cobot System: {'[OK]' if COBOT_IMPORTED else '[NOT AVAILABLE]'}
OpenCV: {'[OK]' if cv2.__version__ else '[NOT AVAILABLE]'}

VISION SYSTEM CONFIG
{'='*60}
"""
        
        if SYSTEM_IMPORTED:
            config = Config()
            system_info += f"""
Video Folder: {config.VIDEO_FOLDER}
Results Folder: {config.RESULTS_FOLDER}
Excel Path: {config.EXCEL_PATH}
Model: {config.CLAUDE_MODEL}
Key Frames: {config.KEY_FRAMES}
Image Width: {config.IMAGE_WIDTH}
Score Threshold: {config.SCORE_THRESHOLD}
"""
        
        system_info += f"""
COBOT CONFIG
{'='*60}
"""
        
        if COBOT_IMPORTED:
            system_info += f"""
Robot IP: 10.10.220.251
Robot Port: 30002
Simulation Mode: Available
"""
        
        system_info += f"""
NOTES
{'='*60}
- This application integrates Vision Analysis with Cobot Control
- Mac OS optimizations applied for compatibility
- All paths use cross-platform Path handling
- Video codec automatically selected based on OS
"""
        
        info_text.insert('1.0', system_info)
        info_text.config(state=tk.DISABLED)
    
    def update_video_list(self):
        """Update video list from folder"""
        if not SYSTEM_IMPORTED:
            return
        
        config = Config()
        video_folder = Path(config.VIDEO_FOLDER)
        
        videos = []
        if video_folder.exists():
            for file in video_folder.iterdir():
                if file.suffix.lower() in ['.mp4', '.avi', '.mov']:
                    videos.append(file.name)
        
        self.video_combo['values'] = sorted(videos)
        if videos:
            self.video_combo.current(0)
    
    def browse_video(self):
        """Browse for video file"""
        filename = filedialog.askopenfilename(
            filetypes=[("Video files", "*.mp4 *.avi *.mov"), ("All files", "*.*")]
        )
        if filename:
            self.video_var.set(Path(filename).name)
    
    def display_result(self, text: str):
        """Display result in text widget"""
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert('1.0', text)
        self.result_text.config(state=tk.NORMAL)
    
    def analyze_video(self):
        """Analyze selected video"""
        if not SYSTEM_IMPORTED or not self.vision_system:
            messagebox.showerror("Error", "Vision system not available")
            return
        
        video_name = self.video_var.get()
        if not video_name:
            messagebox.showwarning("Warning", "Please select a video")
            return
        
        self.analyze_btn.config(state=tk.DISABLED)
        self.vision_status.config(text="Analyzing...", foreground="blue")
        
        def analyze_thread():
            try:
                result = self.vision_system.process_video(video_name)
                if result:
                    formatted = self._format_result(result)
                    self.result_queue.put(("success", formatted))
                else:
                    self.result_queue.put(("error", "Analysis failed"))
            except Exception as e:
                self.result_queue.put(("error", str(e)))
        
        thread = threading.Thread(target=analyze_thread, daemon=True)
        thread.start()
        
        self.root.after(100, self.check_result_queue)
    
    def analyze_latest(self):
        """Analyze latest video"""
        if not SYSTEM_IMPORTED or not self.vision_system:
            messagebox.showerror("Error", "Vision system not available")
            return
        
        config = Config()
        latest = get_latest_video(config.VIDEO_FOLDER)
        
        if not latest:
            messagebox.showerror("Error", "No videos found")
            return
        
        self.video_var.set(latest)
        self.analyze_video()
    
    def check_result_queue(self):
        """Check for analysis results"""
        try:
            status, message = self.result_queue.get_nowait()
            
            if status == "success":
                self.display_result(message)
                self.vision_status.config(text="Ready", foreground="green")
                messagebox.showinfo("Success", "Analysis complete!")
            else:
                self.display_result(f"ERROR:\n{message}")
                messagebox.showerror("Analysis Error", message)
        
        except queue.Empty:
            self.root.after(100, self.check_result_queue)
        
        finally:
            self.analyze_btn.config(state=tk.NORMAL)
    
    def _format_result(self, result) -> str:
        """Format analysis result for display"""
        lines = []
        lines.append("=" * 70)
        lines.append(f"ANALYSIS RESULT: {result.video_name}")
        lines.append("=" * 70)
        
        lines.append(f"\n[SCORES]")
        lines.append(f"  Safety Score:     {result.safety_score:.1f}/100")
        lines.append(f"  Spatial Score:    {result.spatial_score:.1f}/100")
        lines.append(f"  Operation Score:  {result.operation_score:.1f}/100")
        lines.append(f"  Overall Score:    {result.overall_score:.1f}/100")
        
        lines.append(f"\n[ISSUES DETECTED]")
        lines.append(f"  Total Differences: {len(result.differences)}")
        lines.append(f"  Critical Issues:   {len(result.critical)}")
        lines.append(f"  Major Issues:      {len(result.major)}")
        lines.append(f"  Minor Issues:      {len(result.minor)}")
        lines.append(f"  Negligible:        {len(result.negligible)}")
        
        if result.critical:
            lines.append(f"\n[CRITICAL ISSUES]")
            for d in result.critical:
                lines.append(f"  • {d.description} [{d.category}]")
        
        if result.major:
            lines.append(f"\n[MAJOR ISSUES]")
            for d in result.major:
                lines.append(f"  • {d.description} [{d.category}]")
        
        lines.append(f"\n[DECISION]")
        lines.append(f"  Result: {'[OK] PASS' if result.decision == 'PASS' else '[ERROR] FAIL'}")
        lines.append(f"  Reason: {result.reason}")
        
        lines.append(f"\n[SUMMARY]")
        lines.append(f"{result.summary}")
        
        if result.ground_truth:
            lines.append(f"\n[VALIDATION]")
            lines.append(f"  Ground Truth: {result.ground_truth}")
            lines.append(f"  Prediction:   {'[OK] CORRECT' if result.correct else '[ERROR] INCORRECT'}")
        
        lines.append("\n" + "=" * 70)
        
        return "\n".join(lines)
    
    # ===== COBOT METHODS =====
    def _add_cobot_log(self, message: str):
        """Add message to Cobot log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.cobot_log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.cobot_log_text.see(tk.END)
    
    def cobot_connect(self):
        """Connect to Cobot"""
        if not COBOT_IMPORTED or not self.cobot:
            messagebox.showerror("Error", "Cobot system not available")
            return
        
        self._add_cobot_log("Connecting to robot...")
        self.cobot_connect_btn.config(state=tk.DISABLED)
        
        def connect_thread():
            try:
                if self.cobot.connect():
                    self.cobot_queue.put(("connected", "Success"))
                else:
                    self.cobot_queue.put(("connection_failed", "Failed to connect"))
            except Exception as e:
                self.cobot_queue.put(("error", str(e)))
        
        thread = threading.Thread(target=connect_thread, daemon=True)
        thread.start()
        
        self.root.after(100, self.check_cobot_queue)
    
    def check_cobot_queue(self):
        """Check for Cobot status updates"""
        try:
            status, message = self.cobot_queue.get_nowait()
            
            if status == "connected":
                self._add_cobot_log("[OK] Robot connected successfully")
                self.cobot_status.config(text="Connected", foreground="green")
                self.cobot_connect_btn.config(state=tk.DISABLED)
                self.cobot_disconnect_btn.config(state=tk.NORMAL)
                self.cobot_sequence_btn.config(state=tk.NORMAL)
                self.cobot_home_btn.config(state=tk.NORMAL)
                self.cobot_stop_btn.config(state=tk.NORMAL)
                
            elif status == "connection_failed":
                self._add_cobot_log(f"[ERROR] {message}")
                self.cobot_connect_btn.config(state=tk.NORMAL)
                messagebox.showerror("Connection Error", message)
                
            elif status == "error":
                self._add_cobot_log(f"[ERROR] {message}")
                self.cobot_connect_btn.config(state=tk.NORMAL)
                messagebox.showerror("Error", message)
                
            elif status == "sequence_complete":
                self._add_cobot_log("[OK] Sequence completed successfully")
                self.cobot_progress_var.set(100)
                self.cobot_progress_label.config(text="Sequence Complete", foreground="green")
                messagebox.showinfo("Success", "Robot sequence completed!")
                
        except queue.Empty:
            pass
    
    def cobot_disconnect(self):
        """Disconnect from Cobot"""
        if self.cobot:
            self.cobot.disconnect()
            self.cobot_status.config(text="Disconnected", foreground="red")
            self.cobot_connect_btn.config(state=tk.NORMAL)
            self.cobot_disconnect_btn.config(state=tk.DISABLED)
            self.cobot_sequence_btn.config(state=tk.DISABLED)
            self.cobot_home_btn.config(state=tk.DISABLED)
            self.cobot_stop_btn.config(state=tk.DISABLED)
            self._add_cobot_log("[OK] Disconnected from robot")
    
    def cobot_execute_sequence(self):
        """Execute robot sequence"""
        if not self.cobot or not self.cobot.is_connected:
            messagebox.showerror("Error", "Robot not connected")
            return
        
        self._add_cobot_log("Starting high-speed sequence...")
        self.cobot_sequence_btn.config(state=tk.DISABLED)
        self.cobot_progress_var.set(0)
        self.cobot_progress_label.config(text="Executing sequence...", foreground="blue")
        
        def execute_thread():
            try:
                if self.cobot.execute_sequence("high_speed"):
                    self.cobot_queue.put(("sequence_complete", "OK"))
                else:
                    self.cobot_queue.put(("error", "Sequence execution failed"))
            except Exception as e:
                self.cobot_queue.put(("error", str(e)))
            finally:
                self.cobot_sequence_btn.config(state=tk.NORMAL)
        
        thread = threading.Thread(target=execute_thread, daemon=True)
        thread.start()
        
        self.root.after(100, self.check_cobot_queue)
    
    def cobot_return_home(self):
        """Return robot to home position"""
        if not self.cobot or not self.cobot.is_connected:
            messagebox.showerror("Error", "Robot not connected")
            return
        
        self._add_cobot_log("Moving to home position...")
        self.cobot_home_btn.config(state=tk.DISABLED)
        
        def home_thread():
            try:
                if self.cobot.move_to_point("P1"):
                    self._add_cobot_log("[OK] Robot at home position")
                else:
                    self.cobot_queue.put(("error", "Failed to move to home"))
            except Exception as e:
                self.cobot_queue.put(("error", str(e)))
            finally:
                self.cobot_home_btn.config(state=tk.NORMAL)
        
        thread = threading.Thread(target=home_thread, daemon=True)
        thread.start()
    
    def cobot_emergency_stop(self):
        """Emergency stop"""
        if self.cobot:
            self.cobot.stop_emergency()
            self._add_cobot_log("[STOP] EMERGENCY STOP activated")
            messagebox.showwarning("Emergency Stop", "Robot emergency stop activated!")
    
    def cobot_get_status(self):
        """Get robot status"""
        if not self.cobot:
            messagebox.showerror("Error", "Cobot system not available")
            return
        
        status = self.cobot.get_status()
        status_msg = (
            f"Platform: {status['platform']}\n"
            f"Connected: {status['connected']}\n"
            f"Busy: {status['busy']}\n"
            f"Mode: {'Simulation' if status['simulation_mode'] else 'Real'}\n"
            f"Available Points: {len(status['available_points'])}"
        )
        
        messagebox.showinfo("Robot Status", status_msg)
        self._add_cobot_log(f"Status checked - Platform: {status['platform']}, Connected: {status['connected']}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point"""
    root = tk.Tk()
    app = VisionSystemGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
