#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
COBOT CONTROLLER - Independent Module
=============================================================================
Extracted and simplified Cobot control system for UR10 robot
Features:
- Robot connection management
- Motion control with predefined points
- Timing and logging
- Simulation mode support

Author: Based on Tiziano's original Cobot system
Date: 2025-10-29
=============================================================================
"""

import socket
import math
import time
import json
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ==================== CONFIGURATION ====================
ROBOT_IP = "10.10.220.251"
ROBOT_PORT = 30002
SIMULATION_MODE = False  # Set to True for testing without real robot


# ==================== LOGGING SYSTEM ====================
class TimingLogger:
    """Simple timing and logging system for Cobot operations"""
    
    def __init__(self):
        self.start_time = None
        self.steps = []
        self.current_step = None
        self.step_start_time = None
        
        # Setup logging
        log_filename = f'cobot_control_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def start_operation(self, operation_name: str):
        """Start timing an operation"""
        self.start_time = time.time()
        self.steps = []
        self.logger.info(f"🚀 STARTING OPERATION: {operation_name}")
    
    def start_step(self, step_name: str):
        """Start timing a specific step"""
        self.current_step = step_name
        self.step_start_time = time.time()
        self.logger.info(f"▶️ STARTING STEP: {step_name}")
    
    def end_step(self, step_name: str = None):
        """End timing of current step"""
        if self.step_start_time and self.current_step:
            duration = time.time() - self.step_start_time
            
            step_data = {
                'step': self.current_step,
                'duration': duration
            }
            self.steps.append(step_data)
            
            self.logger.info(f"✅ COMPLETED: {self.current_step} - Duration: {duration:.2f}s")
            
            self.current_step = None
            self.step_start_time = None
    
    def end_operation(self, operation_name: str) -> Dict:
        """End operation and generate report"""
        if self.start_time:
            total_duration = time.time() - self.start_time
            
            report = {
                'operation_name': operation_name,
                'timestamp': datetime.now().isoformat(),
                'total_duration': total_duration,
                'steps': self.steps
            }
            
            self.logger.info(f"🎯 OPERATION COMPLETED: {operation_name} - Total: {total_duration:.2f}s")
            return report
        
        return None
    
    def add_message(self, message: str):
        """Log a message"""
        self.logger.info(message)
        print(f"[COBOT] {message}")


# ==================== COBOT CONTROL SYSTEM ====================
class CobotController:
    """Main Cobot control system for UR10 robot"""
    
    def __init__(self, simulation_mode: bool = SIMULATION_MODE):
        """
        Initialize Cobot controller
        
        Args:
            simulation_mode: If True, simulate robot without real connection
        """
        self.robot_conn = None
        self.simulation_mode = simulation_mode
        self.timing_logger = TimingLogger()
        self.is_connected = False
        self.is_busy = False
        
        # Robot points configuration (angles in degrees)
        self.robot_points = {
            "P1":  [-0.12,  -110.68, -97.23,  -62.58, -85.68, -89.16],
            "P2":  [-35.1,  -99.5,   -109.7,  -63.74, -86.76, -54.12],
            "P3":  [-34.88, -96.67,  -106.45, -69.81, -86.75, -54.35],
            "P4":  [-34.77, -101.22, -112.36, -59.33, -86.75, -54.45],
            "P5":  [-19.5,  -109.39, -98.15,  -64.37, -86.09, -70.14],
            "P6":  [-18.32, -109.97, -96.01,  -69.08, -86.16, -68.84],
            "P7":  [-18.79, -108.64, -93.37,  -73.07, -86.19, -68.39],
            "P8":  [1.05,   -98.84,  -112.58, -58.99, -85.66, -90.34],
            "P9":  [1.11,   -133.62, -60.36,  -76.42, -85.68, -90.4],
            "P10": [-17.16, -157.33, 9.79,   -123.44, -85.85, -77.3],
            "P11": [-23.4,  -111.44, -81.29,  -81.23, -88.24, -76.47],
            "P12": [-17.76, -167.71, 32.49,  -138.53, -87.83, -82.09],
            "P13": [-17.13, -113.56, -78.31,  -81.86, -87.82, -82.71],
            "P14": [-19.15, -165.07, 25.42,  -133.48, -87.91, -80.76],
            "P15": [-21.68, -119.04, -71.47,  -82.15, -87.23, -73.33],
            "P16": [-0.12,  -110.68, -97.23,  -62.58, -85.68, -89.16]
        }
        
        self.timing_logger.add_message(
            f"CobotController initialized - Mode: {'SIMULATION' if simulation_mode else 'REAL'}"
        )
    
    def connect(self) -> bool:
        """
        Connect to the robot
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        self.timing_logger.start_step("Connect to robot")
        
        if self.simulation_mode:
            self.timing_logger.add_message("🎮 Simulation mode - Virtual robot connected")
            self.robot_conn = "SIMULATED_CONNECTION"
            self.is_connected = True
            self.timing_logger.end_step()
            return True
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(8.0)
            sock.connect((ROBOT_IP, ROBOT_PORT))
            time.sleep(0.3)
            
            self.robot_conn = sock
            self.is_connected = True
            
            self.timing_logger.add_message(f"🤖 Connected to robot at {ROBOT_IP}:{ROBOT_PORT}")
            self.timing_logger.end_step()
            return True
            
        except Exception as e:
            self.timing_logger.add_message(f"❌ Connection failed: {str(e)}")
            self.is_connected = False
            self.timing_logger.end_step()
            return False
    
    def disconnect(self):
        """Disconnect from robot"""
        self.timing_logger.start_step("Disconnect from robot")
        
        if self.robot_conn and not self.simulation_mode:
            try:
                self.robot_conn.close()
            except:
                pass
        
        self.is_connected = False
        self.timing_logger.add_message("Disconnected from robot")
        self.timing_logger.end_step()
    
    def move_to_point(self, point_name: str, wait: bool = True) -> bool:
        """
        Move robot to a predefined point
        
        Args:
            point_name: Name of the point (e.g., "P1", "P2")
            wait: If True, wait for movement to complete
        
        Returns:
            bool: True if movement successful, False otherwise
        """
        if not self.is_connected:
            self.timing_logger.add_message(f"❌ Cannot move to {point_name}: Robot not connected")
            return False
        
        if self.is_busy:
            self.timing_logger.add_message(f"❌ Robot is busy, cannot move to {point_name}")
            return False
        
        if point_name not in self.robot_points:
            self.timing_logger.add_message(f"❌ Unknown point: {point_name}")
            return False
        
        self.timing_logger.start_step(f"Move to {point_name}")
        self.is_busy = True
        
        try:
            angles = self.robot_points[point_name]
            
            if self.simulation_mode:
                self.timing_logger.add_message(f"🎮 [SIM] Moving to {point_name}: {angles}")
                time.sleep(1.0)  # Simulate movement time
            else:
                # Convert degrees to radians
                radians = [math.radians(a) for a in angles]
                
                # Send movement command to robot
                cmd = f"movej({radians}, a=1.0, v=1.2, t=0, r=0)\n"
                self.robot_conn.send(cmd.encode())
                
                # Wait for movement
                if wait:
                    time.sleep(2.0)
                
                self.timing_logger.add_message(f"✓ Moved to {point_name}")
            
            self.timing_logger.end_step()
            return True
            
        except Exception as e:
            self.timing_logger.add_message(f"❌ Movement failed: {str(e)}")
            self.timing_logger.end_step()
            return False
        
        finally:
            self.is_busy = False
    
    def execute_sequence(self, sequence_name: str = "default") -> bool:
        """
        Execute a predefined movement sequence
        
        Args:
            sequence_name: Name of sequence ("default", "high_speed", etc.)
        
        Returns:
            bool: True if sequence completed successfully
        """
        self.timing_logger.start_operation(f"Execute {sequence_name} sequence")
        
        if not self.is_connected:
            self.timing_logger.add_message("❌ Robot not connected")
            return False
        
        try:
            if sequence_name == "default" or sequence_name == "high_speed":
                self._execute_high_speed_sequence()
            else:
                self.timing_logger.add_message(f"❌ Unknown sequence: {sequence_name}")
                return False
            
            report = self.timing_logger.end_operation(f"{sequence_name} sequence")
            self.timing_logger.add_message(f"✓ Sequence '{sequence_name}' completed successfully")
            return True
            
        except Exception as e:
            self.timing_logger.add_message(f"❌ Sequence execution failed: {str(e)}")
            return False
    
    def _execute_high_speed_sequence(self):
        """Execute the high-speed assembly sequence"""
        points = self.robot_points
        
        # Group 1: Initial positions
        self.move_to_point("P1")  # Start
        self.move_to_point("P2")
        self.move_to_point("P3")
        self.move_to_point("P4")
        self.move_to_point("P5")
        self.move_to_point("P6")
        self.move_to_point("P7")
        
        time.sleep(2)
        
        # Group 2: Middle positions
        self.move_to_point("P8")
        self.move_to_point("P9")
        self.move_to_point("P10")
        
        time.sleep(2)
        
        # Group 3: Final positions
        self.move_to_point("P11")
        time.sleep(2)
        
        self.move_to_point("P12")
        time.sleep(2)
        
        self.move_to_point("P13")
        time.sleep(2)
        
        self.move_to_point("P14")
        time.sleep(2)
        
        self.move_to_point("P15")
        
        # Return to home
        self.move_to_point("P16")
    
    def execute_custom_sequence(self, points: List[str]) -> bool:
        """
        Execute a custom sequence of points
        
        Args:
            points: List of point names to visit in order
        
        Returns:
            bool: True if sequence completed successfully
        """
        self.timing_logger.start_operation(f"Custom sequence ({len(points)} points)")
        
        if not self.is_connected:
            self.timing_logger.add_message("❌ Robot not connected")
            return False
        
        try:
            for point in points:
                if not self.move_to_point(point):
                    return False
            
            self.timing_logger.add_message("✓ Custom sequence completed")
            self.timing_logger.end_operation("Custom sequence")
            return True
            
        except Exception as e:
            self.timing_logger.add_message(f"❌ Custom sequence failed: {str(e)}")
            return False
    
    def get_status(self) -> Dict:
        """
        Get current robot status
        
        Returns:
            dict: Robot status information
        """
        return {
            'connected': self.is_connected,
            'busy': self.is_busy,
            'simulation_mode': self.simulation_mode,
            'available_points': list(self.robot_points.keys()),
            'timestamp': datetime.now().isoformat()
        }
    
    def stop_emergency(self):
        """Emergency stop (graceful shutdown)"""
        self.timing_logger.add_message("🛑 EMERGENCY STOP initiated")
        self.is_busy = False
        self.disconnect()


# ==================== UTILITY FUNCTIONS ====================
def test_connection(ip: str = ROBOT_IP, port: int = ROBOT_PORT, timeout: float = 5.0) -> bool:
    """
    Test robot connection without creating a controller
    
    Args:
        ip: Robot IP address
        port: Robot port
        timeout: Connection timeout in seconds
    
    Returns:
        bool: True if connection successful
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        sock.close()
        return True
    except:
        return False


def list_available_points(controller: CobotController) -> List[str]:
    """Get list of available robot points"""
    return list(controller.robot_points.keys())


# ==================== MAIN TEST FUNCTION ====================
def main():
    """Test the Cobot controller"""
    print("\n" + "="*70)
    print("COBOT CONTROLLER - Test Mode")
    print("="*70 + "\n")
    
    # Create controller (simulation mode for testing)
    controller = CobotController(simulation_mode=True)
    
    # Connect
    if controller.connect():
        print("✓ Robot connected\n")
        
        # Execute sequence
        if controller.execute_sequence("high_speed"):
            print("\n✓ Sequence completed successfully")
        
        # Disconnect
        controller.disconnect()
    else:
        print("✗ Failed to connect to robot")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
