from flask import Flask, request, jsonify, send_file
import os
import uuid
import subprocess
from werkzeug.utils import secure_filename
import logging
import shutil
from PIL import Image
import tempfile

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/waifu2x_uploads'
app.config['OUTPUT_FOLDER'] = '/tmp/waifu2x_results'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'bmp', 'tif', 'tiff', 'tga', 'gif', 'webp'}

# 필요한 디렉토리 생성
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def process_image(input_path, output_path, params):
    """이미지를 처리하는 함수"""
    try:
        # 기본 명령 구성
        cmd = [
            'waifu2x-caffe',
            '-i', input_path,
            '-o', output_path
        ]
        
        # 모드 설정 (noise, scale, noise_scale, auto_scale)
        if 'mode' in params:
            cmd.extend(['-m', params['mode']])
        
        # 노이즈 감소 레벨
        if 'noise_level' in params:
            cmd.extend(['-n', str(params['noise_level'])])
        
        # 스케일링 옵션 처리
        # 세 가지 스케일링 옵션 중 하나만 사용해야 함
        if 'scale_mode' in params:
            if params['scale_mode'] == 'ratio' and 'scale_ratio' in params:
                cmd.extend(['-s', str(params['scale_ratio'])])
            elif params['scale_mode'] == 'width' and 'scale_width' in params and params['scale_width']:
                cmd.extend(['-w', str(params['scale_width'])])
            elif params['scale_mode'] == 'height' and 'scale_height' in params and params['scale_height']:
                cmd.extend(['-h', str(params['scale_height'])])
        elif 'scale_ratio' in params:  # 이전 버전과의 호환성 유지
            cmd.extend(['-s', str(params['scale_ratio'])])
        
        # 처리 방식 (cpu, gpu, cudnn)
        if 'process' in params:
            cmd.extend(['-p', params['process']])
        
        # 기타 옵션들
        if 'tta' in params and params['tta']:
            cmd.extend(['-t', '1'])
            
        if 'output_format' in params:
            cmd.extend(['-e', params['output_format']])
        
        # 명령 실행
        app.logger.info(f"Executing command: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            app.logger.info(f"Image processing completed successfully")
            return True, output_path
        else:
            error_msg = stderr.decode('shift_jis') + stdout.decode('shift_jis')
            app.logger.error(f"Image processing failed: {error_msg}")
            return False, error_msg
            
    except Exception as e:
        app.logger.error(f"Exception during image processing: {str(e)}")
        return False, str(e)

def split_gif_frames(gif_path, output_dir):
    """GIF 파일을 개별 프레임으로 분리"""
    try:
        app.logger.info(f"Splitting GIF frames from {gif_path} to {output_dir}")
        
        # 디렉토리가 존재하지 않으면 생성
        os.makedirs(output_dir, exist_ok=True)
        
        # ImageMagick 명령어로 GIF 프레임 분리
        cmd = ['convert', gif_path, '-coalesce', f'{output_dir}/frame%03d.png']
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            app.logger.error(f"GIF 분리 실패: {stderr.decode()}")
            return False, stderr.decode()
        
        # 지연 시간 추출
        img = Image.open(gif_path)
        frame_delays = []
        try:
            while True:
                # 각 프레임의 지연 시간을 밀리초 단위로 저장 (기본값 100ms)
                delay = img.info.get('duration', 100)
                frame_delays.append(delay / 10)  # ImageMagick은 1/100초 단위 사용
                img.seek(img.tell() + 1)
        except EOFError:
            pass  # 모든 프레임 처리 완료
        
        app.logger.info(f"GIF frames split successfully")
        return True, frame_delays
    except Exception as e:
        app.logger.error(f"GIF 프레임 분리 중 예외 발생: {str(e)}")
        return False, str(e)

def process_gif(input_path, output_path, params):
    """GIF 이미지 처리"""
    try:
        app.logger.info(f"Processing GIF: {input_path}")
        
        # 임시 디렉토리 생성
        frames_dir = tempfile.mkdtemp(prefix='waifu2x_gif_')
        processed_dir = tempfile.mkdtemp(prefix='waifu2x_processed_')
        
        # GIF 파일을 프레임으로 분리
        success, frame_delays = split_gif_frames(input_path, frames_dir)
        if not success:
            return False, frame_delays  # 에러 메시지 반환
        
        # waifu2x로 모든 프레임 처리 (디렉토리 모드)
        cmd = [
            'waifu2x-caffe',
            '-i', frames_dir,
            '-o', processed_dir
        ]
        
        # 파라미터 추가
        if 'mode' in params:
            cmd.extend(['-m', params['mode']])
        if 'noise_level' in params:
            cmd.extend(['-n', str(params['noise_level'])])
        
        # 스케일링 옵션 처리
        if 'scale_mode' in params:
            if params['scale_mode'] == 'ratio' and 'scale_ratio' in params:
                cmd.extend(['-s', str(params['scale_ratio'])])
            elif params['scale_mode'] == 'width' and 'scale_width' in params and params['scale_width']:
                cmd.extend(['-w', str(params['scale_width'])])
            elif params['scale_mode'] == 'height' and 'scale_height' in params and params['scale_height']:
                cmd.extend(['-h', str(params['scale_height'])])
        elif 'scale_ratio' in params:  # 이전 버전과의 호환성 유지
            cmd.extend(['-s', str(params['scale_ratio'])])
            
        if 'process' in params:
            cmd.extend(['-p', params['process']])
        if 'tta' in params and params['tta']:
            cmd.extend(['-t', '1'])
        
        # 출력 포맷은 PNG로 고정 (나중에 GIF로 변환)
        cmd.extend(['-e', 'png'])
        
        app.logger.info(f"프레임 처리 명령 실행: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode('shift_jis') + stdout.decode('shift_jis')
            app.logger.error(f"프레임 처리 실패: {error_msg}")
            return False, error_msg
        
        app.logger.info(f"GIF frames processed successfully")
        
        # 처리된 프레임을 GIF로 결합
        app.logger.info(f"Combining processed frames into GIF: {output_path}")
        cmd = ['convert', '-dispose', 'background', '-background', 'none']
        
        # 처리된 모든 프레임 찾기
        processed_frames = sorted([f for f in os.listdir(processed_dir) if f.endswith('.png')])
        
        # 각 프레임마다 지연 시간 설정
        for i, frame in enumerate(processed_frames):
            delay_idx = min(i, len(frame_delays) - 1)  # 인덱스가 범위를 벗어나지 않게 처리
            cmd.extend(['-delay', str(frame_delays[delay_idx])])
            cmd.append(os.path.join(processed_dir, frame))
        
        cmd.append(output_path)
        
        app.logger.info(f"GIF 결합 명령 실행: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            app.logger.error(f"GIF 결합 실패: {stderr.decode()}")
            return False, stderr.decode()
        
        app.logger.info(f"GIF combined successfully")
        return True, output_path
    except Exception as e:
        app.logger.error(f"GIF 처리 중 예외 발생: {str(e)}")
        return False, str(e)
    finally:
        # 임시 디렉토리 정리
        try:
            shutil.rmtree(frames_dir, ignore_errors=True)
            shutil.rmtree(processed_dir, ignore_errors=True)
        except:
            pass
        app.logger.info(f"Cleaning up temporary directories")

def process_webp(input_path, output_path, params):
    """WebP 이미지 처리 (애니메이션 WebP 직접 처리)"""
    try:
        img = Image.open(input_path)
        is_animated = hasattr(img, 'n_frames') and img.n_frames > 1
        
        if is_animated:
            # 임시 디렉토리 생성
            frames_dir = tempfile.mkdtemp(prefix='waifu2x_webp_')
            processed_dir = tempfile.mkdtemp(prefix='waifu2x_processed_')
            
            app.logger.info(f"애니메이션 WebP에서 프레임 추출: {input_path}")
            
            # 프레임 추출 및 지연 시간 저장
            frame_delays = []
            frame_count = 0
            
            try:
                while True:
                    # 현재 프레임 저장
                    frame_path = os.path.join(frames_dir, f"frame{frame_count:03d}.png")
                    img.save(frame_path, "PNG")
                    
                    # 지연 시간 저장 (밀리초 단위, 기본값 100ms)
                    delay = img.info.get('duration', 100)
                    frame_delays.append(delay)
                    
                    # 다음 프레임으로 이동
                    frame_count += 1
                    img.seek(img.tell() + 1)
            except EOFError:
                # 모든 프레임 처리 완료
                app.logger.info(f"WebP에서 {frame_count}개 프레임 추출 완료")
                
            # waifu2x로 모든 프레임 처리 (디렉토리 모드)
            cmd = [
                'waifu2x-caffe',
                '-i', frames_dir,
                '-o', processed_dir
            ]
            
            # 파라미터 추가
            if 'mode' in params:
                cmd.extend(['-m', params['mode']])
            if 'noise_level' in params:
                cmd.extend(['-n', str(params['noise_level'])])
            
            # 스케일링 옵션 처리
            if 'scale_mode' in params:
                if params['scale_mode'] == 'ratio' and 'scale_ratio' in params:
                    cmd.extend(['-s', str(params['scale_ratio'])])
                elif params['scale_mode'] == 'width' and 'scale_width' in params and params['scale_width']:
                    cmd.extend(['-w', str(params['scale_width'])])
                elif params['scale_mode'] == 'height' and 'scale_height' in params and params['scale_height']:
                    cmd.extend(['-h', str(params['scale_height'])])
            elif 'scale_ratio' in params:  # 이전 버전과의 호환성 유지
                cmd.extend(['-s', str(params['scale_ratio'])])
            
            if 'process' in params:
                cmd.extend(['-p', params['process']])
            if 'tta' in params and params['tta']:
                cmd.extend(['-t', '1'])
            
            # 출력 포맷은 PNG로 고정 (투명도 보존)
            cmd.extend(['-e', 'png'])
            
            app.logger.info(f"프레임 처리 명령 실행: {' '.join(cmd)}")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('shift_jis') + stdout.decode('shift_jis')
                app.logger.error(f"프레임 처리 실패: {error_msg}")
                return False, error_msg
            
            app.logger.info(f"WebP 프레임 처리 완료")
            
            # 요청된 출력 형식에 따라 애니메이션 생성
            output_format = params.get('output_format', 'webp')
            
            if output_format == 'webp':
                # WebP 애니메이션으로 다시 결합
                processed_frames = sorted([f for f in os.listdir(processed_dir) if f.endswith('.png')])
                images = []
                
                for frame in processed_frames:
                    img_path = os.path.join(processed_dir, frame)
                    images.append(Image.open(img_path))
                
                # 첫 번째 이미지를 기준으로 나머지 이미지 저장
                images[0].save(
                    output_path,
                    format='WEBP',
                    append_images=images[1:],
                    save_all=True,
                    duration=frame_delays,
                    lossless=True,  # 무손실 압축으로 품질 보존
                    quality=95,     # 높은 품질 설정
                    method=6        # 최고 품질 압축 방식
                )
            elif output_format == 'gif':
                # GIF 애니메이션으로 결합
                cmd = ['convert', '-dispose', 'background', '-background', 'none']
                
                # 처리된 모든 프레임 찾기
                processed_frames = sorted([f for f in os.listdir(processed_dir) if f.endswith('.png')])
                
                # 각 프레임마다 지연 시간 설정
                for i, frame in enumerate(processed_frames):
                    delay_idx = min(i, len(frame_delays) - 1)
                    delay_cs = max(1, int(frame_delays[delay_idx] / 10))  # ImageMagick은 1/100초 단위 사용
                    cmd.extend(['-delay', str(delay_cs)])
                    cmd.append(os.path.join(processed_dir, frame))
                
                cmd.append(output_path)
                
                app.logger.info(f"GIF 결합 명령 실행: {' '.join(cmd)}")
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    app.logger.error(f"GIF 결합 실패: {stderr.decode()}")
                    return False, stderr.decode()
            else:
                # PNG 또는 JPG 등으로 저장 (첫 번째 프레임만)
                processed_frames = sorted([f for f in os.listdir(processed_dir) if f.endswith('.png')])
                if processed_frames:
                    img_path = os.path.join(processed_dir, processed_frames[0])
                    img = Image.open(img_path)
                    img.save(output_path, format=output_format.upper())
                    app.logger.info(f"첫 번째 프레임을 {output_format} 형식으로 저장")
            
            app.logger.info(f"처리 완료: {output_path}")
            return True, output_path
            
        else:
            # 일반 WebP는 일반 이미지처럼 처리
            return process_image(input_path, output_path, params)
            
    except Exception as e:
        app.logger.error(f"WebP 처리 중 예외 발생: {str(e)}")
        return False, str(e)
    finally:
        # 임시 디렉토리 정리
        try:
            if 'frames_dir' in locals():
                shutil.rmtree(frames_dir, ignore_errors=True)
            if 'processed_dir' in locals():
                shutil.rmtree(processed_dir, ignore_errors=True)
        except Exception as e:
            app.logger.error(f"임시 디렉토리 정리 중 오류: {str(e)}")
        app.logger.info("임시 디렉토리 정리 완료")

@app.route('/api/v1/process', methods=['POST'])
def process():
    # 파일이 요청에 포함되어 있는지 확인
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        # 고유한 ID 생성
        process_id = str(uuid.uuid4())
        
        # 안전한 파일명 생성 및 파일 저장
        filename = secure_filename(file.filename)
        base_name, extension = os.path.splitext(filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{process_id}{extension}")
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{process_id}")
        
        file.save(input_path)
        
        # 요청에서 파라미터 추출
        params = {
            'mode': request.form.get('mode', 'noise_scale'),
            'noise_level': request.form.get('noise_level', '1'),
            'process': request.form.get('process', 'gpu'),
            'tta': request.form.get('tta', '0') == '1',
            'output_format': request.form.get('output_format', 'png')
        }
        
        # 스케일링 모드 및 관련 파라미터 처리
        scale_mode = request.form.get('scale_mode', 'ratio')
        params['scale_mode'] = scale_mode
        
        if scale_mode == 'ratio':
            params['scale_ratio'] = request.form.get('scale_ratio', '2.0')
        elif scale_mode == 'width':
            params['scale_width'] = request.form.get('scale_width', '')
        elif scale_mode == 'height':
            params['scale_height'] = request.form.get('scale_height', '')
        
        # 파일 확장자에 따라 다른 처리 방식 적용
        extension = extension.lower()
        if extension == '.gif':
            # GIF 처리 경로
            output_gif_path = output_path + '.gif'
            success, result = process_gif(input_path, output_gif_path, params)
        elif extension == '.webp':
            # WebP 처리 경로 (애니메이션 WebP 포함)
            output_format = params['output_format']
            output_webp_path = output_path + '.' + output_format
            success, result = process_webp(input_path, output_webp_path, params)
        else:
            # 일반 이미지 처리 경로
            output_img_path = output_path + '.' + params['output_format']
            success, result = process_image(input_path, output_img_path, params)
        
        # 처리가 완료된 후 임시 입력 파일 삭제
        try:
            os.remove(input_path)
        except:
            pass
        
        if success:
            # 처리 성공 시 결과 이미지 반환
            return send_file(result, as_attachment=True)
        else:
            # 처리 실패 시 에러 반환
            return jsonify({'error': result}), 500
    
    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/api/v1/options', methods=['GET'])
def options():
    """사용 가능한 옵션 목록을 반환합니다"""
    return jsonify({
        'modes': ['noise', 'scale', 'noise_scale', 'auto_scale'],
        'noise_levels': [0, 1, 2, 3],
        'processes': ['cpu', 'gpu', 'cudnn'],
        'output_formats': ['png', 'jpg', 'webp', 'gif'],
        'scale_modes': ['ratio', 'width', 'height']
    })

@app.route('/')
def index():
    # 도움말 페이지
    return """
    <h1>Waifu2x API</h1>
    <p>Upload an image to convert using Waifu2x</p>
    <form method="post" action="/api/v1/process" enctype="multipart/form-data">
        <h3>파일 선택</h3>
        <input type="file" name="file">
        
        <h3>처리 모드</h3>
        <select name="mode">
            <option value="noise_scale">Noise Reduction + 2x Upscaling</option>
            <option value="noise">Noise Reduction</option>
            <option value="scale">2x Upscaling</option>
            <option value="auto_scale">Automatic Upscaling</option>
        </select>
        
        <h3>노이즈 감소 레벨</h3>
        <input type="number" name="noise_level" value="1" min="0" max="3">
        
        <h3>스케일링 방식</h3>
        <div>
            <input type="radio" id="scale_mode_ratio" name="scale_mode" value="ratio" checked>
            <label for="scale_mode_ratio">비율로 확대:</label>
            <input type="number" name="scale_ratio" value="2.0" step="0.1" min="0.1">
        </div>
        <div>
            <input type="radio" id="scale_mode_width" name="scale_mode" value="width">
            <label for="scale_mode_width">너비 지정:</label>
            <input type="number" name="scale_width" placeholder="너비(픽셀)" min="1">
        </div>
        <div>
            <input type="radio" id="scale_mode_height" name="scale_mode" value="height">
            <label for="scale_mode_height">높이 지정:</label>
            <input type="number" name="scale_height" placeholder="높이(픽셀)" min="1">
        </div>
        
        <h3>처리 방식</h3>
        <select name="process">
            <option value="gpu">GPU</option>
            <option value="cpu">CPU</option>
            <option value="cudnn">cuDNN</option>
        </select>
        
        <h3>추가 옵션</h3>
        <input type="checkbox" name="tta" value="1" id="tta">
        <label for="tta">Enable TTA (처리 시간이 늘어나지만 품질이 향상됨)</label>
        
        <h3>출력 형식</h3>
        <select name="output_format">
            <option value="png">PNG</option>
            <option value="jpg">JPEG</option>
            <option value="webp">WebP</option>
            <option value="gif">GIF</option>
        </select>
        
        <div style="margin-top: 20px;">
            <button type="submit">처리 시작</button>
        </div>
    </form>

    <h2>CLI API 사용 방법</h2>
    <p>명령줄에서 curl을 사용하여 API를 호출할 수 있습니다:</p>
    
    <h3>기본 사용법</h3>
    <pre>
    curl -X POST \\
      -F "file=@/path/to/your/image.jpg" \\
      -F "mode=noise_scale" \\
      -F "noise_level=1" \\
      -F "scale_mode=ratio" \\
      -F "scale_ratio=2.0" \\
      -F "process=gpu" \\
      -F "output_format=png" \\
      -o output.png \\
      http://서버주소:8080/api/v1/process
    </pre>
    
    <h3>너비 지정 예시</h3>
    <pre>
    curl -X POST \\
      -F "file=@/path/to/your/image.jpg" \\
      -F "mode=noise_scale" \\
      -F "scale_mode=width" \\
      -F "scale_width=1920" \\
      -o output.png \\
      http://서버주소:8080/api/v1/process
    </pre>
    
    <h3>높이 지정 예시</h3>
    <pre>
    curl -X POST \\
      -F "file=@/path/to/your/image.jpg" \\
      -F "mode=noise_scale" \\
      -F "scale_mode=height" \\
      -F "scale_height=1080" \\
      -o output.png \\
      http://서버주소:8080/api/v1/process
    </pre>
    
    <h3>매개변수 설명</h3>
    <ul>
      <li><strong>file</strong>: 처리할 이미지 파일 (필수)</li>
      <li><strong>mode</strong>: 처리 모드 [noise, scale, noise_scale, auto_scale] (기본값: noise_scale)</li>
      <li><strong>noise_level</strong>: 노이즈 제거 레벨 [0-3] (기본값: 1)</li>
      <li><strong>scale_mode</strong>: 스케일링 방식 [ratio, width, height] (기본값: ratio)</li>
      <li><strong>scale_ratio</strong>: 확대 비율 (기본값: 2.0, scale_mode=ratio일 때 사용)</li>
      <li><strong>scale_width</strong>: 출력 너비(픽셀) (scale_mode=width일 때 사용)</li>
      <li><strong>scale_height</strong>: 출력 높이(픽셀) (scale_mode=height일 때 사용)</li>
      <li><strong>process</strong>: 처리 방법 [cpu, gpu, cudnn] (기본값: gpu)</li>
      <li><strong>tta</strong>: TTA 모드 사용 [0, 1] (기본값: 0)</li>
      <li><strong>output_format</strong>: 출력 형식 [png, jpg, webp, gif] (기본값: png)</li>
    </ul>
    
    <h3>GIF 처리 예시</h3>
    <pre>
    curl -X POST \\
      -F "file=@animation.gif" \\
      -F "mode=noise_scale" \\
      -F "noise_level=1" \\
      -F "output_format=gif" \\
      -o enhanced.gif \\
      http://서버주소:8080/api/v1/process
    </pre>
    
    <h3>WebP 애니메이션 처리 예시</h3>
    <pre>
    curl -X POST \\
      -F "file=@animation.webp" \\
      -F "mode=noise" \\
      -F "noise_level=2" \\
      -F "output_format=webp" \\
      -o enhanced.webp \\
      http://서버주소:8080/api/v1/process
    </pre>

    <h3>사용 가능한 옵션 조회</h3>
    <pre>
    curl http://서버주소:8080/api/v1/options
    </pre>
    
    <script>
    // 스케일링 모드에 따라 입력 필드 활성화/비활성화
    document.addEventListener('DOMContentLoaded', function() {
        const radioButtons = document.querySelectorAll('input[name="scale_mode"]');
        const updateFields = function() {
            const selectedMode = document.querySelector('input[name="scale_mode"]:checked').value;
            document.querySelector('input[name="scale_ratio"]').disabled = (selectedMode !== 'ratio');
            document.querySelector('input[name="scale_width"]').disabled = (selectedMode !== 'width');
            document.querySelector('input[name="scale_height"]').disabled = (selectedMode !== 'height');
        };
        
        radioButtons.forEach(radio => {
            radio.addEventListener('change', updateFields);
        });
        
        // 초기 상태 설정
        updateFields();
    });
    </script>
    """
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0', port=8080, debug=True)