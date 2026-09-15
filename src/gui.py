'''
source iosvenv/bin/activate
'''

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

# 添加当前文件夹到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# ===== 缺失的工具类 =====
class ConfigLoader:
    """Load configuration from JSON file"""
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
    
    def _load_config(self, config_path: str):
        try:
            if Path(config_path).exists():
                with open(config_path, 'r') as f:
                    return json.load(f)
            else:
                return {"video": {"folder": "VideoExample"}, "robot": {}}
        except:
            return {"video": {"folder": "VideoExample"}, "robot": {}}


class PlatformUtils:
    """Platform utilities"""
    @staticmethod
    def resolve_path(path_str: str) -> Path:
        """Resolve path, handling OneDrive and special characters"""
        # 处理OneDrive路径
        path_str = path_str.replace("OneDrive - Politecnico di Torino", "OneDrive - Politecnico di Torino")
        return Path(path_str).expanduser().resolve()


# ===== 正确的导入 =====
try:
    from CobotController import CobotController
    COBOT_IMPORTED = True
except Exception as e:
    print(f"⚠️ Cobot import error: {e}")
    COBOT_IMPORTED = False

try:
    from MotionClaudeVisionSystem import DetectionSystem, Config, find_video, get_latest_video
    SYSTEM_IMPORTED = True
    print("✓ Vision system imported successfully")
except Exception as e:
    print(f"⚠️ Vision system import error: {e}")
    print(f"   Error details: {e}")
    SYSTEM_IMPORTED = False


# ===== PLATFORM DETECTION =====
PLATFORM = platform.system()  # 'Windows', 'Darwin' (macOS), 'Linux'
IS_WINDOWS = PLATFORM == 'Windows'
IS_MAC = PLATFORM == 'Darwin'

print(f"Running on {PLATFORM}")


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
            print(f"Error starting recording: {e}")
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


class VisionSystemGUI:
    """Main GUI Application (Cross-Platform)"""
    
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
            print(f"Config load error: {e}")
            self.config = {"video": {"folder": "VideoExample"}, "robot": {}}
        
        # Initialize Vision System if available
        if SYSTEM_IMPORTED:
            try:
                self.vision_config = Config()
                self.vision_system = DetectionSystem(self.vision_config)
                print("✓ Vision system initialized")
            except Exception as e:
                print(f"Vision system initialization error: {e}")
        
        # Initialize Cobot if available
        if COBOT_IMPORTED:
            try:
                self.cobot = CobotController(config=self.config, simulation_mode=False)
            except Exception as e:
                print(f"Cobot initialization error: {e}")
        
        # Build GUI
        self.setup_ui()
        self.update_video_list()
    
    def setup_ui(self):
        """Setup the user interface"""
        
        # Main container with notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ===== TAB 1: VISION SYSTEM =====
        vision_frame = ttk.Frame(notebook, padding="10")
        notebook.add(vision_frame, text="📹 Vision Analysis")
        self.setup_vision_tab(vision_frame)
        
        # ===== TAB 2: COBOT CONTROL =====
        cobot_frame = ttk.Frame(notebook, padding="10")
        notebook.add(cobot_frame, text="🤖 Cobot Control")
        self.setup_cobot_tab(cobot_frame)
        
        # ===== TAB 3: SYSTEM INFO =====
        info_frame = ttk.Frame(notebook, padding="10")
        notebook.add(info_frame, text="ℹ️ System Info")
        self.setup_info_tab(info_frame)
    
    def setup_vision_tab(self, parent):
        """Setup vision analysis tab"""
        
        # ===== TITLE =====
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
        self.status_label = status_label
        
        # ===== BUTTON PANEL =====
        button_frame = ttk.LabelFrame(parent, text="Controls", padding="10")
        button_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Row 1: Video selection
        select_frame = ttk.Frame(button_frame)
        select_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(select_frame, text="Video File:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.video_var = tk.StringVar(value="Select a video...")
        self.video_combo = ttk.Combobox(
            select_frame,
            textvariable=self.video_var,
            state="readonly",
            width=50
        )
        self.video_combo.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        
        browse_btn = ttk.Button(select_frame, text="Browse", command=self.browse_video)
        browse_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        refresh_btn = ttk.Button(select_frame, text="Refresh", command=self.update_video_list)
        refresh_btn.pack(side=tk.LEFT)
        
        # Row 2: Recording
        record_frame = ttk.Frame(button_frame)
        record_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(record_frame, text="Recording:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.record_btn = ttk.Button(
            record_frame,
            text="Start Recording",
            command=self.start_recording,
            width=15
        )
        self.record_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.record_status = ttk.Label(record_frame, text="Not recording", foreground="gray")
        self.record_status.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Row 3: Analysis
        analysis_frame = ttk.Frame(button_frame)
        analysis_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.analyze_btn = ttk.Button(
            analysis_frame,
            text="▶️ Start Analysis",
            command=self.start_analysis,
            width=20
        )
        self.analyze_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            analysis_frame,
            variable=self.progress_var,
            maximum=100,
            length=400
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # ===== INSTRUCTIONS PANEL =====
        instr_frame = ttk.LabelFrame(parent, text="Current Operation Instructions", padding="10")
        instr_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        scrollbar = ttk.Scrollbar(instr_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.instr_text = tk.Text(
            instr_frame,
            height=8,
            font=("Courier", 10),
            yscrollcommand=scrollbar.set,
            wrap=tk.WORD
        )
        self.instr_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.instr_text.yview)
        
        self.display_instruction("Vision Analysis System Ready\n\n"
                                "Instructions:\n"
                                "1. Select a video file or record a new one\n"
                                "2. Click 'Refresh' to see available videos")
        
        # ===== RESULTS PANEL =====
        result_frame = ttk.LabelFrame(parent, text="Analysis Results", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        
        result_scrollbar = ttk.Scrollbar(result_frame)
        result_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.result_text = tk.Text(
            result_frame,
            height=8,
            font=("Courier", 9),
            yscrollcommand=result_scrollbar.set,
            wrap=tk.WORD
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)
        result_scrollbar.config(command=self.result_text.yview)
        
        self.display_result("No analysis results yet.")
    
    def setup_cobot_tab(self, parent):
        """Setup Cobot control tab"""
        
        # ===== TITLE =====
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = ttk.Label(
            title_frame,
            text="Cobot Robot Control",
            font=("Arial", 18, "bold")
        )
        title_label.pack(side=tk.LEFT)
        
        self.cobot_status = ttk.Label(
            title_frame,
            text="Disconnected",
            font=("Arial", 10),
            foreground="red"
        )
        self.cobot_status.pack(side=tk.RIGHT)
        
        # ===== CONNECTION PANEL =====
        conn_frame = ttk.LabelFrame(parent, text="Connection Control", padding="10")
        conn_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.cobot_connect_btn = ttk.Button(
            conn_frame,
            text="🔌 Connect Robot",
            command=self.cobot_connect,
            width=20
        )
        self.cobot_connect_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.cobot_disconnect_btn = ttk.Button(
            conn_frame,
            text="🔌 Disconnect Robot",
            command=self.cobot_disconnect,
            state=tk.DISABLED,
            width=20
        )
        self.cobot_disconnect_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        cobot_test_btn = ttk.Button(
            conn_frame,
            text="📋 Get Status",
            command=self.cobot_get_status,
            width=20
        )
        cobot_test_btn.pack(side=tk.LEFT)
        
        # ===== OPERATION PANEL =====
        op_frame = ttk.LabelFrame(parent, text="Robot Operations", padding="10")
        op_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.cobot_sequence_btn = ttk.Button(
            op_frame,
            text="▶️ Execute High-Speed Sequence",
            command=self.cobot_execute_sequence,
            state=tk.DISABLED,
            width=30
        )
        self.cobot_sequence_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.cobot_home_btn = ttk.Button(
            op_frame,
            text="🏠 Return to Home",
            command=self.cobot_return_home,
            state=tk.DISABLED,
            width=20
        )
        self.cobot_home_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.cobot_stop_btn = ttk.Button(
            op_frame,
            text="🛑 Emergency Stop",
            command=self.cobot_emergency_stop,
            state=tk.DISABLED,
            width=20
        )
        self.cobot_stop_btn.pack(side=tk.LEFT)
        
        # ===== PROGRESS PANEL =====
        progress_frame = ttk.LabelFrame(parent, text="Operation Progress", padding="10")
        progress_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.cobot_progress_var = tk.DoubleVar()
        self.cobot_progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.cobot_progress_var,
            maximum=100
        )
        self.cobot_progress_bar.pack(fill=tk.X, expand=True)
        
        self.cobot_progress_label = ttk.Label(progress_frame, text="Ready", foreground="blue")
        self.cobot_progress_label.pack(pady=(5, 0))
        
        # ===== LOG PANEL =====
        log_frame = ttk.LabelFrame(parent, text="Operation Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        log_scrollbar = ttk.Scrollbar(log_frame)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.cobot_log_text = tk.Text(
            log_frame,
            height=12,
            font=("Courier", 9),
            yscrollcommand=log_scrollbar.set,
            wrap=tk.WORD
        )
        self.cobot_log_text.pack(fill=tk.BOTH, expand=True)
        log_scrollbar.config(command=self.cobot_log_text.yview)
        
        self._add_cobot_log("Cobot system ready")
        self._add_cobot_log("Status: Waiting for connection")
    
    def setup_info_tab(self, parent):
        """Setup system information tab"""
        
        info_frame = ttk.LabelFrame(parent, text="System Information", padding="20")
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        info_text = tk.Text(info_frame, height=20, font=("Courier", 10), wrap=tk.WORD)
        info_text.pack(fill=tk.BOTH, expand=True)
        
        # Gather system info
        info = self._gather_system_info()
        info_text.insert(1.0, info)
        info_text.config(state=tk.DISABLED)
    
    def _gather_system_info(self) -> str:
        """Gather system information"""
        import platform as plat
        
        lines = []
        lines.append("="*60)
        lines.append("SYSTEM INFORMATION")
        lines.append("="*60)
        lines.append(f"\nPlatform: {plat.system()} {plat.release()}")
        lines.append(f"Python Version: {plat.python_version()}")
        lines.append(f"Machine: {plat.machine()}")
        lines.append(f"Processor: {plat.processor()}")
        
        lines.append("\n" + "="*60)
        lines.append("CONFIGURATION")
        lines.append("="*60)
        
        if self.config:
            lines.append(f"\nRobot IP: {self.config.get('robot', {}).get('ip', 'N/A')}")
            lines.append(f"Robot Port: {self.config.get('robot', {}).get('port', 'N/A')}")
            lines.append(f"Video Folder: {self.config.get('video', {}).get('folder', 'N/A')}")
        
        lines.append("\n" + "="*60)
        lines.append("COBOT STATUS")
        lines.append("="*60)
        
        if self.cobot:
            status = self.cobot.get_status()
            lines.append(f"\nConnected: {status['connected']}")
            lines.append(f"Busy: {status['busy']}")
            lines.append(f"Simulation Mode: {status['simulation_mode']}")
            lines.append(f"Available Points: {len(status['available_points'])}")
        else:
            lines.append("\nCobot system not available")
        
        return "\n".join(lines)
    
    # ===== VISION METHODS =====
    def display_instruction(self, text: str):
        """Update instruction display"""
        self.instr_text.config(state=tk.NORMAL)
        self.instr_text.delete(1.0, tk.END)
        self.instr_text.insert(1.0, text)
        self.instr_text.config(state=tk.NORMAL)
    
    def display_result(self, text: str):
        """Update result display"""
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(1.0, text)
        self.result_text.config(state=tk.NORMAL)
    
    def update_video_list(self):
        """Update available videos list"""
        try:
            video_dir = self.config.get('video', {}).get('folder', 'VideoExample')
            video_path = PlatformUtils.resolve_path(video_dir)
            
            if video_path.exists():
                videos = [f for f in os.listdir(video_path) 
                         if f.lower().endswith(('.mp4', '.avi', '.mov'))]
                self.video_combo['values'] = videos
                if videos:
                    self.video_combo.set(videos[0])
        except Exception as e:
            print(f"Error updating video list: {e}")
    
    def browse_video(self):
        """Browse for video file"""
        filetypes = (("Video Files", "*.mp4 *.avi *.mov"), ("All Files", "*.*"))
        filename = filedialog.askopenfilename(
            title="Select a video file",
            filetypes=filetypes
        )
        if filename:
            self.video_var.set(filename)
    
    def start_recording(self):
        """Start or stop video recording"""
        if not self.is_recording:
            filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            video_dir = self.config.get('video', {}).get('folder', 'VideoExample')
            video_path = PlatformUtils.resolve_path(video_dir)
            
            video_path.mkdir(parents=True, exist_ok=True)
            output_path = str(video_path / filename)
            
            self.recorder = VideoRecorder(output_path)
            
            if self.recorder.start_recording():
                self.is_recording = True
                self.record_btn.config(text="Stop Recording")
                self.record_status.config(text="🔴 RECORDING...", foreground="red")
                
                record_thread = threading.Thread(target=self.recorder.record_loop, daemon=True)
                record_thread.start()
            else:
                messagebox.showerror("Recording Error", 
                                   "Failed to start recording. Check webcam access.")
        else:
            self.is_recording = False
            self.record_btn.config(text="Start Recording")
            self.record_status.config(text="✓ Recording saved", foreground="green")
            
            if self.recorder:
                self.recorder.stop_recording()
            
            self.update_video_list()
    
    def start_analysis(self):
        """Start video analysis"""
        if not SYSTEM_IMPORTED or not self.vision_system:
            messagebox.showerror("Error", "Vision system not available")
            return
        
        video_selection = self.video_var.get()
        if video_selection == "Select a video..." or not video_selection:
            messagebox.showwarning("No Video Selected", "Please select a video file first.")
            return
        
        # Extract just the filename if full path was selected
        if os.path.exists(video_selection):
            video_name = os.path.basename(video_selection)
        else:
            video_name = video_selection
        
        # Disable button during analysis
        self.analyze_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)
        
        self.display_instruction(
            "ANALYSIS IN PROGRESS\n\n"
            f"Processing: {video_name}\n\n"
            "Current Operation:\n"
            "1. Extracting key frames from video...\n"
            "2. Encoding frames to base64...\n"
            "3. Sending to Claude Vision API...\n"
            "4. Analyzing spatial relationships...\n"
            "5. Evaluating safety compliance...\n"
            "6. Generating detailed report...\n\n"
            "Please wait..."
        )
        
        # Run analysis in background thread
        analysis_thread = threading.Thread(
            target=self._run_analysis,
            args=(video_name,),
            daemon=True
        )
        analysis_thread.start()
    
    def _run_analysis(self, video_name: str):
        """Run analysis in background"""
        try:
            self.progress_var.set(20)
            self.root.update()
            
            # 获取完整的视频路径
            video_dir = self.config.get('video', {}).get('folder', 'VideoExample')
            video_path = PlatformUtils.resolve_path(video_dir)
            full_video_path = str(video_path / video_name)
            
            # 如果video_name已经是完整路径，直接使用
            if os.path.exists(video_name):
                full_video_path = video_name
            
            # 检查文件是否存在
            if not os.path.exists(full_video_path):
                self.result_queue.put(("error", f"Video file not found: {full_video_path}"))
                self.check_result_queue()
                return
            
            # 调用vision系统分析
            result = self.vision_system.process_video(video_name)
            
            self.progress_var.set(100)
            
            if result:
                # Format results
                result_text = self._format_result(result)
                self.result_queue.put(("success", result_text))
            else:
                self.result_queue.put(("error", "Analysis failed. Video processing error."))
        
        except Exception as e:
            import traceback
            error_msg = f"Analysis error: {str(e)}\n{traceback.format_exc()}"
            self.result_queue.put(("error", error_msg))
        
        finally:
            self.check_result_queue()
    
    def check_result_queue(self):
        """Check for analysis results"""
        try:
            status, message = self.result_queue.get_nowait()
            
            if status == "success":
                self.display_result(message)
                messagebox.showinfo("Analysis Complete", 
                                  "Video analysis finished successfully!")
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
        
        lines.append(f"\n📊 SCORES:")
        lines.append(f"  Safety Score:     {result.safety_score:.1f}/100")
        lines.append(f"  Spatial Score:    {result.spatial_score:.1f}/100")
        lines.append(f"  Operation Score:  {result.operation_score:.1f}/100")
        lines.append(f"  Overall Score:    {result.overall_score:.1f}/100")
        
        lines.append(f"\n🔍 ISSUES DETECTED:")
        lines.append(f"  Total Differences: {len(result.differences)}")
        lines.append(f"  Critical Issues:   {len(result.critical)}")
        lines.append(f"  Major Issues:      {len(result.major)}")
        lines.append(f"  Minor Issues:      {len(result.minor)}")
        lines.append(f"  Negligible:        {len(result.negligible)}")
        
        if result.critical:
            lines.append(f"\n🔴 CRITICAL ISSUES:")
            for d in result.critical:
                lines.append(f"  • {d.description} [{d.category}]")
        
        if result.major:
            lines.append(f"\n🟠 MAJOR ISSUES:")
            for d in result.major:
                lines.append(f"  • {d.description} [{d.category}]")
        
        lines.append(f"\n📋 DECISION:")
        lines.append(f"  Result: {'✅ PASS' if result.decision == 'PASS' else '❌ FAIL'}")
        lines.append(f"  Reason: {result.reason}")
        
        lines.append(f"\n💡 SUMMARY:")
        lines.append(f"{result.summary}")
        
        if result.ground_truth:
            lines.append(f"\n✔️ VALIDATION:")
            lines.append(f"  Ground Truth: {result.ground_truth}")
            lines.append(f"  Prediction:   {'✅ CORRECT' if result.correct else '❌ INCORRECT'}")
        
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
                self._add_cobot_log("✓ Robot connected successfully")
                self.cobot_status.config(text="Connected", foreground="green")
                self.cobot_connect_btn.config(state=tk.DISABLED)
                self.cobot_disconnect_btn.config(state=tk.NORMAL)
                self.cobot_sequence_btn.config(state=tk.NORMAL)
                self.cobot_home_btn.config(state=tk.NORMAL)
                self.cobot_stop_btn.config(state=tk.NORMAL)
                
            elif status == "connection_failed":
                self._add_cobot_log(f"✗ {message}")
                self.cobot_connect_btn.config(state=tk.NORMAL)
                messagebox.showerror("Connection Error", message)
                
            elif status == "error":
                self._add_cobot_log(f"✗ Error: {message}")
                self.cobot_connect_btn.config(state=tk.NORMAL)
                messagebox.showerror("Error", message)
                
            elif status == "sequence_complete":
                self._add_cobot_log("✓ Sequence completed successfully")
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
            self._add_cobot_log("Disconnected from robot")
    
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
                    self._add_cobot_log("✓ Robot at home position")
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
            self._add_cobot_log("🛑 EMERGENCY STOP activated")
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


def main():
    """Main entry point"""
    root = tk.Tk()
    app = VisionSystemGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()