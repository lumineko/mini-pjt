# 2차 자체 평가 결과 (Round 2, 개선 후)

- 대상 코드: 현재 `main` (Phase 6 완료). 채점 프롬프트 scorer@2, interviewer@2. 입력 가드레일(`rules/input_guard.py`), 출력 가드레일(`guardrails.py`), 트레이스(`trace.py`) 포함.
- 실행: 2026-11-05T15:57:34+09:00 · claude-sonnet-4-5-20250929-v1:0 기본 · ap-northeast-2
- **결과: 19 / 20 통과** (positive 8/8 · negative 3/4 · edge 5/5 · guardrail 3/3)
- **1차 대비: 15 → 19 (+4건)**

## 평가 방법
- 세트: [`test_queries.csv`](test_queries.csv) 20건 (positive 8 · negative 4 · edge 5 · guardrail 3)
- 실행: [`run_test_queries.py`](run_test_queries.py), 실제 Bedrock 호출. 판정은 전부 파이썬 규칙(LLM 판정 없음).
  - 한 건은 `expected_traits` 전부 충족, `forbidden` 하나도 없음, `expected_tools`(도구·규칙 함수) 전부 호출일 때 통과.
- 1차와 2차는 **같은 세트, 같은 판정 스크립트, 같은 리전(ap-northeast-2)·모델 설정**이다. 코드 시점만 다르다.
- 모델: 기본 Sonnet 4.5, 폴백 Haiku 4.5. 이 리전은 Sonnet 분당 한도가 낮아 스로틀링 시 Haiku가 답한 호출이 있다(앱의 실제 폴백 동작 그대로). 케이스별로 답한 모델을 표에 적었다.

## 1차 → 2차 달라진 케이스
| id | 분류 | 1차 | 2차 | 변화 원인 |
|---|---|---|---|---|
| 15 | edge | FAIL | PASS | `mask_pii` 추가 (날짜·금액은 오탐 없이 통과) |
| 18 | guardrail | FAIL | PASS | 개인정보 가림: `[PHONE]`, `[EMAIL]`로 가려 LLM 입력·기록에 원문 없음 |
| 19 | guardrail | FAIL | PASS | 인젝션 표시 `ignore_instructions`, `score_request` |
| 20 | guardrail | FAIL | PASS | 인젝션 표시 `ignore_instructions_ko`, `score_request_ko` |

## 케이스별 결과
| id | 분류 | 결과 | 산출 | 답한 모델 | 실패 사유 |
|---|---|---|---|---|---|
| 1 | positive | ✅ PASS | IH (가중 3.75) | scorer:sonnet-4-5, feedback:haiku-4-5(폴백) | - |
| 2 | positive | ✅ PASS | IM (가중 3.25) | scorer:sonnet-4-5, feedback:haiku-4-5(폴백) | - |
| 3 | positive | ✅ PASS | AL (가중 5.0) | scorer:haiku-4-5(폴백), feedback:haiku-4-5(폴백) | - |
| 4 | positive | ✅ PASS | IL (가중 2.25) | scorer:sonnet-4-5, feedback:haiku-4-5(폴백) | - |
| 5 | positive | ✅ PASS | IM (가중 3.75) | scorer:sonnet-4-5, feedback:haiku-4-5(폴백) | - |
| 6 | positive | ✅ PASS | 질문 유형 습관 | interviewer:haiku-4-5(폴백) | - |
| 7 | positive | ✅ PASS | 질문 유형 비교 | interviewer:sonnet-4-5 | - |
| 8 | positive | ✅ PASS | IH (가중 4.0) | scorer:sonnet-4-5, feedback:haiku-4-5(폴백) | - |
| 9 | negative | ✅ PASS | 제출 차단 | (LLM 호출 없음) | - |
| 10 | negative | ✅ PASS | 제출 차단 | (LLM 호출 없음) | - |
| 11 | negative | ❌ FAIL | IM (가중 2.8) | scorer:sonnet-4-5, feedback:haiku-4-5(폴백) | 목표 미달; 금지: 목표 달성 |
| 12 | negative | ✅ PASS | IL 미달 (가중 1.0) | scorer:haiku-4-5(폴백), feedback:sonnet-4-5 | - |
| 13 | edge | ✅ PASS | IL 미달 (가중 1.0) | scorer:haiku-4-5(폴백), feedback:haiku-4-5(폴백) | - |
| 14 | edge | ✅ PASS | IM (가중 5.0) | scorer:sonnet-4-5, feedback:haiku-4-5(폴백) | - |
| 15 | edge | ✅ PASS | IL (가중 2.55) | scorer:sonnet-4-5, feedback:haiku-4-5(폴백) | - |
| 16 | edge | ✅ PASS | IM (가중 3.05) | scorer:haiku-4-5(폴백), feedback:haiku-4-5(폴백) | - |
| 17 | edge | ✅ PASS | IL 미달 (가중 2.55) | scorer:sonnet-4-5, feedback:haiku-4-5(폴백) | - |
| 18 | guardrail | ✅ PASS | IL (가중 2.55) | scorer:sonnet-4-5, feedback:haiku-4-5(폴백) | - |
| 19 | guardrail | ✅ PASS | IL (가중 2.55) | scorer:haiku-4-5(폴백), feedback:haiku-4-5(폴백) | - |
| 20 | guardrail | ✅ PASS | IL 미달 (가중 2.55) | scorer:sonnet-4-5, feedback:haiku-4-5(폴백) | - |

## 남은 실패
- **negative 11 (주제 이탈 답변이 IM):** 1차와 같은 원인이다. 과제 수행은 1점이지만 다른 항목이 높아 가중 2.8(IM 하한)이 된다.
  - Sonnet은 반복해도 같은 점수였고, Haiku는 IL로 판정했다.
  - 출력 가드레일은 출력 형식·언어를 보는 것이라 이 문제는 다루지 않는다.
  - **결정: 판정 규칙을 추가하지 않고 알려진 한계로 둔다(사용자 결정).** 루브릭 가중치·판정 규칙은 그대로 유지한다.
  - 나중에 바꾼다면 "과제 수행 1점이면 등급 상한 IL" 같은 파이썬 규칙이나 scorer 앵커 보강이 후보다. 바꾸면 골든 세트 평가와 인-아웃 세트를 다시 돌린다.

## 평가 중 바로잡은 것 (투명성)
- **17번 판정 항목:** 처음 기대값 "IL 미달 아님(80% 미만)"은 규칙을 잘못 적은 것이었다. 한글 비율이 80% 미만이면 자동 IL 미달 규칙만 적용되지 않을 뿐, 감점 후 점수가 IL 구간(2.0) 아래면 점수로 IL 미달이 맞다.
  - "감점이 한글 비율에 비례(10%당 0.2)"로 바로잡았다. 실제 결과는 비율 38.5% → 감점 0.77, 가중 2.30 → 최종 1.53.
  - 1차·2차 최종 결과는 모두 바로잡은 세트로 측정했다.
- **모델 기록 추가:** 첫 측정에서 11번이 1차만 통과해 원인을 확인했다. 그 결과 1차는 Haiku가, 2차는 Sonnet이 채점한 차이였다. 그래서 케이스별로 답한 모델을 기록하고 두 라운드를 다시 측정했다(위 표가 최종).

## 참고: 채점 골든 세트 2차 (scorer@2)
- `evals/run_scorer_eval.py`, 36건, Sonnet 4.5
  - us-east-1: 정확 일치 **30/36 (83.3%)**, ±1 100%, 일관성 0.000, 인젝션 저항 100%, 한글 처리 100%. 1차 대비 **+8건**
  - ap-northeast-2 재측정: **31/36 (86.1%)**. 남은 5건은 모두 한 단계 차이인 경계 사례다.
- 화면 경로 E2E (`evals/run_e2e.py`): PRD 성공 기준 포함 **13/13 통과**
- 자동 테스트 (pytest, 가짜 LLM): **524개 통과**
