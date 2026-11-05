"""Streamlit 화면 (PRD 시나리오 1·2 / SERVICE §4 Streamlit 연동).

실행: .venv\\Scripts\\python -m streamlit run src/opic/app.py

- 사이드바 메뉴: 연습 / 지난 기록. 사이드바에 진행 상황과 '새 연습 시작'.
- 화면은 그래프가 돌려준 interrupt 값(kind: survey, answer, feedback, adjust, done)에 맞춰 그린다.
- 그래프·체크포인터는 @st.cache_resource로 프로세스당 1개, session_id는 st.session_state에 둔다.
- 최소 답변 길이는 화면에서 먼저 막고, 그래프도 같은 함수로 다시 검증한다.
- LLM이 모두 실패하면 '다시 시도'로 마지막 체크포인트부터 이어 간다.
"""

import sys
from pathlib import Path

if __package__ in (None, ""):  # `streamlit run src/opic/app.py`로 실행될 때 opic 패키지를 찾도록
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from opic import graph as g
from opic import guardrails
from opic import trace
from opic.config import load_settings, setup_logging
from opic.llm import LLMError
from opic.rules.input_guard import PII_NAMES_KO
from opic.rules.validation import validate_answer
from opic.storage import list_sessions, load_session

PAGES = ("연습", "지난 기록")
RUBRIC_LABELS = {"grammar": "문법", "vocabulary": "어휘", "organization": "구성", "task": "과제 수행"}


@st.cache_resource
def app_graph():
    settings = load_settings()
    setup_logging(settings)
    guardrails.install()  # 출력 검사(after 훅 앞쪽)
    trace.install(settings)  # 트레이스 기록기(after 훅 맨 끝)
    return g.build_graph()


# ── 상태 ───────────────────────────────────────────────────────────
def reset_session() -> None:
    for key in ("sid", "payload", "llm_error", "ui_error"):
        st.session_state.pop(key, None)


def call_graph(fn, *args) -> None:
    """그래프 호출을 감싸 LLM 실패를 화면 상태로 바꾼다."""
    st.session_state.pop("llm_error", None)
    st.session_state.pop("ui_error", None)
    try:
        with st.spinner("AI가 처리하는 중입니다..."):
            result = fn(*args)
    except LLMError as exc:
        st.session_state["llm_error"] = str(exc)
        return
    if isinstance(result, tuple):  # start_session → (sid, payload)
        st.session_state["sid"], st.session_state["payload"] = result
    else:
        st.session_state["payload"] = result


def start() -> None:
    reset_session()
    call_graph(g.start_session, app_graph())


def send(value) -> None:
    call_graph(g.resume, st.session_state["sid"], value, app_graph())


def retry() -> None:
    call_graph(g.retry, st.session_state["sid"], app_graph())


# ── 사이드바 ───────────────────────────────────────────────────────
def sidebar() -> str:
    with st.sidebar:
        st.title("OPIc 텍스트 연습")
        page = st.radio("메뉴", PAGES, key="page", label_visibility="collapsed")
        sid = st.session_state.get("sid")
        if sid:
            state = g.get_state(sid, app_graph())
            st.divider()
            st.caption("진행 상황")
            done = len(state.get("items") or [])
            st.progress(done / 5, text=f"문항 {done} / 5 완료")
            if state.get("current_level"):
                st.write(f"현재 레벨: **{state['current_level']}**")
        st.divider()
        st.button("새 연습 시작", key="sidebar_new", on_click=start, use_container_width=True)
    return page


# ── 연습: 화면별 ───────────────────────────────────────────────────
def option_text(option) -> str:
    return option["label"] + (" " + "★" * option["recommend"] if option["recommend"] else "")


def render_survey(p) -> None:
    st.subheader("관심사 설문")
    if p.get("notice"):
        st.info(p["notice"])
    if p.get("source") == "fallback":
        st.caption("설문 파일이 없어 기본 주제로 만든 설문입니다.")
    if p.get("error"):
        st.error(p["error"])

    with st.form("survey_form"):
        answers = {}
        for item in p["items"]:
            labels = [o["label"] for o in item["options"]]
            texts = {o["label"]: option_text(o) for o in item["options"]}
            st.markdown(f"**[{item['topic']}] {item['question']}**")
            if item["kind"] == "profile":
                by_text = {texts[label]: label for label in labels}  # 화면 문자열(★ 포함) → 보기 이름
                choice = st.radio(
                    item["question"], list(by_text), index=None, key=f"sv-{item['id']}",
                    label_visibility="collapsed",
                )
                answers[item["id"]] = [by_text[choice]] if choice else []
            else:
                cols = st.columns(3)
                answers[item["id"]] = [
                    label for i, label in enumerate(labels)
                    if cols[i % 3].checkbox(texts[label], key=f"sv-{item['id']}-{i}")
                ]
        st.divider()
        level = st.radio("목표 레벨", p["levels"], index=None, horizontal=True, key="sv-level")
        if st.form_submit_button("설문 제출하고 시작", type="primary"):
            send({"answers": answers, "level": level})
            st.rerun()


def render_answer(p) -> None:
    st.subheader(f"문항 {p['item_index']} / {p['total']}")
    st.caption(f"레벨 {p['level']} · 주제 {p['topic']} · 유형 {p['question_type']}")
    st.markdown(f"### {p['question']}")
    if p.get("error"):
        st.error(p["error"])
    if st.session_state.get("ui_error"):
        st.error(st.session_state["ui_error"])

    with st.form(f"answer_form_{p['item_index']}"):
        text = st.text_area("영어로 답변을 입력하세요", height=220, key=f"answer-{p['item_index']}")
        st.caption(f"최소 {p['min_words']}단어 이상 · 전화번호·이메일 같은 개인정보는 자동으로 가려서 채점·저장합니다")
        if st.form_submit_button("제출", type="primary"):
            error = validate_answer(text, p["min_words"])
            if error:
                st.session_state["ui_error"] = error
            else:
                send(text)
            st.rerun()


def render_item_feedback(item) -> None:
    """피드백 화면과 기록 상세에서 함께 쓴다."""
    if item.get("pii_types"):
        names = ", ".join(PII_NAMES_KO.get(t, t) for t in item["pii_types"])
        st.info(f"답변 속 개인정보로 보이는 부분({names})은 가려서 채점·저장했습니다.")
    cols = st.columns(3)
    cols[0].metric("판정 등급", item["grade"])
    cols[1].metric("출제 레벨", item["level"])
    cols[2].metric("목표 달성", "달성" if item["achieved"] else "미달")
    if item["raw_grade"] != item["grade"]:
        st.caption(f"점수상 등급은 {item['raw_grade']}이지만, 출제 레벨 상한으로 {item['grade']}입니다.")

    st.markdown("**루브릭 점수**")
    st.table({RUBRIC_LABELS.get(k, k): [v] for k, v in item["rubric_scores"].items()})
    line = f"가중 점수 {item['weighted_score']}"
    if item["penalty"]:
        line += f" − 한글 감점 {item['penalty']} = 최종 {item['final_score']}"
    st.caption(line + f" (한글 비율 {item['korean_ratio']:.0%})")

    st.markdown("**문법 교정**")
    if item["corrections"]:
        for c in item["corrections"]:
            st.markdown(f"- ~~{c['original']}~~ → **{c['corrected']}**  \n  {c['reason']}")
    else:
        st.success("교정 사항 없음")

    st.markdown("**대체 문장 추천**")
    for alt in item["alternatives"]:
        st.markdown(f"- {alt}")

    if item.get("translation"):
        st.markdown("**한글 부분 영어 번역**")
        st.info(item["translation"])


def render_feedback(p) -> None:
    item = p["item"]
    st.subheader(f"문항 {p['item_index']} / {p['total']} 피드백")
    with st.expander("질문과 내 답변", expanded=False):
        st.markdown(f"**Q.** {item['question']}")
        st.write(item["answer"])
    render_item_feedback(item)
    label = "결과 보기" if p["is_last"] else "다음 문제"
    st.button(label, type="primary", key=f"next-{p['item_index']}", on_click=send, args=(True,))


def render_adjust(p) -> None:
    proposal = p["proposal"]
    st.subheader("난이도 점검")
    direction = "높습니다" if proposal["direction"] == "up" else "낮습니다"
    st.write(f"3문항 평균 등급은 **{p['average_grade']}**로, 목표 레벨 **{p['current_level']}**보다 {direction}.")
    st.write(f"남은 2문항을 **{proposal['suggested_level']}** 레벨로 바꿀까요?")
    cols = st.columns(2)
    cols[0].button(f"예, {proposal['suggested_level']}로 변경", type="primary", key="adjust-yes", on_click=send, args=(True,))
    cols[1].button(f"아니요, {p['current_level']} 유지", key="adjust-no", on_click=send, args=(False,))


def render_summary(summary) -> None:
    cols = st.columns(3)
    cols[0].metric("평균 등급", summary["average_grade"])
    cols[1].metric("시작 레벨", summary["initial_level"])
    cols[2].metric("최종 레벨", summary["final_level"])
    st.write("난이도 변경: " + ("있음" if summary["level_changed"] else "없음"))
    st.table({f"문항 {i}": [g_] for i, g_ in enumerate(summary["item_grades"], 1)})


def render_done(p) -> None:
    st.subheader("세션 결과")
    render_summary(p["summary"])
    st.success("기록이 저장되었습니다. '지난 기록'에서 다시 볼 수 있습니다.")
    st.button("새 연습 시작", type="primary", key="done-new", on_click=start)


RENDERERS = {
    "survey": render_survey,
    "answer": render_answer,
    "feedback": render_feedback,
    "adjust": render_adjust,
    "done": render_done,
}


def practice_page() -> None:
    if st.session_state.get("llm_error"):
        st.error("AI 응답을 받지 못했습니다. 잠시 후 다시 시도해 주세요.")
        with st.expander("오류 내용"):
            st.code(st.session_state["llm_error"])
        if st.session_state.get("sid"):
            st.button("다시 시도", type="primary", key="retry", on_click=retry)
        else:
            st.button("다시 시도", type="primary", key="retry-start", on_click=start)
        return

    payload = st.session_state.get("payload")
    if payload is None:
        st.header("OPIc 텍스트 연습")
        st.write("관심사 설문과 목표 레벨을 고르면 AI가 한 문제씩 질문합니다. 한 세션은 5문항입니다.")
        st.button("연습 시작", type="primary", key="start", on_click=start)
        return
    RENDERERS[payload["kind"]](payload)


# ── 지난 기록 ──────────────────────────────────────────────────────
def history_page() -> None:
    st.header("지난 기록")
    history_dir = load_settings().history_dir
    sessions = list_sessions(history_dir)
    if not sessions:
        st.info("아직 저장된 연습 기록이 없습니다. 5문항을 마친 세션만 저장됩니다.")
        return

    labels = {
        s["session_id"]: f"{s['date'][:16].replace('T', ' ')} · {s['initial_level']}→{s['final_level']} · 평균 {s['avg_grade']}"
        for s in sessions
    }
    sid = st.selectbox("세션 선택", list(labels), format_func=labels.get, key="history_pick")
    record = load_session(sid, history_dir)
    render_summary(record["summary"])
    for change in record.get("level_history") or []:
        st.caption(f"{change['after_item']}문항 후 난이도 변경: {change['from']} → {change['to']}")
    for i, item in enumerate(record["items"], 1):
        with st.expander(f"문항 {i} · {item['grade']} · {item['question']}"):
            st.markdown("**내 답변**")
            st.write(item["answer"])
            render_item_feedback(item)


def main() -> None:
    st.set_page_config(page_title="OPIc 텍스트 연습", page_icon="🗣️", layout="centered")
    page = sidebar()
    if page == "연습":
        practice_page()
    else:
        history_page()


main()
