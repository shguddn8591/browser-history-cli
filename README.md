# 브라우저 방문 기록 분석 CLI

터미널에서 브라우저 방문 기록을 분석해 자주 찾는 사이트, 체류 시간, 시간대별 패턴 등을 보여주는 CLI 도구입니다.

**macOS / Windows / Linux** 에서 동작합니다.

---

## 목적

브라우저를 얼마나, 어떻게 사용하고 있는지 수치로 파악하기 위해 만들었습니다.

- 하루 중 언제 가장 많이 탐색하는지
- 어떤 사이트에 실제로 시간을 많이 쏟는지
- 방문 횟수와 실제 체류 시간이 얼마나 다른지

를 한눈에 볼 수 있습니다.

---

## 지원 브라우저

| 브라우저 | macOS | Windows | Linux |
|---|---|---|---|
| Chrome  | ✅ | ✅ | ✅ |
| Firefox | ✅ | ✅ | ✅ |
| Brave   | ✅ | ✅ | ✅ |
| Edge    | ✅ | ✅ | ✅ |
| Vivaldi | ✅ | ✅ | ✅ |
| Opera   | ✅ | ✅ | ✅ |
| Arc     | ✅ | ✅ | ❌ |
| Safari  | ⚠️ | ❌ | ❌ |

설치된 브라우저는 자동으로 감지됩니다.

> Safari는 macOS 전용이며, 터미널에 **전체 디스크 접근** 권한이 필요합니다.

---

## 설치

**요구사항**: Python 3.9 이상

### 1. 프로젝트 클론

```bash
git clone <repo-url>
cd "웹탐색 cli"
```

### 2. 가상환경 생성 및 활성화

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. 패키지 설치

```bash
pip install -e .
```

이후부터는 어디서든 `browser-history` 명령을 사용할 수 있습니다.

> 새 터미널 세션을 열면 `source venv/bin/activate` (Windows: `venv\Scripts\activate`)로 가상환경을 다시 활성화하세요.

---

## 실행 방법

```bash
browser-history <명령> [옵션]
```

### 명령 목록

| 명령 | 설명 |
|---|---|
| `stats` | 통계 대시보드 (기본값) |
| `top` | 자주 방문한 사이트 순위 |
| `browsers` | 감지된 브라우저 목록 확인 |

### 옵션

| 옵션 | 설명 | 기본값 |
|---|---|---|
| `--browser`, `-b` | 특정 브라우저만 분석 (`chrome`, `firefox`, `brave` 등) | 전체 |
| `--days`, `-d` | 최근 N일만 분석 | 전체 기간 |
| `--top`, `-t` | 표시할 사이트 수 | 20 |
| `--sort`, `-s` | 정렬 기준 (`count` \| `duration`) | `count` |
| `--limit`, `-l` | `top` 명령에서 표시할 수 | 20 |

---

## 예시

```bash
# 전체 기간 통계
browser-history stats

# Chrome 브라우저, 최근 7일
browser-history stats --browser chrome --days 7

# 체류 시간 기준 Top 30
browser-history top --sort duration --limit 30

# 최근 30일, 방문 횟수 기준 순위
browser-history top --days 30

# 감지된 브라우저 확인
browser-history browsers
```

---

## 출력 내용

**요약 카드**
- 총 방문 수, 고유 도메인 수, 총 체류 시간, 분석 기간

**Top 사이트 표**
- 도메인별 방문 횟수, 총 체류 시간, 마지막 방문 일시

**시간대 히트맵**
- 0~23시 블록 차트로 언제 가장 많이 탐색하는지 표시

**요일별 막대 차트**
- 주중/주말 구분, 요일별 방문 빈도

**일별 추이**
- 최근 14일간 방문량 변화

---

## Safari 권한 설정 (macOS)

Safari 데이터를 읽으려면 터미널에 전체 디스크 접근 권한이 필요합니다.

**시스템 설정 > 개인 정보 보호 및 보안 > 전체 디스크 접근** 에서 사용 중인 터미널 앱을 추가하세요.

---

## 주의 사항

- 브라우저 실행 중에도 분석 가능합니다. 원본 DB를 직접 수정하지 않고 임시 복사본을 읽습니다.
- 방문 기록은 로컬에서만 처리되며 외부로 전송되지 않습니다.
