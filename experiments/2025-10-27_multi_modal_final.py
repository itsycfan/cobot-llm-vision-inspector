import openai
import json
import base64
import cv2
import os
from typing import Dict, List
from datetime import datetime
import time
import openpyxl
import concurrent.futures

# ==================== 配置 ====================
# API密钥配置
API_KEY = os.getenv("OPENAI_API_KEY", "")
client = openai.OpenAI(api_key=API_KEY)
TEMPERATURE = 0.1  # 降低温度 提高一致性

# 重要路径
VIDEO_FOLDER = "VideoExample"
RESULTS_FOLDER = "PromptTestResults"
LOGS_FOLDER = "SystemLogs"
ASSEMBLY_DATA_PATH = "Data/AssemblyInstructions.xlsx"

# 性能优化配置
USE_PARALLEL_PROCESSING = True  # 是否使用并行处理
TARGET_IMAGE_WIDTH = 512  # 目标图像宽度
JPEG_QUALITY = 75  # JPEG压缩质量 (1-100)
MAX_WORKERS = 2  # 并行处理的最大线程数

# 确保文件夹存在
os.makedirs(RESULTS_FOLDER, exist_ok=True)
os.makedirs(LOGS_FOLDER, exist_ok=True)

# ==================== 装配指令数据加载 ====================
def load_assembly_instructions(filepath, row_index=2):
    """从Excel读取装配指令，默认从第2行（首个数据行）开始"""
    try:
        wb = openpyxl.load_workbook(filepath)
        ws = wb.active
        
        # 从第1行读取表头
        headers = []
        for cell in ws[1]:
            headers.append(cell.value)
        
        # 从指定行读取数据
        task_data = {}
        for idx, header in enumerate(headers, 1):
            cell_value = ws.cell(row=row_index, column=idx).value
            if header and cell_value:
                task_data[header] = cell_value
        
        wb.close()
        return task_data, row_index
    except Exception as e:
        print(f"✗ 读取装配指令失败: {str(e)}")
        return None, None

# 加载初始任务
TASK_DATA, TASK_INDEX = load_assembly_instructions(ASSEMBLY_DATA_PATH, row_index=2)

# ==================== 提示词生成函数 ====================
def generate_p1_prompt(task_data, is_multi_frame=False, frame_count=1):
    """P1: 安全风险识别 - Safety Assessment (安全专家)"""
    
    multi_frame_instruction = f"""Analyze {frame_count} frames for SAFETY HAZARDS.

Look for:
- Hitting/banging objects with force (MAJOR HAZARD)
- Uncontrolled tool use or excessive force
- Hands in dangerous positions
- Erratic movements

Score:
- SAFE (85-100): Proper safety practices observed
- CAUTION (60-84): Minor issues, awkward positioning
- DANGER (0-59): Forceful hitting, impact hazards, uncontrolled actions"""

    single_frame_instruction = """Analyze this frame for safety hazards."""
    
    return f"""You are a safety specialist. Evaluate safety hazards in assembly operations.

Task: {task_data.get('TaskName', 'Assembly Task')}

{"=" + (multi_frame_instruction if is_multi_frame else single_frame_instruction)}

{"Compare frames for: progressive unsafe actions, impact moments, force escalation" if is_multi_frame else "Check for immediate hazards."}

Respond ONLY with valid JSON:
{{
  "safety_status": "SAFE/CAUTION/DANGER",
  "risk_level": "LOW/MEDIUM/HIGH",
  "hazards_detected": ["specific hazard description"] or [],
  "safety_violations": ["specific violation"] or [],
  "immediate_concerns": ["urgent safety issue"] or [],
  "safety_score": 0-100,
  "safety_recommendations": "specific safety actions needed",
  "unsafe_behaviors": ["specific unsafe behavior observed"] or [],
  "impact_hazards": ["specific impact/hitting hazard"] or []
}}"""

def generate_p2_prompt(task_data, is_multi_frame=False):
    """P2: 基础操作正确性检查 - Basic Operation Assessment"""
    multi_frame_instruction = """Analyze operation execution quality across frames.

Quality indicators:
- Smooth completion → EXCELLENT/GOOD (95-100/85-94)
- Minor adjustments (1-3) but completed correctly → GOOD/ACCEPTABLE (85-94/75-84)
- Multiple failed attempts before success → ACCEPTABLE/POOR (60-84)
- Operation incorrect or abandoned → FAILED (0-59)"""
    
    return f"""You are a quality control specialist. Evaluate if the assembly operation was executed correctly.

Task: {task_data.get('TaskName', 'Assembly Task')}
Expected: {task_data.get('ExpectedActions', 'Standard assembly')}

{"=" + multi_frame_instruction if is_multi_frame else ""}

Key criteria:
- Was the operation completed? (COMPLETE/PARTIAL/INCOMPLETE)
- Was procedure followed correctly? (FULLY/PARTIAL/NOT)
- How smoothly was it executed? (EXCELLENT/GOOD/ACCEPTABLE/POOR/FAILED)

Score 0-100: Higher for smooth, correct completion; lower for difficulties or errors.

Respond ONLY with valid JSON:
{{
  "operation_status": "EXCELLENT/GOOD/ACCEPTABLE/POOR/FAILED",
  "completion_quality": "COMPLETE/PARTIAL/INCOMPLETE/FAILED",
  "procedure_followed": "FULLY/PARTIALLY/NOT_FOLLOWED",
  "quality_score": 0-100,
  "key_observations": ["specific observation"] or [],
  "issues_detected": ["specific issue description"] or [],
  "primary_issue": "main problem or null",
  "recommendation": "specific improvement guidance",
  "attempts_observed": "number of attempts seen in frames or 1",
  "difficulty_indicators": ["specific indicator of difficulty"] or []
}}"""

def generate_p3_prompt(task_data, is_multi_frame=False, frame_count=1):
    """P3: 空间视觉认知评估 - Spatial Visual Assessment (空间视觉专家)"""
    
    multi_frame_instruction = f"""Analyzing {frame_count} frames for SPATIAL PROCESSING DIFFICULTIES.

KEY INDICATORS of spatial deficits:
- Repeated failures at SAME angle → orientation deficit
- Multiple approach angles without success → spatial estimation problem
- Erratic positioning between frames → coordination issue
- No improvement across attempts → spatial learning difficulty

SCORING (must match observations):
- 90-100 (GOOD/EXCELLENT): First attempt mostly correct, <3 minor adjustments, smooth completion
- 83-89 (ACCEPTABLE): Some difficulty but completes successfully, minor assistance may help
- 75-82 (POOR): Multiple failed attempts, clear spatial difficulty, assistance recommended
- 0-74 (FAILED): Severe difficulty, repeated failures, immediate assistance required

CRITICAL: Score must match what you observe. If you see "multiple attempts" or "difficulty", score should be ≤79."""

    single_frame_instruction = """Analyze this single frame for spatial alignment issues."""
    
    return f"""You are a SPATIAL PROCESSING SPECIALIST. Analyze the frames for spatial alignment quality.

Task: {task_data.get('TaskName', 'Assembly Task')}

{"=" + (multi_frame_instruction if is_multi_frame else single_frame_instruction)}

DIFFERENTIATE:
✓ Normal operation: 1-2 positioning adjustments are normal and acceptable (score 85-100)
✗ Spatial difficulty: Repeated failures at same angle, no progression, erratic positioning (score ≤79)

{"Compare frames to identify: smooth completion vs repeated difficulties" if is_multi_frame else ""}

Score should reflect actual difficulty observed, not minor adjustments.

Respond ONLY with valid JSON:
{{
  "spatial_status": "EXCELLENT/GOOD/ACCEPTABLE/POOR/FAILED",
  "alignment_quality": "PERFECT/GOOD/ACCEPTABLE/POOR/FAILED",
  "spatial_coordination": "SMOOTH/ADEQUATE/DIFFICULT/POOR/FAILED",
  "positioning_accuracy": "PRECISE/GOOD/ACCEPTABLE/INACCURATE/FAILED",
  "spatial_score": 0-100,
  "spatial_issues": ["specific misalignment issue"] or [],
  "spatial_difficulty_level": "NONE/MILD/MODERATE/SEVERE",
  "spatial_assessment": "detailed assessment focusing on alignment and positioning accuracy",
  "temporal_patterns": ["patterns observed across frames (if multi-frame)"] or [],
  "repetitive_errors": "describe if same errors repeated across frames" or null,
  "score_justification": "brief explanation of why this score was assigned given the observed difficulties"
}}"""

def generate_p4_prompt(task_data, results, is_multi_frame=False, frame_count=1):
    """P4: 综合评估 - Comprehensive Assessment (综合专家，基于视频分析和专家意见)"""
    
    safety_status = results.get('p1', {}).get('safety_status', 'UNKNOWN')
    safety_score = results.get('p1', {}).get('safety_score', 100)
    safety_level = "HIGH RISK" if safety_score < 60 else "MODERATE RISK" if safety_score < 80 else "LOW RISK"
    
    spatial_status = results.get('p3', {}).get('spatial_status', 'UNKNOWN')
    spatial_score = results.get('p3', {}).get('spatial_score', 100)
    spatial_level = "SEVERE DEFICIT" if spatial_score < 65 else "SIGNIFICANT DEFICIT" if spatial_score < 80 else "MILD DEFICIT" if spatial_score < 85 else "MINIMAL ISSUES"
    
    video_analysis_instruction = f"""Comprehensive assessment with priority hierarchy.

PRIORITY 1 - SAFETY (score {safety_score}/100):
- < 60: DANGER → Overall FAILED/POOR, CRITICAL priority, YES assistance
- 60-79: CAUTION → Max ACCEPTABLE, HIGH priority, YES assistance
- ≥ 80: Safe → Continue to Priority 2

PRIORITY 2 - SPATIAL VISUAL (score {spatial_score}/100):
- < 65: Severe deficit → HIGH priority, assistance REQUIRED
- 65-79: Moderate deficit → HIGH/MEDIUM priority, strongly recommend assistance
- 80-84: Mild deficit → MEDIUM priority, recommend assistance
- ≥ 85: Minimal issues → NO assistance needed

PRIORITY 3 - OPERATION QUALITY:
- Consider only if safety and spatial are minimal

Expert findings:
- Safety: {results.get('p1', {}).get('hazards_detected', [])}
- Spatial: {results.get('p3', {}).get('spatial_issues', [])}
- Operation: {results.get('p2', {}).get('issues_detected', [])}

{"Verify findings against the " + str(frame_count) + " video frames." if is_multi_frame else "Verify against video."}"""
    
    single_frame_instruction = f"""You have expert assessments and one video frame for verification."""
    
    return f"""You are a comprehensive assessment specialist. Provide final evaluation following the priority hierarchy.

Task: {task_data.get('TaskName', 'Assembly Task')}

{"=" + (video_analysis_instruction if is_multi_frame else single_frame_instruction)}

Apply the priority hierarchy above to determine:
- Overall performance (EXCELLENT/GOOD/ACCEPTABLE/POOR/FAILED)
- Overall score (0-100)
- Assistance needed (YES/NO)
- Priority level (CRITICAL/HIGH/MEDIUM/LOW/NONE)

Respond ONLY with valid JSON:
{{
  "overall_performance": "EXCELLENT/GOOD/ACCEPTABLE/POOR/FAILED",
  "safety_status": "SAFE/CAUTION/DANGER",
  "operation_quality": "EXCELLENT/GOOD/ACCEPTABLE/POOR/FAILED",
  "spatial_processing": "EXCELLENT/GOOD/ACCEPTABLE/POOR/FAILED",
  "assistance_needed": "YES/NO",
  "priority_level": "CRITICAL/HIGH/MEDIUM/LOW/NONE",
  "overall_score": 0-100,
  "recommended_interventions": ["specific intervention"] or [],
  "final_assessment": "comprehensive summary following priority hierarchy (safety > spatial > operation)",
  "confidence_level": "HIGH/MEDIUM/LOW",
  "expert_consensus": "describe agreement/disagreement among experts",
  "video_verification": "what video frames confirm or refute",
  "spatial_assistance_warranted": "YES/NO - whether spatial processing difficulties justify robotic assistance (research focus)",
  "primary_concern": "SAFETY/SPATIAL_DEFICIT/OPERATION_QUALITY - which issue is driving the assessment"
}}"""

PROMPT_GENERATORS = {
    "p1": generate_p1_prompt,
    "p2": generate_p2_prompt,
    "p3": generate_p3_prompt,
    "p4": generate_p4_prompt,
}

# ==================== 工具函数 ====================

class SimpleTimeLogger:
    """Simple time logging for key milestones"""
    
    def __init__(self):
        self.start_time = time.time()
        self.timestamps = []
        
    def log(self, event_name, additional_info=""):
        """Log a timestamp for an event"""
        elapsed = time.time() - self.start_time
        info_str = f" | {additional_info}" if additional_info else ""
        self.timestamps.append(f"[{elapsed:8.3f}s] {event_name}{info_str}")
        
    def get_report(self):
        """Get formatted report"""
        total_time = time.time() - self.start_time
        lines = ["\n" + "="*80, "SYSTEM TIMING LOG", "="*80]
        lines.extend(self.timestamps)
        lines.extend(["="*80, f"TOTAL RUNTIME: {total_time:8.3f}s", "="*80])
        return "\n".join(lines)

def get_latest_video():
    """获取文件夹中的视频"""
    try:
        files = os.listdir(VIDEO_FOLDER)
        video_files = [f for f in files if 'bad1' in f and f.endswith(('.mp4', '.avi', '.mov'))]
        if not video_files:
            return None
        
        latest = max(video_files, key=lambda f: os.path.getctime(os.path.join(VIDEO_FOLDER, f)))
        return os.path.join(VIDEO_FOLDER, latest)
    except:
        return None

def extract_frames(video_path, sample_rate=2, target_width=512, jpeg_quality=75):
    """提取视频帧 - 降低采样率以获取更多帧"""
    start = time.time()
    cap = cv2.VideoCapture(video_path)
    frames = []
    count = 0
    
    # 获取原始视频尺寸
    original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # 计算目标高度，保持宽高比
    target_height = int(target_width * original_height / original_width)
    
    # 设置JPEG编码参数
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if count % sample_rate == 0:
            # 调整图像大小
            if original_width > target_width:
                frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
            
            # 使用优化的编码参数
            _, buffer = cv2.imencode('.jpg', frame, encode_params)
            frame_b64 = base64.b64encode(buffer).decode()
            frames.append(frame_b64)

        count += 1

    cap.release()
    elapsed = time.time() - start
    return frames, elapsed

def execute_single_prompt(prompt_name, frames_input, context_results=None, max_retries=2, is_multi_frame=False):
    """统一的提示词执行函数，支持单帧或多帧输入
    
    Args:
        prompt_name: 提示词名称
        frames_input: 单个frame_b64字符串或frame_b64列表
        context_results: 上下文结果（用于p4）
        max_retries: 最大重试次数
        is_multi_frame: 是否使用多帧分析
    """
    # 确保frames_input是列表格式
    if isinstance(frames_input, str):
        frames_list = [frames_input]
    else:
        frames_list = frames_input
    
    for attempt in range(max_retries):
        start = time.time()
        response_text = None
        
        try:
            # 生成提示词文本（传入多帧信息）
            if prompt_name == "p4":
                full_prompt = PROMPT_GENERATORS[prompt_name](TASK_DATA, context_results or {}, is_multi_frame=is_multi_frame, frame_count=len(frames_list))
            elif prompt_name == "p3":
                full_prompt = PROMPT_GENERATORS[prompt_name](TASK_DATA, is_multi_frame=is_multi_frame, frame_count=len(frames_list))
            elif prompt_name == "p2":
                full_prompt = PROMPT_GENERATORS[prompt_name](TASK_DATA, is_multi_frame=is_multi_frame)
            elif prompt_name == "p1":
                full_prompt = PROMPT_GENERATORS[prompt_name](TASK_DATA, is_multi_frame=is_multi_frame, frame_count=len(frames_list))
            else:
                full_prompt = PROMPT_GENERATORS[prompt_name](TASK_DATA)
            
            # 构建内容数组（可以包含多张图像）
            content_items = []
            for frame_b64 in frames_list:
                content_items.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"}})
            content_items.append({"type": "text", "text": full_prompt})
            
            # 执行API调用
            msg = client.chat.completions.create(
                model="gpt-4o",
                max_tokens=1500,
                temperature=TEMPERATURE,
                messages=[{
                    "role": "user",
                    "content": content_items
                }]
            )

            response_text = msg.choices[0].message.content
            
            # 记录调试信息
            _log_debug_info(prompt_name, attempt, max_retries, full_prompt, response_text)
            
            if not response_text or response_text.strip() == "":
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    return {"error": "Empty response"}, time.time() - start, "Empty response"

            # 处理响应并解析JSON
            result = _parse_response(response_text, prompt_name, attempt, max_retries)
            if result is None:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    return {"error": "Failed to parse response"}, time.time() - start, "Parse failed"
            
            elapsed = time.time() - start
            _log_success(prompt_name, attempt)
            return result, elapsed, None
            
        except Exception as e:
            error_msg = f"API error: {str(e)}"
            _log_error(prompt_name, attempt, error_msg, response_text)
            
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                return {"error": f"API Error: {error_msg[:100]}"}, time.time() - start, str(e)
    
    return {"error": "Max retries exceeded"}, time.time() - start, "Max retries exceeded"

def _log_debug_info(prompt_name, attempt, max_retries, full_prompt, response_text):
    """记录调试信息"""
    os.makedirs(LOGS_FOLDER, exist_ok=True)
    with open(os.path.join(LOGS_FOLDER, f"debug_{prompt_name}.log"), "w", encoding='utf-8') as f:
        f.write(f"[{prompt_name}] Attempt {attempt+1}/{max_retries}\n")
        f.write(f"Prompt length: {len(full_prompt)}\n")
        f.write(f"Response length: {len(response_text)}\n")
        f.write(f"Response (first 300 chars):\n{response_text[:300]}\n")
        f.write(f"\nResponse (last 300 chars):\n{response_text[-300:]}\n")

def _parse_response(response_text, prompt_name, attempt, max_retries):
    """解析API响应"""
    try:
        # 处理markdown代码块
        processed_text = response_text
        if processed_text.startswith("```"):
            processed_text = processed_text.split("```")[1]
            if processed_text.startswith("json"):
                processed_text = processed_text[4:]

        processed_text = processed_text.strip()
        
        if not processed_text:
            return None
        
        # 解析JSON
        return json.loads(processed_text)
        
    except json.JSONDecodeError as e:
        error_msg = f"JSON decode error: {str(e)}"
        with open(os.path.join(LOGS_FOLDER, f"debug_{prompt_name}.log"), "a", encoding='utf-8') as f:
            f.write(f"\n✗ JSON parsing failed: {error_msg}\n")
            f.write(f"Full response text:\n{response_text}\n")
        return None

def _log_success(prompt_name, attempt):
    """记录成功日志"""
    with open(os.path.join(LOGS_FOLDER, f"debug_{prompt_name}.log"), "a", encoding='utf-8') as f:
        f.write(f"\n✓ JSON parsing successful at attempt {attempt+1}\n")

def _log_error(prompt_name, attempt, error_msg, response_text):
    """记录错误日志"""
    with open(os.path.join(LOGS_FOLDER, f"debug_{prompt_name}.log"), "a", encoding='utf-8') as f:
        f.write(f"\n✗ Exception: {error_msg}\n")
        if response_text:
            f.write(f"Response preview: {response_text[:200]}\n")

def run_prompts_parallel(frames, prompts_order, frame_strategy, max_workers=2):
    """并行运行多个prompt"""
    results = {}
    prompt_times = {}
    prompt_errors = {}
    
    def run_single_prompt(prompt_name, context_results=None):
        """运行单个prompt的包装函数"""
        frames_to_use = frame_strategy[prompt_name]
        
        # 判断是否使用多帧（P1, P2, P3, P4都支持多帧）
        is_multi_frame = (len(frames_to_use) > 1 and prompt_name in ["p1", "p2", "p3", "p4"])
        
        # 传递给API的图像（单帧或多帧）
        if is_multi_frame:
            frames_input = frames_to_use  # 传递整个列表
        else:
            frames_input = frames_to_use[0]  # 只传递第一帧
        
        result, p_time, error = execute_single_prompt(prompt_name, frames_input, context_results, is_multi_frame=is_multi_frame)
        return prompt_name, result, p_time, error
    
    # 分离p4和其他prompts（p4需要等待前三个结果）
    independent_prompts = [p for p in prompts_order if p != "p4"]
    p4_prompt = "p4" if "p4" in prompts_order else None
    
    # 先并行运行独立的prompts
    if independent_prompts:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_prompt = {executor.submit(run_single_prompt, prompt_name): prompt_name 
                               for prompt_name in independent_prompts}
            
            for future in concurrent.futures.as_completed(future_to_prompt):
                prompt_name, result, p_time, error = future.result()
                results[prompt_name] = result
                prompt_times[prompt_name] = p_time
                if error:
                    prompt_errors[prompt_name] = error
    
    # 然后运行p4（如果需要）
    if p4_prompt:
        prompt_name, result, p_time, error = run_single_prompt(p4_prompt, results)
        results[prompt_name] = result
        prompt_times[prompt_name] = p_time
        if error:
            prompt_errors[prompt_name] = error
    
    return results, prompt_times, prompt_errors

def save_file(content, filename, folder):
    """通用文件保存函数"""
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return filepath

def save_results(results, filename):
    """保存结果到txt文件"""
    # 统计信息
    total_prompts = len(results)
    successful = sum(1 for r in results.values() if "error" not in r or not r.get("error"))
    failed = total_prompts - successful
    
    # 构建内容
    content = f"""{"="*60}
ASSEMBLY EVALUATION RESULTS
{"="*60}

Summary:
  Total Prompts: {total_prompts}
  Successful: {successful}
  Failed: {failed}

"""
    
    # 详细结果
    for prompt_name, result in results.items():
        content += f"""
{'-'*60}
PROMPT: {prompt_name.upper()}
{'-'*60}
"""
        if "error" in result and result["error"]:
            content += f"❌ ERROR: {result['error']}\n"
            if "response_preview" in result:
                content += f"Response preview: {result['response_preview']}\n"
        else:
            content += "✓ SUCCESS\n"
            content += json.dumps(result, indent=2, ensure_ascii=False)
        content += "\n"
    
    content += f"""
{'='*60}
RAW JSON
{'='*60}
{json.dumps(results, indent=2, ensure_ascii=False)}"""
    
    return save_file(content, filename, RESULTS_FOLDER)

def save_log(log_text, filename):
    """保存日志到txt文件"""
    return save_file(log_text, filename, LOGS_FOLDER)

class AssemblyEvaluator:
    """装配评估系统主类"""
    
    def __init__(self):
        self.task_data = TASK_DATA
        self.task_index = TASK_INDEX
        self.total_start = None
        self.log_lines = []
        self.time_logger = SimpleTimeLogger()
        self.silent_mode = False  # 静默模式，用于批量测试
        
    def initialize_log(self, video_path):
        """初始化日志"""
        self.log_lines = [
            f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Temperature: {TEMPERATURE}",
            f"Task Index: {self.task_index}",
            f"Task: {self.task_data.get('TaskName', 'N/A')}",
            f"Video: {os.path.basename(video_path) if video_path else 'None'}",
        ]
        self.time_logger.log("System Initialized")
    
    def run_evaluation(self, video_path):
        """运行完整评估流程"""
        # 提取视频帧
        print("\n[2] 提取视频帧...")
        self.total_start = time.time()
        self.time_logger.log("Frame Extraction Started")
        
        frames, frame_time = extract_frames(video_path, sample_rate=3, 
                                           target_width=TARGET_IMAGE_WIDTH, 
                                           jpeg_quality=JPEG_QUALITY)
        print(f"✓ 提取 {len(frames)} 帧 ({frame_time:.2f}s)")
        self.time_logger.log(f"Frame Extraction Completed", f"{len(frames)} frames")
        
        if not frames:
            return None
            
        # 执行提示词评估
        results, prompt_times, prompt_errors = self._execute_prompts(frames)
        
        # 生成报告
        self._generate_reports(results, prompt_times, prompt_errors)
        
        return results
    
    def _execute_prompts(self, frames):
        """执行提示词评估"""
        # 智能帧选择策略 - 增加帧数以提高准确性
        num_frames = len(frames)
        
        # P1（安全专家）：使用更多帧检测时序安全风险（击打、暴力动作等）
        p1_frames = []
        if num_frames <= 8:
            p1_frames = frames
        else:
            # 选择8个均匀分布的帧检测不安全行为
            step = max(1, num_frames // 8)
            p1_frames = [frames[i] for i in range(0, num_frames, step)][:8]
        
        # P2（操作专家）：使用更多帧分析操作过程
        p2_frames = []
        if num_frames <= 5:
            p2_frames = frames
        else:
            # 选择5个关键帧：开头、1/4、中间、3/4、结尾
            indices = [0, num_frames // 4, num_frames // 2, 3 * num_frames // 4, num_frames - 1]
            p2_frames = [frames[i] for i in indices]
        
        # P3（空间视觉专家）：使用最多帧识别空间障碍
        p3_frames = []
        if num_frames <= 10:
            p3_frames = frames
        else:
            # 选择10个均匀分布的帧
            step = max(1, num_frames // 10)
            p3_frames = [frames[i] for i in range(0, num_frames, step)][:10]
        
        # P4（综合专家）：使用适中帧数进行独立复核
        p4_frames = []
        if num_frames <= 6:
            p4_frames = frames
        else:
            # 选择6个关键帧进行综合评估
            step = max(1, num_frames // 6)
            p4_frames = [frames[i] for i in range(0, num_frames, step)][:6]
        
        frame_strategy = {
            "p1": p1_frames,
            "p2": p2_frames,
            "p3": p3_frames,
            "p4": p4_frames,
        }
        
        # 打印使用的帧数
        print(f"  帧使用策略:")
        print(f"    P1 (安全专家): {len(p1_frames)} 帧")
        print(f"    P2 (操作专家): {len(p2_frames)} 帧")
        print(f"    P3 (空间专家): {len(p3_frames)} 帧")
        print(f"    P4 (综合专家): {len(p4_frames)} 帧")
        
        prompts_order = ["p1", "p2", "p3", "p4"]
        mode = "并行模式" if USE_PARALLEL_PROCESSING else "顺序模式"
        print(f"\n[3] 运行评估提示词（{mode}）...")
        self.time_logger.log("Prompt Execution Started", mode)
        
        if USE_PARALLEL_PROCESSING:
            results, prompt_times, prompt_errors = run_prompts_parallel(frames, prompts_order, frame_strategy, MAX_WORKERS)
        else:
            results, prompt_times, prompt_errors = self._execute_sequential(prompts_order, frame_strategy)
        
        # Log individual prompt completion
        for prompt_name in prompts_order:
            if prompt_name in prompt_times:
                status = "SUCCESS" if prompt_name not in prompt_errors else "FAILED"
                self.time_logger.log(f"{prompt_name.upper()} Completed", f"{status} ({prompt_times[prompt_name]:.2f}s)")
        
        return results, prompt_times, prompt_errors
    
    def _execute_sequential(self, prompts_order, frame_strategy):
        """顺序执行提示词"""
        results = {}
        prompt_times = {}
        prompt_errors = {}
        
        for i, prompt_name in enumerate(prompts_order, 1):
            print(f"  {i}/4 运行 {prompt_name}...", end=" ")
            
            frames_to_use = frame_strategy[prompt_name]
            
            # 判断是否使用多帧（P1, P2, P3, P4都支持多帧）
            is_multi_frame = (len(frames_to_use) > 1 and prompt_name in ["p1", "p2", "p3", "p4"])
            
            # 传递给API的图像（单帧或多帧）
            if is_multi_frame:
                frames_input = frames_to_use  # 传递整个列表
            else:
                frames_input = frames_to_use[0]  # 只传递第一帧
            
            result, p_time, error = execute_single_prompt(prompt_name, frames_input, results, is_multi_frame=is_multi_frame)
            
            results[prompt_name] = result
            prompt_times[prompt_name] = p_time
            
            if error:
                print(f"✗ ({p_time:.2f}s)")
                prompt_errors[prompt_name] = error
            else:
                print(f"✓ ({p_time:.2f}s)")
        
        return results, prompt_times, prompt_errors
    
    def _generate_reports(self, results, prompt_times, prompt_errors):
        """生成报告和日志"""
        if not self.silent_mode:
            print("\n[4] 生成报告...")
        self.time_logger.log("Report Generation Started")
        
        # 保存结果（仅在非静默模式保存）
        if not self.silent_mode:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_filename = f"{timestamp}_PromptResults.txt"
            save_results(results, result_filename)
            print(f"✓ 结果已保存: {result_filename}")
            self.time_logger.log("Results Saved", result_filename)
        
        # 生成日志（仅在非静默模式）
        if not self.silent_mode:
            self._build_log_content(results, prompt_times, prompt_errors)
            
            # Add timing report to log
            timing_report = self.time_logger.get_report()
            self.log_lines.append(timing_report)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"{timestamp}_SystemLog.txt"
            save_log("\n".join(self.log_lines), log_filename)
            print(f"✓ 日志已保存: {log_filename}")
            self.time_logger.log("Log Saved", log_filename)
            
            # 显示结果
            self._display_results(results, prompt_times, prompt_errors)
    
    def _build_log_content(self, results, prompt_times, prompt_errors):
        """构建日志内容"""
        total_time = time.time() - self.total_start
        prompts_order = ["p1", "p2", "p3", "p4"]
        
        self.log_lines.extend([
            "\n--- Execution Summary ---",
            f"Total API Time: {sum(prompt_times.values()):.2f}s",
            f"Total Program Time: {total_time:.2f}s"
        ])
        
        if prompt_errors:
            self.log_lines.extend([
                "\n--- Error Information ---",
                *[f"\n{p}:\n  Error: {error}" for p, error in prompt_errors.items()]
            ])
        
        self.log_lines.extend([
            "\n--- Results Summary ---",
            f"Total Prompts: 4",
            f"Successful: {len([p for p in prompts_order if 'error' not in results[p] or not results[p].get('error')])}",
            f"Failed: {len([p for p in prompts_order if 'error' in results[p] and results[p].get('error')])}",
            "\n--- Key Assessment Findings ---"
        ])
        
        # 关键评估结果
        if "p1" in results and "error" not in results["p1"]:
            self.log_lines.append(f"Safety Status: {results['p1'].get('safety_status', 'N/A')} (Score: {results['p1'].get('safety_score', 'N/A')})")
        if "p2" in results and "error" not in results["p2"]:
            self.log_lines.append(f"Operation Quality: {results['p2'].get('operation_status', 'N/A')} (Score: {results['p2'].get('quality_score', 'N/A')})")
        if "p3" in results and "error" not in results["p3"]:
            self.log_lines.append(f"Spatial Processing: {results['p3'].get('spatial_status', 'N/A')} (Score: {results['p3'].get('spatial_score', 'N/A')})")
        if "p4" in results and "error" not in results["p4"]:
            self.log_lines.extend([
                f"Overall Performance: {results['p4'].get('overall_performance', 'N/A')} (Score: {results['p4'].get('overall_score', 'N/A')})",
                f"Assistance Needed: {results['p4'].get('assistance_needed', 'N/A')}",
                f"Priority Level: {results['p4'].get('priority_level', 'N/A')}"
            ])
    
    def _display_results(self, results, prompt_times, prompt_errors):
        """显示结果"""
        prompt_names = {
            "p1": "P1-安全", "p2": "P2-基础操作", 
            "p3": "P3-空间视觉", "p4": "P4-综合"
        }
        
        prompts_order = ["p1", "p2", "p3", "p4"]
        for i, prompt_name in enumerate(prompts_order, 1):
            p_time = prompt_times[prompt_name]
            display_name = prompt_names.get(prompt_name, prompt_name)
            if prompt_name in prompt_errors:
                print(f"  {i}/4 {display_name}: ✗ ({p_time:.2f}s)")
            else:
                print(f"  {i}/4 {display_name}: ✓ ({p_time:.2f}s)")
        
        # 打印最终摘要
        print("\n" + "="*60)
        print("完整结果:")
        print("="*60)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        
        print("\n" + "="*60)
        print("系统日志:")
        print("="*60)
        print("\n".join(self.log_lines))

# ==================== 批量测试功能 ====================

def analyze_test_results(test_results_list):
    """分析多次测试结果的一致性和准确性"""
    if not test_results_list:
        return
    
    print("\n" + "="*80)
    print("批量测试结果分析")
    print("="*80)
    
    # 提取关键指标
    safety_scores = []
    operation_scores = []
    spatial_scores = []
    overall_scores = []
    overall_performances = []
    assistance_needed_list = []
    priority_levels = []
    
    for result in test_results_list:
        p1 = result.get('p1', {})
        p2 = result.get('p2', {})
        p3 = result.get('p3', {})
        p4 = result.get('p4', {})
        
        if 'error' not in p1:
            safety_scores.append(p1.get('safety_score', 0))
        if 'error' not in p2:
            operation_scores.append(p2.get('quality_score', 0))
        if 'error' not in p3:
            spatial_scores.append(p3.get('spatial_score', 0))
        if 'error' not in p4:
            overall_scores.append(p4.get('overall_score', 0))
            overall_performances.append(p4.get('overall_performance', 'UNKNOWN'))
            assistance_needed_list.append(p4.get('assistance_needed', 'UNKNOWN'))
            priority_levels.append(p4.get('priority_level', 'UNKNOWN'))
    
    # 计算统计信息
    if safety_scores:
        print(f"\n【安全分数】 ({len(safety_scores)}次测试)")
        print(f"  平均值: {sum(safety_scores)/len(safety_scores):.2f}")
        print(f"  范围: {min(safety_scores)} - {max(safety_scores)}")
        print(f"  标准差: {(sum((x - sum(safety_scores)/len(safety_scores))**2 for x in safety_scores)/len(safety_scores))**0.5:.2f}")
    
    if operation_scores:
        print(f"\n【操作质量分数】 ({len(operation_scores)}次测试)")
        print(f"  平均值: {sum(operation_scores)/len(operation_scores):.2f}")
        print(f"  范围: {min(operation_scores)} - {max(operation_scores)}")
        print(f"  标准差: {(sum((x - sum(operation_scores)/len(operation_scores))**2 for x in operation_scores)/len(operation_scores))**0.5:.2f}")
    
    if spatial_scores:
        print(f"\n【空间视觉分数】 ({len(spatial_scores)}次测试)")
        print(f"  平均值: {sum(spatial_scores)/len(spatial_scores):.2f}")
        print(f"  范围: {min(spatial_scores)} - {max(spatial_scores)}")
        print(f"  标准差: {(sum((x - sum(spatial_scores)/len(spatial_scores))**2 for x in spatial_scores)/len(spatial_scores))**0.5:.2f}")
    
    if overall_scores:
        print(f"\n【综合分数】 ({len(overall_scores)}次测试)")
        print(f"  平均值: {sum(overall_scores)/len(overall_scores):.2f}")
        print(f"  范围: {min(overall_scores)} - {max(overall_scores)}")
        print(f"  标准差: {(sum((x - sum(overall_scores)/len(overall_scores))**2 for x in overall_scores)/len(overall_scores))**0.5:.2f}")
    
    # 一致性分析
    if overall_performances:
        from collections import Counter
        perf_counter = Counter(overall_performances)
        assistance_counter = Counter(assistance_needed_list)
        priority_counter = Counter(priority_levels)
        
        print(f"\n【整体表现一致性】")
        for perf, count in perf_counter.items():
            print(f"  {perf}: {count}次 ({count/len(overall_performances)*100:.1f}%)")
        
        print(f"\n【需要辅助一致性】")
        for ass, count in assistance_counter.items():
            print(f"  {ass}: {count}次 ({count/len(assistance_needed_list)*100:.1f}%)")
        
        print(f"\n【优先级一致性】")
        for priority, count in priority_counter.items():
            print(f"  {priority}: {count}次 ({count/len(priority_levels)*100:.1f}%)")

def run_batch_tests(num_tests, video_path):
    """运行批量测试"""
    print("\n" + "="*80)
    print(f"开始批量测试: {num_tests}次")
    print("="*80)
    
    test_results = []
    
    for i in range(num_tests):
        print(f"\n--- 测试 {i+1}/{num_tests} ---")
        
        evaluator = AssemblyEvaluator()
        evaluator.initialize_log(video_path)
        evaluator.silent_mode = True  # 静默模式
        
        results = evaluator.run_evaluation(video_path)
        
        if results:
            test_results.append(results)
            # 提取关键信息
            p1 = results.get('p1', {})
            p4 = results.get('p4', {})
            if 'error' not in p1 and 'error' not in p4:
                print(f"  安全: {p1.get('safety_status', 'N/A')} ({p1.get('safety_score', 0)})")
                print(f"  综合: {p4.get('overall_performance', 'N/A')} ({p4.get('overall_score', 0)})")
                print(f"  需要辅助: {p4.get('assistance_needed', 'N/A')}")
        else:
            print(f"  测试 {i+1} 失败")
    
    return test_results

# ==================== 主程序 ====================

def main():
    """主程序入口"""
    print("="*60)
    print("Assembly Evaluation System - Enhanced Version")
    print("="*60)
    
    # 检查任务数据
    print("\n[0] 加载装配指令...")
    if not TASK_DATA:
        print("✗ 装配指令加载失败")
        return
    else:
        print(f"✓ 任务索引: {TASK_INDEX}")
        print(f"✓ 任务名称: {TASK_DATA.get('TaskName', 'N/A')}")
        print(f"✓ 位置: {TASK_DATA.get('Position', 'N/A')}")
    
    # 获取最新视频
    print("\n[1] 查找最新视频...")
    video_path = get_latest_video()
    
    if not video_path:
        print("✗ 未找到视频文件")
        return
    else:
        print(f"✓ 找到视频: {os.path.basename(video_path)}")
    
    # 询问运行模式
    print("\n选择运行模式:")
    print("  1 - 单次测试")
    print("  2 - 批量测试")
    
    try:
        choice = input("\n请输入选项 (1 或 2): ").strip()
        
        if choice == '2':
            num_tests = input("请输入测试次数 (建议3-10次): ").strip()
            try:
                num_tests = int(num_tests)
                if num_tests < 1 or num_tests > 20:
                    print("测试次数应在1-20之间，使用默认值5")
                    num_tests = 5
            except:
                print("无效输入，使用默认值5")
                num_tests = 5
            
            # 运行批量测试
            test_results = run_batch_tests(num_tests, video_path)
            
            # 分析结果
            analyze_test_results(test_results)
            
            # 保存批量测试结果
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_filename = f"{timestamp}_BatchTest_{num_tests}rounds.json"
            batch_filepath = os.path.join(RESULTS_FOLDER, batch_filename)
            with open(batch_filepath, 'w', encoding='utf-8') as f:
                json.dump(test_results, f, indent=2, ensure_ascii=False)
            print(f"\n✓ 批量测试结果已保存: {batch_filename}")
        else:
            # 单次测试
            program_logger = SimpleTimeLogger()
            program_logger.log("Program Started")
            program_logger.log("Task Data Loaded")
            program_logger.log("Video Search Started")
            program_logger.log("Video Found", os.path.basename(video_path))
            
            evaluator = AssemblyEvaluator()
            evaluator.initialize_log(video_path)
            evaluator.time_logger = program_logger
            
            results = evaluator.run_evaluation(video_path)
            
            if results:
                program_logger.log("Evaluation Completed")
                print("\n✓ 评估完成！")
    
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n发生错误: {str(e)}")

if __name__ == "__main__":
    main()