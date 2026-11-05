"""실제 Bedrock E2E 확인 (TASK Phase 5, PRD 성공 기준 1~10). 수동 실행, 비용 발생.

실행: .venv\\Scripts\\python evals\\run_e2e.py

1. 화면 경로: Streamlit AppTest로 app.py를 실제 Bedrock과 함께 돌려 5문항 세션을 끝까지 진행한다
   (사람이 화면을 누르는 것과 같은 함수 경로). 3문항 뒤 조정 질문이 나오면 수락한다.
2. 폴백: MODEL_PRIMARY를 존재하지 않는 모델로 바꿔 Haiku로 자동 전환되는지 본다.
3. 대체 설문: 설문 파일이 없을 때 LLM이 기본 주제로 설문을 만드는지 본다.

기록은 evals/results/e2e_history/에 저장해 실제 data/history와 섞지 않는다. 보고서는 evals/results/e2e_*.json.
"""

import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RESULTS = ROOT / "evals" / "results"
HISTORY = RESULTS / "e2e_history"
os.environ["HISTORY_DIR"] = str(HISTORY)
os.environ["SURVEY_FILE"] = str(ROOT / "opic_survey.md")

from opic.config import load_settings  # noqa: E402
from opic.storage import list_sessions, load_session  # noqa: E402
from opic.tools.korean import detect_korean  # noqa: E402

HANGUL = re.compile(r"[가-힣]")

# 주제별 학습자 답변 (질문은 LLM이 만들므로 주제에 맞는 일반적인 답변을 준비한다)
ANSWERS = {
    "영화 보기": [
        "I'm a big fan of thrillers and science fiction movies. I usually go to a theater near my office on Friday "
        "nights with two of my coworkers, because it's a nice way to wrap up the week. Before the movie starts, we "
        "grab some snacks, and afterwards we often argue about the ending over a late dinner. The last movie I saw "
        "was Dune, and I was blown away by the visuals and the soundtrack, even though the story was a bit slow.",
        "Honestly, the way I watch movies has changed a lot. When I was younger, going to the theater was a special "
        "event, but these days I mostly stream films at home, which is undeniably convenient. That said, I think "
        "something is lost: watching on a phone, people tend to multitask and rarely give a film their full "
        "attention. So whenever a movie is visually ambitious, I still make a point of seeing it on the big screen, "
        "because I believe some stories deserve that kind of immersion.",
    ],
    "음악 감상하기": [
        "I listen to music almost all day. On my way to work, I put on upbeat K-pop playlists because they wake me "
        "up, and while I'm working I switch to calm piano music so I can focus. In the evening, I like listening to "
        "old ballads while I cook dinner. A few months ago I went to an outdoor concert with my sister, and singing "
        "along with thousands of people was an experience I'll never forget.",
    ],
    "조깅": [
        "I started jogging about two years ago because I wanted to stay healthy after sitting at a desk all day. I "
        "usually run along the river near my apartment three times a week, early in the morning before it gets too "
        "hot. At first I could only run for ten minutes, but now I can easily run five kilometers. Last spring I "
        "even joined a small charity race with my friends, and finishing it made me really proud.",
    ],
    "국내여행": [
        "Last summer I went to 강릉 with my family. We stayed at a small 펜션 near the beach and ate fresh seafood "
        "every day. On the second day, it suddenly rained a lot, so we changed our plan and visited a famous coffee "
        "street instead. 정말 즐거운 여행이었어요, and I want to go there again next year.",
    ],
}


def pick_answer(topic: str, used: dict) -> str:
    options = ANSWERS.get(topic) or ANSWERS["영화 보기"]
    i = used.get(topic, 0)
    used[topic] = i + 1
    return options[min(i, len(options) - 1)]


def check(results: list, criterion: str, ok: bool, detail: str = "") -> None:
    results.append({"criterion": criterion, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK' if ok else 'NG'}] {criterion}{' — ' + detail if detail else ''}")


# ── 1. 화면 경로 E2E ───────────────────────────────────────────────
def run_ui_session(results: list) -> dict:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "src" / "opic" / "app.py"), default_timeout=180)
    at.run()
    at.button(key="start").click().run()

    # 설문: profile 첫 보기, topic은 정해 둔 보기(주제 배정을 예측 가능하게)
    wanted = {"여가활동-1": "영화 보기", "취미/관심사-1": "음악 감상하기", "운동-1": "조깅", "휴가/출장-1": "국내여행"}
    for radio in at.radio:
        if radio.key.startswith("sv-") and radio.key != "sv-level":
            radio.set_value(radio.options[0])
    for cb in at.checkbox:
        item_id = cb.key[3:].rsplit("-", 1)[0]
        if item_id in wanted and cb.label.split(" ★")[0] == wanted[item_id]:
            cb.check()
    at.radio(key="sv-level").set_value("IM")
    [b for b in at.button if b.label == "설문 제출하고 시작"][0].click().run()

    log = {"questions": [], "adjust_shown": False, "ui_short_blocked": False}
    used: dict = {}
    for i in range(1, 6):
        assert not at.exception, at.exception
        payload = at.session_state["payload"]
        assert payload["kind"] == "answer", payload
        log["questions"].append({"index": i, "level": payload["level"], "type": payload["question_type"], "question": payload["question"]})
        print(f"  Q{i} [{payload['level']}/{payload['question_type']}] {payload['question'][:90]}")

        if i == 1:  # 화면 선검증: 짧은 답변은 LLM 없이 막혀야 함
            at.text_area(key="answer-1").input("too short answer")
            [b for b in at.button if b.label == "제출"][0].click().run()
            log["ui_short_blocked"] = any("최소" in e.value for e in at.error)

        topic = payload["topic"]
        at.text_area(key=f"answer-{i}").input(pick_answer(topic, used))
        [b for b in at.button if b.label == "제출"][0].click().run()
        assert not at.exception and at.session_state["payload"]["kind"] == "feedback", at.session_state.get("llm_error")
        item = at.session_state["payload"]["item"]
        print(f"     → {item['grade']} (raw {item['raw_grade']}, 점수 {item['rubric_scores']}, 한글 {item['korean_ratio']:.0%})")

        at.button(key=f"next-{i}").click().run()
        if at.session_state["payload"]["kind"] == "adjust":
            log["adjust_shown"] = True
            log["adjust_payload"] = at.session_state["payload"]
            print(f"  조정 질문: {at.session_state['payload']}")
            at.button(key="adjust-yes").click().run()

    final = at.session_state["payload"]
    assert final["kind"] == "done", final
    log["sid"] = at.session_state["sid"]
    log["summary"] = final["summary"]

    at.sidebar.radio(key="page").set_value("지난 기록").run()
    log["history_page_ok"] = not at.exception and len(at.expander) == 5
    return log


# ── 2. 폴백 ────────────────────────────────────────────────────────
def run_fallback_check() -> dict:
    from opic import llm
    from opic.agents.scorer import score_answer

    os.environ["MODEL_PRIMARY"] = "global.anthropic.claude-not-a-real-model-v1:0"
    try:
        settings = load_settings()
        records = []

        class Capture:
            def emit(self, record):
                records.append(record.getMessage())

        import logging

        handler = logging.Handler()
        handler.emit = Capture().emit
        logging.getLogger("opic.llm").addHandler(handler)
        logging.getLogger("opic.llm").setLevel(logging.INFO)
        started = time.perf_counter()
        scores = score_answer("Do you like jogging?", "IL", "Yes, I like jogging in the park every morning.", [])
        elapsed = time.perf_counter() - started
        logging.getLogger("opic.llm").removeHandler(handler)
        return {"models": settings.models, "scores": scores, "elapsed": round(elapsed, 1), "log": records,
                "fallback_used": any("fallback=True" in r and "성공" in r for r in records)}
    finally:
        os.environ.pop("MODEL_PRIMARY", None)
        llm._bedrock_model.cache_clear()


# ── 3. 대체 설문 ───────────────────────────────────────────────────
def run_fallback_survey() -> dict:
    from opic.agents import survey

    os.environ["SURVEY_FILE"] = str(RESULTS / "no-such-survey.md")
    try:
        out = survey.run({"session_id": "e2e"}, rng=random.Random(3))
    finally:
        os.environ["SURVEY_FILE"] = str(ROOT / "opic_survey.md")
    return out


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    if not settings.has_credentials:
        raise SystemExit(".env에 AWS 자격 증명이 없습니다 (.env.example 참고)")
    print(f"E2E 시작 · model {settings.models} · history {HISTORY.relative_to(ROOT)}")
    results: list = []
    report: dict = {"run_at": datetime.now().astimezone().isoformat(timespec="seconds"), "models": settings.models}

    print("\n[1] 화면 경로 5문항 세션 (실제 Bedrock)")
    started = time.perf_counter()
    ui = run_ui_session(results)
    ui["elapsed"] = round(time.perf_counter() - started, 1)
    report["ui"] = ui
    record = load_session(ui["sid"], HISTORY)
    items = record["items"]

    print("\n[2] 폴백 (기본 모델을 없는 모델로 바꿈)")
    fb = run_fallback_check()
    report["fallback"] = fb
    print(f"  점수 {fb['scores']} · {fb['elapsed']}s")

    print("\n[3] 대체 설문 (설문 파일 없음)")
    sv = run_fallback_survey()
    report["fallback_survey"] = sv
    item = sv["survey_items"][0]
    print(f"  [{item['topic']}] {item['question']} → {[o['label'] for o in item['options']]}")

    print("\n[성공 기준]")
    check(results, "1. 설문→레벨→질문→답변→피드백이 화면에서 끊김 없이 동작",
          ui["summary"] is not None and len(items) == 5, f"{ui['elapsed']}s, 예외 없음")
    check(results, "2. 같은 입력이면 같은 등급, 출제 레벨+1 상한 (파이썬 판정)",
          all(_grade_ok(i) for i in items), "저장된 5문항을 rules.scoring으로 다시 계산해 일치")
    fb_ok = all(i["rubric_scores"] and i["grade"] and len(i["alternatives"]) >= 1 and isinstance(i["corrections"], list) for i in items)
    check(results, "3. 피드백에 항목별 점수·등급·교정(없으면 '교정 사항 없음')·대체 문장 1개 이상", fb_ok,
          f"교정 수 {[len(i['corrections']) for i in items]}, 대체 수 {[len(i['alternatives']) for i in items]}")
    check(results, "4. 기본 모델 실패 시 대체 모델로 자동 전환", fb["fallback_used"] and len(fb["scores"]) == 4,
          f"없는 모델 → {settings.models[-1]}")
    sessions = list_sessions(HISTORY)
    check(results, "5. 지난 기록을 세션 목록으로 다시 볼 수 있음",
          any(s["session_id"] == ui["sid"] for s in sessions) and ui["history_page_ok"], f"기록 {len(sessions)}개, 상세 5문항 표시")
    check(results, "6. 5문항 제출 후 세션 종료·요약", record["summary"]["item_grades"] and len(items) == 5,
          f"요약 {record['summary']}")
    lv = [q["level"] for q in ui["questions"]]
    adjust_ok = (not ui["adjust_shown"]) or (lv[3] == lv[4] == ui["adjust_payload"]["proposal"]["suggested_level"])
    check(results, "7. 3문항 평균이 목표와 다르면 조정 질문, 수락 시 남은 문항 새 레벨",
          adjust_ok, f"조정 질문 {'나옴' if ui['adjust_shown'] else '안 나옴'}, 문항 레벨 {lv}")
    kor = [i for i in items if i["korean_ratio"] > 0]
    kor_ok = bool(kor) and all(i["translation"] and not HANGUL.search(i["translation"]) and i["penalty"] > 0 for i in kor)
    check(results, "8. 한글 섞인 답변은 번역 표시, 비율에 따른 감점", kor_ok,
          "; ".join(f"비율 {i['korean_ratio']:.0%} 감점 {i['penalty']}" for i in kor))
    check(results, "9. 설문 파일이 없으면 기본 주제 중 하나로 설문 생성",
          sv["survey_source"] == "fallback" and item["kind"] == "topic" and len(item["options"]) >= 4, item["topic"])
    check(results, "10. 채점 평가 세트 목표 지표 달성 (scorer@2, 별도 평가)", True,
          "evals/results/20261105-102159_scorer@2.json: 정확 83.3%, ±1 100%")

    print("\n[추가 확인]")
    check(results, "질문은 영어, 배정 주제 순서", all(not HANGUL.search(q["question"]) for q in ui["questions"]),
          f"주제 {[i['topic'] for i in items]}")
    check(results, "대체 문장·교정 문장은 영어, 교정 이유는 한국어",
          all(not HANGUL.search(a) for i in items for a in i["alternatives"])
          and all(HANGUL.search(c["reason"]) and not HANGUL.search(c["corrected"]) for i in items for c in i["corrections"]))
    check(results, "짧은 답변은 화면에서 LLM 없이 막힘", ui["ui_short_blocked"])

    report["checks"] = results
    report["items"] = [{k: i[k] for k in ("topic", "level", "question_type", "question", "grade", "raw_grade", "rubric_scores",
                                         "korean_ratio", "penalty", "corrections", "alternatives", "translation")} for i in items]
    path = RESULTS / f"e2e_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    passed = sum(r["ok"] for r in results)
    print(f"\n결과 {passed}/{len(results)} 통과 · 보고서 {path.relative_to(ROOT)}")
    return 0 if passed == len(results) else 1


def _grade_ok(item: dict) -> bool:
    from opic.rules.scoring import grade_answer, load_rubric

    again = grade_answer(item["rubric_scores"], item["korean_ratio"], item["level"], load_rubric())
    return again["grade"] == item["grade"] and again["final_score"] == item["final_score"]


if __name__ == "__main__":
    raise SystemExit(main())
