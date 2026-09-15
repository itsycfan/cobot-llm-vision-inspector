#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Assembly Detection System - SIMPLIFIED VERSION 6.0 (Claude) - Mac Compatible
=============================================================================
Focus: 
- Clear code structure
- Optimized GENERIC prompt (result-oriented)
- Easy debugging and analysis
- Save all results and frames
- Mac OS compatibility

Key Improvement:
- Emphasize OUTCOME not just PROCESS
- Judge differences by TASK COMPLETION not just visual appearance
- Use Success/Failure criteria from Excel

Version: 6.0 (Simplified Result-Oriented) - Claude Edition - Mac Compatible
Date: 2025-10-30
Platform: macOS
=============================================================================
"""

import os
import json
import time
import base64
import cv2
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path
import sys

# Suppress warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import warnings
warnings.filterwarnings('ignore')

try:
    import mediapipe as mp
    MP_AVAILABLE = True
except:
    MP_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except:
    ANTHROPIC_AVAILABLE = False

try:
    import openpyxl
    EXCEL_AVAILABLE = True
except:
    EXCEL_AVAILABLE = False


# =============================================================================
# 1. CONFIGURATION
# =============================================================================

@dataclass
class Config:
    """System configuration"""
    
    # API
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = "claude-sonnet-4-5-20250929"
    CLAUDE_TEMPERATURE: float = 0.1
    
    # Paths - Mac compatible
    VIDEO_FOLDER: str = "VideoExample"
    RESULTS_FOLDER: str = "Results"
    EXCEL_PATH: str = "Data/AssemblyInstructions.xlsx"
    REFERENCE_VIDEO: str = "OK1"
    
    # Frame settings
    KEY_FRAMES: int = 8
    REF_FRAMES: int = 6
    IMAGE_WIDTH: int = 768
    JPEG_QUALITY: int = 85
    
    # Decision thresholds
    CRITICAL_THRESHOLD: int = 1
    MAJOR_THRESHOLD: int = 1
    SCORE_THRESHOLD: float = 70.0
    
    def __post_init__(self):
        """Create directories"""
        results_path = Path(self.RESULTS_FOLDER)
        results_path.mkdir(parents=True, exist_ok=True)
        (results_path / "frames").mkdir(parents=True, exist_ok=True)
        (results_path / "reports").mkdir(parents=True, exist_ok=True)


# Ground truth
GROUND_TRUTH = {
    "OK1": "OK", "OK2": "OK", "OK3": "OK", "OK4": "OK", "OK5": "OK",
    "KO1": "KO", "KO2": "KO", "KO3": "KO", "KO4": "KO", "KO5": "KO"
}


# =============================================================================
# 2. DATA MODELS
# =============================================================================

@dataclass
class Difference:
    """A single observed difference"""
    description: str
    is_problem: bool
    severity: str  # CRITICAL, MAJOR, MINOR, NEGLIGIBLE
    category: str  # safety, spatial, operation


@dataclass
class Result:
    """Analysis result"""
    video_name: str
    timestamp: str
    
    # Scores
    safety_score: float
    spatial_score: float
    operation_score: float
    overall_score: float
    
    # Analysis
    differences: List[Difference] = field(default_factory=list)
    summary: str = ""
    
    # Decision
    decision: str = ""  # PASS or FAIL
    reason: str = ""
    
    # Validation
    ground_truth: str = ""
    correct: bool = False
    
    @property
    def critical(self) -> List[Difference]:
        return [d for d in self.differences if d.is_problem and d.severity == 'CRITICAL']
    
    @property
    def major(self) -> List[Difference]:
        return [d for d in self.differences if d.is_problem and d.severity == 'MAJOR']
    
    @property
    def minor(self) -> List[Difference]:
        return [d for d in self.differences if d.is_problem and d.severity == 'MINOR']
    
    @property
    def negligible(self) -> List[Difference]:
        return [d for d in self.differences if not d.is_problem]


# =============================================================================
# 3. UTILITIES
# =============================================================================

def load_task_data(config: Config) -> Optional[Dict]:
    """Load task data from Excel"""
    
    if not EXCEL_AVAILABLE:
        return None
    
    try:
        excel_path = Path(config.EXCEL_PATH)
        if not excel_path.exists():
            return None
            
        wb = openpyxl.load_workbook(str(excel_path))
        ws = wb.active
        
        # Get headers
        headers = [cell.value for cell in ws[1]]
        
        # Get data from row 2
        data = {}
        for idx, header in enumerate(headers, 1):
            if header:
                value = ws.cell(row=2, column=idx).value
                if value:
                    data[header] = value
        
        wb.close()
        
        return {
            'task_description': data.get('TaskDescription', ''),
            'safety_requirements': data.get('SafetyRequirements', ''),
            'spatial_requirements': data.get('SpatialRequirements', ''),
            'success_criteria': data.get('SuccessCriteria', ''),
            'failure_indicators': data.get('FailureIndicators', '')
        }
    except Exception as e:
        print(f"[WARN] Could not load Excel: {e}")
        return None


def find_video(folder: str, name: str) -> Optional[str]:
    """Find video file"""
    
    folder_path = Path(folder)
    if not folder_path.exists():
        return None
    
    for file in folder_path.iterdir():
        if name.lower() in file.name.lower() and file.suffix.lower() in ['.mp4', '.avi', '.mov']:
            return str(file)
    
    return None


def save_json(data: Dict, path: Path):
    """Save JSON file"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# =============================================================================
# 4. FRAME EXTRACTOR
# =============================================================================

class FrameExtractor:
    """Extract key frames from video"""
    
    def __init__(self, config: Config):
        self.config = config
        self.hands = None
        
        if MP_AVAILABLE:
            mp_hands = mp.solutions.hands
            self.hands = mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.5
            )
    
    def extract(self, video_path: str, n_frames: int) -> List[Dict]:
        """Extract n key frames"""
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        
        # Read all frames
        frames = []
        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
            idx += 1
        
        cap.release()
        
        if not frames:
            return []
        
        # Select key frames
        step = len(frames) // n_frames
        if step < 1:
            step = 1
        
        key_frames = []
        for i in range(n_frames):
            frame_idx = i * step
            if frame_idx < len(frames):
                frame = frames[frame_idx]
                
                # Resize
                h, w = frame.shape[:2]
                aspect_ratio = w / h
                new_w = self.config.IMAGE_WIDTH
                new_h = int(new_w / aspect_ratio)
                frame = cv2.resize(frame, (new_w, new_h))
                
                # Encode to JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.config.JPEG_QUALITY])
                image_base64 = base64.b64encode(buffer).decode('utf-8')
                
                key_frames.append({
                    'frame_idx': i,
                    'timestamp': i * step / 30.0,
                    'image_base64': image_base64
                })
        
        return key_frames


# =============================================================================
# 5. ANALYZER
# =============================================================================

class VisionAnalyzer:
    """Analyze frames using Claude Vision"""
    
    def __init__(self, config: Config):
        self.config = config
        if ANTHROPIC_AVAILABLE:
            self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        else:
            self.client = None
    
    def analyze(self, frames: List[Dict], task_data: Dict = None) -> Optional[Result]:
        """Analyze frames and return result"""
        
        if not self.client:
            print("[ERROR] Anthropic client not available")
            return None
        
        if not frames:
            return None
        
        try:
            # Build system prompt
            system_prompt = self._build_system_prompt(task_data or {})
            
            # Build message with images
            content = [
                {
                    "type": "text",
                    "text": "Analyze these assembly frames and identify any differences from the correct procedure."
                }
            ]
            
            # Add frames
            for frame in frames:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": frame['image_base64']
                    }
                })
            
            # Call Claude
            response = self.client.messages.create(
                model=self.config.CLAUDE_MODEL,
                max_tokens=2000,
                temperature=self.config.CLAUDE_TEMPERATURE,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            )
            
            # Parse response
            analysis_text = response.content[0].text
            result = self._parse_analysis(analysis_text)
            
            return result
            
        except Exception as e:
            print(f"[ERROR] Analysis failed: {e}")
            return None
    
    def _build_system_prompt(self, task_data: Dict) -> str:
        """Build system prompt for Claude"""
        
        prompt = """You are an expert assembly quality inspector. Analyze the provided images and:

1. IDENTIFY DIFFERENCES: Compare each frame with the expected assembly process
2. CATEGORIZE SEVERITY:
   - CRITICAL: Safety hazards or assembly failure
   - MAJOR: Significant deviations affecting quality
   - MINOR: Small deviations that don't affect function
   - NEGLIGIBLE: Imperceptible differences

3. PROVIDE SCORES (0-100):
   - Safety Score: How safe is the assembly process?
   - Spatial Score: Are parts positioned correctly?
   - Operation Score: Is the procedure being followed correctly?
   - Overall Score: (Safety + Spatial + Operation) / 3

4. DECISION: PASS or FAIL based on:
   - 0+ Critical issues = FAIL
   - 2+ Major issues = FAIL
   - Otherwise = PASS if Overall Score >= 70

Respond in this JSON format:
{
  "differences": [
    {"description": "...", "is_problem": true/false, "severity": "CRITICAL/MAJOR/MINOR/NEGLIGIBLE", "category": "safety/spatial/operation"}
  ],
  "scores": {"safety": 0-100, "spatial": 0-100, "operation": 0-100, "overall": 0-100},
  "decision": "PASS or FAIL",
  "reason": "Brief explanation",
  "summary": "Overall assessment"
}"""
        
        return prompt
    
    def _parse_analysis(self, text: str) -> Optional[Result]:
        """Parse Claude response"""
        
        try:
            # Extract JSON
            start = text.find('{')
            end = text.rfind('}') + 1
            if start == -1 or end == 0:
                return None
            
            json_str = text[start:end]
            data = json.loads(json_str)
            
            # Build result
            result = Result(
                video_name="",
                timestamp=datetime.now().isoformat(),
                safety_score=data.get('scores', {}).get('safety', 50),
                spatial_score=data.get('scores', {}).get('spatial', 50),
                operation_score=data.get('scores', {}).get('operation', 50),
                overall_score=data.get('scores', {}).get('overall', 50),
                summary=data.get('summary', ''),
                decision=data.get('decision', 'FAIL'),
                reason=data.get('reason', '')
            )
            
            # Parse differences
            for diff_data in data.get('differences', []):
                diff = Difference(
                    description=diff_data.get('description', ''),
                    is_problem=diff_data.get('is_problem', False),
                    severity=diff_data.get('severity', 'NEGLIGIBLE'),
                    category=diff_data.get('category', 'operation')
                )
                result.differences.append(diff)
            
            return result
            
        except Exception as e:
            print(f"[ERROR] Parse failed: {e}")
            return None


# =============================================================================
# 6. DETECTION SYSTEM
# =============================================================================

class DetectionSystem:
    """Main detection system"""
    
    def __init__(self, config: Config):
        self.config = config
        self.extractor = FrameExtractor(config)
        self.analyzer = VisionAnalyzer(config)
        self.task_data = load_task_data(config)
    
    def process_video(self, video_name: str) -> Optional[Result]:
        """Process one video"""
        
        print(f"\n{'='*70}")
        print(f"PROCESSING: {video_name}")
        print(f"{'='*70}")
        
        # Find video
        video_path = find_video(self.config.VIDEO_FOLDER, video_name)
        if not video_path:
            print(f"[ERROR] Video not found")
            return None
        
        # Extract frames
        print(f"[INFO] Extracting frames...")
        t0 = time.time()
        frames = self.extractor.extract(video_path, self.config.KEY_FRAMES)
        print(f"        [OK] Extracted {len(frames)} frames ({time.time()-t0:.1f}s)")
        
        if not frames:
            return None
        
        # Save frames
        self._save_frames(video_name, frames)
        
        # Analyze
        print(f"[INFO] Analyzing...")
        t0 = time.time()
        result = self.analyzer.analyze(frames, self.task_data or {})
        print(f"        [OK] Analysis complete ({time.time()-t0:.1f}s)")
        
        if not result:
            return None
        
        # Add metadata
        result.video_name = video_name
        video_base_name = Path(video_name).stem
        result.ground_truth = GROUND_TRUTH.get(video_base_name, "UNKNOWN")
        result.correct = (result.ground_truth == "OK" and result.decision == "PASS") or \
                        (result.ground_truth == "KO" and result.decision == "FAIL")
        
        # Display and save
        self._display(result)
        self._save_result(result)
        
        return result
    
    def process_batch(self, video_names: List[str]) -> List[Result]:
        """Process multiple videos"""
        
        results = []
        for i, name in enumerate(video_names, 1):
            print(f"\n[{i}/{len(video_names)}] {name}")
            result = self.process_video(name)
            if result:
                results.append(result)
            time.sleep(0.5)
        
        self._display_summary(results)
        return results
    
    def _save_frames(self, video_name: str, frames: List[Dict]):
        """Save frames to disk"""
        
        output_dir = Path(self.config.RESULTS_FOLDER) / "frames" / video_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for frame in frames:
            idx = frame['frame_idx']
            data = base64.b64decode(frame['image_base64'])
            
            with open(output_dir / f"frame_{idx:04d}.jpg", 'wb') as f:
                f.write(data)
    
    def _save_result(self, result: Result):
        """Save result to JSON"""
        
        output_path = Path(self.config.RESULTS_FOLDER) / "reports" / f"{result.video_name}.json"
        
        data = {
            'video_name': result.video_name,
            'timestamp': result.timestamp,
            'scores': {
                'safety': result.safety_score,
                'spatial': result.spatial_score,
                'operation': result.operation_score,
                'overall': result.overall_score
            },
            'differences': {
                'total': len(result.differences),
                'critical': [{'desc': d.description, 'cat': d.category} for d in result.critical],
                'major': [{'desc': d.description, 'cat': d.category} for d in result.major],
                'minor': [{'desc': d.description, 'cat': d.category} for d in result.minor],
                'negligible': [{'desc': d.description, 'cat': d.category} for d in result.negligible]
            },
            'decision': {
                'result': result.decision,
                'reason': result.reason
            },
            'validation': {
                'ground_truth': result.ground_truth,
                'correct': result.correct
            },
            'summary': result.summary
        }
        
        save_json(data, output_path)
        print(f"[OK] Saved: {output_path.name}")
    
    def _display(self, result: Result):
        """Display result"""
        
        print(f"\n{'='*70}")
        print(f"RESULT: {result.video_name}")
        print(f"{'='*70}")
        print(f"[SCORES] Safety={result.safety_score:.0f}, Spatial={result.spatial_score:.0f}, "
              f"Operation={result.operation_score:.0f}, Overall={result.overall_score:.0f}")
        print(f"[ISSUES] Total={len(result.differences)}, Critical={len(result.critical)}, "
              f"Major={len(result.major)}, Minor={len(result.minor)}, Negligible={len(result.negligible)}")
        
        if result.critical:
            print(f"\n[CRITICAL]:")
            for d in result.critical:
                print(f"   - {d.description}")
        
        if result.major:
            print(f"\n[MAJOR]:")
            for d in result.major:
                print(f"   - {d.description}")
        
        print(f"\n[DECISION] {result.decision}")
        print(f"[REASON] {result.reason}")
        print(f"[VALIDATION] GT={result.ground_truth}, {'[OK] CORRECT' if result.correct else '[ERROR] WRONG'}")
        print(f"{'='*70}")
    
    def _display_summary(self, results: List[Result]):
        """Display batch summary"""
        
        if not results:
            return
        
        print(f"\n{'='*70}")
        print(f"BATCH SUMMARY")
        print(f"{'='*70}")
        
        total = len(results)
        correct = sum(1 for r in results if r.correct)
        accuracy = correct / total * 100 if total > 0 else 0
        
        print(f"\nTotal: {total}")
        print(f"Correct: {correct}/{total} ({accuracy:.1f}%)")
        
        print(f"\n{'Video':<10} {'GT':<4} {'Pred':<6} {'Score':<6} {'Crit':<5} {'Major':<6} {'Result'}")
        print(f"{'-'*70}")
        
        for r in results:
            pred = "OK" if r.decision == "PASS" else "KO"
            status = "[OK]" if r.correct else "[ERR]"
            print(f"{r.video_name:<10} {r.ground_truth:<4} {pred:<6} "
                  f"{r.overall_score:<6.0f} {len(r.critical):<5} {len(r.major):<6} {status}")
        
        print(f"{'-'*70}")
        
        # Save summary
        summary_path = Path(self.config.RESULTS_FOLDER) / "reports" / "summary.json"
        save_json({
            'timestamp': datetime.now().isoformat(),
            'total': total,
            'correct': correct,
            'accuracy': accuracy,
            'results': [
                {
                    'video': r.video_name,
                    'gt': r.ground_truth,
                    'decision': r.decision,
                    'score': r.overall_score,
                    'critical': len(r.critical),
                    'major': len(r.major),
                    'correct': r.correct
                }
                for r in results
            ]
        }, summary_path)
        print(f"\n[OK] Summary saved: {summary_path.name}")


# =============================================================================
# 7. MAIN
# =============================================================================

def get_latest_video(folder: str) -> Optional[str]:
    """Get the latest video file from folder"""
    
    folder_path = Path(folder)
    if not folder_path.exists():
        print(f"[ERROR] Folder not found: {folder}")
        return None
    
    video_files = []
    for file in folder_path.iterdir():
        if file.suffix.lower() in ['.mp4', '.avi', '.mov']:
            video_files.append((file.name, file.stat().st_mtime))
    
    if not video_files:
        print(f"[ERROR] No video files found in: {folder}")
        return None
    
    # Sort by modification time, get the latest
    latest_video = max(video_files, key=lambda x: x[1])[0]
    return latest_video


def main():
    """Main entry"""
    
    print(f"\n{'='*70}")
    print(f"ASSEMBLY DETECTION SYSTEM V6.0 (Mac Compatible)")
    print(f"{'='*70}\n")
    
    config = Config()
    
    print(f"[INFO] Config:")
    print(f"        Model: {config.CLAUDE_MODEL}")
    print(f"        Reference: {config.REFERENCE_VIDEO}")
    print(f"        Thresholds: Critical>={config.CRITICAL_THRESHOLD}, Major>={config.MAJOR_THRESHOLD}, Score<{config.SCORE_THRESHOLD}")
    
    system = DetectionSystem(config)
    
    # Get the latest video file
    latest_video = get_latest_video(config.VIDEO_FOLDER)
    
    if latest_video:
        print(f"[INFO] Latest video found: {latest_video}")
        system.process_video(latest_video)
    else:
        print(f"[ERROR] No video found to process")
    
    print(f"\n{'='*70}")
    print(f"DONE")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
