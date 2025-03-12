# Waifu2X API Server

애니메이션 스타일의 이미지와 애니메이션을 고품질로 업스케일링하고 노이즈 제거를 수행하는 RESTful API 서버입니다. 이 프로젝트는 [waifu2x-caffe](https://github.com/lltcggie/waifu2x-caffe)를 이미지 처리 엔진으로 활용하며, 웹 기반 인터페이스와 API 엔드포인트를 제공합니다.

## 주요 기능

- 이미지 업스케일링 (비율, 너비, 높이 지정 방식 지원)
- 다양한 레벨의 노이즈 제거
- 다양한 이미지 형식 지원 (PNG, JPG, JPEG, WebP, BMP, TIF, TIFF, TGA)
- GIF 애니메이션 처리 지원
- 애니메이션 WebP 처리 지원
- 사용하기 쉬운 웹 인터페이스
- 단순한 RESTful API

## 요구 사항

- Docker 및 Docker Compose
- NVIDIA GPU (CUDA 지원) (선택적)
- NVIDIA Container Toolkit (선택적)

## 설치 방법

### 1. NVIDIA Container Toolkit 설치 (선택적)

```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. docker-compose.yml 파일 생성

```yaml
version: '3.8'

services:
  waifu2x:
    image: kamilake/waifu2x-api-server
    ports:
      - "8080:80"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: always
```

### 3. 실행

```bash
docker-compose up -d
```

서버가 시작되면 `http://localhost:8080`으로 접속할 수 있습니다.

## 사용 방법

### 웹 인터페이스

웹 브라우저에서 `http://localhost:8080`에 접속하면 아래와 같은 기능을 사용할 수 있습니다:

- 이미지 파일 업로드
- 처리 모드 선택 (노이즈 제거, 업스케일링, 둘 다)
- 노이즈 감소 레벨 선택 (0-3)
- 스케일링 방식 선택 (비율, 너비, 높이)
- 처리 방식 선택 (CPU, GPU, cuDNN)
- 출력 형식 선택 (PNG, JPEG, WebP, GIF)
- TTA(Test-Time Augmentation) 활성화 옵션

### API 사용법

#### 기본 사용법

```bash
curl -X POST \
  -F "file=@/path/to/your/image.jpg" \
  -F "mode=noise_scale" \
  -F "noise_level=1" \
  -F "scale_mode=ratio" \
  -F "scale_ratio=2.0" \
  -F "process=gpu" \
  -F "output_format=png" \
  -o output.png \
  http://localhost:8080/api/v1/process
```

#### 너비 지정 예시

```bash
curl -X POST \
  -F "file=@/path/to/your/image.jpg" \
  -F "mode=noise_scale" \
  -F "scale_mode=width" \
  -F "scale_width=1920" \
  -o output.png \
  http://localhost:8080/api/v1/process
```

#### 높이 지정 예시

```bash
curl -X POST \
  -F "file=@/path/to/your/image.jpg" \
  -F "mode=noise_scale" \
  -F "scale_mode=height" \
  -F "scale_height=1080" \
  -o output.png \
  http://localhost:8080/api/v1/process
```

#### GIF 처리 예시

```bash
curl -X POST \
  -F "file=@animation.gif" \
  -F "mode=noise_scale" \
  -F "noise_level=1" \
  -F "output_format=gif" \
  -o enhanced.gif \
  http://localhost:8080/api/v1/process
```

#### WebP 애니메이션 처리 예시

```bash
curl -X POST \
  -F "file=@animation.webp" \
  -F "mode=noise" \
  -F "noise_level=2" \
  -F "output_format=webp" \
  -o enhanced.webp \
  http://localhost:8080/api/v1/process
```

#### 사용 가능한 옵션 조회

```bash
curl http://localhost:8080/api/v1/options
```

### API 매개변수

| 매개변수 | 설명 | 값 | 기본값 |
|---------|------|------|---------|
| `file` | 처리할 이미지 파일 | 이미지 파일 | (필수) |
| `mode` | 처리 모드 | `noise`, `scale`, `noise_scale`, `auto_scale` | `noise_scale` |
| `noise_level` | 노이즈 제거 레벨 | 0, 1, 2, 3 | 1 |
| `scale_mode` | 스케일링 방식 | `ratio`, `width`, `height` | `ratio` |
| `scale_ratio` | 확대 비율 | 0.1 이상의 숫자 | 2.0 |
| `scale_width` | 출력 너비(픽셀) | 숫자 | - |
| `scale_height` | 출력 높이(픽셀) | 숫자 | - |
| `process` | 처리 방법 | `cpu`, `gpu`, `cudnn` | `gpu` |
| `tta` | TTA 모드 사용 | 0, 1 | 0 |
| `output_format` | 출력 형식 | `png`, `jpg`, `webp`, `gif` | `png` |

## 동작 원리

이 서버는 다음과 같은 과정으로 이미지를 처리합니다:

1. 클라이언트가 이미지를 업로드하면 서버에 임시 저장
2. 이미지 형식에 따라 적절한 처리 함수 호출:
   - 일반 이미지: `process_image`
   - GIF 애니메이션: `process_gif`
   - WebP 애니메이션: `process_webp`
3. waifu2x-caffe를 사용하여 이미지 처리
4. GIF나 애니메이션 WebP인 경우 프레임 추출 → 개별 처리 → 재결합
5. 처리된 이미지를 클라이언트에 반환

## 성능 최적화

- GPU 가속으로 처리 속도 향상
- 애니메이션 처리에 멀티프레임 처리 방식 적용
- 처리 완료 후 임시 파일 자동 정리

## 직접 빌드

소스코드에서 직접 이미지를 빌드하려면:

1. 이 저장소를 클론합니다.
2. docker-compose.yml 파일에서 build 부분의 주석을 해제합니다.
3. `docker-compose build`를 실행합니다.
4. `docker-compose up -d`로 서버를 시작합니다.

## 라이센스

MIT License

## 기여 방법

1. 이 저장소를 포크합니다.
2. 새로운 기능 브랜치를 만듭니다: `git checkout -b my-new-feature`
3. 변경 사항을 커밋합니다: `git commit -am 'Add some feature'`
4. 브랜치에 푸시합니다: `git push origin my-new-feature`
5. Pull Request를 제출합니다.

## 저작권 및 감사의 말

- 이 프로젝트는 [waifu2x-caffe](https://github.com/lltcggie/waifu2x-caffe)를 사용합니다.
- waifu2x 원본 프로젝트: https://github.com/nagadomi/waifu2x

---

문제나 제안사항이 있으시면 GitHub 이슈를 통해 알려주세요.