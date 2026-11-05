"""공용 샘플 설문 (SurveyItem 목록). 주제 배정·검증·그래프 테스트에서 재사용한다."""


def _opts(*labels):
    return [{"label": label, "recommend": 0} for label in labels]


SURVEY_ITEMS = [
    {"id": "job-1", "topic": "직업", "kind": "profile", "question": "현재 귀하는 어느 분야에 종사하고 계십니까?",
     "options": _opts("사업/회사", "교사/교육자", "군복무", "일 경험 없음")},
    {"id": "home-1", "topic": "거주지", "kind": "profile", "question": "현재 어디에 살고 있나요?",
     "options": _opts("홀로 거주", "가족과 함께 거주", "친구와 함께 거주")},
    {"id": "leisure-1", "topic": "여가활동", "kind": "topic", "question": "여가 활동으로 무엇을 하나요?",
     "options": _opts("영화 보기", "공연 보기", "콘서트 보기", "카페 가기")},
    {"id": "hobby-1", "topic": "취미/관심사", "kind": "topic", "question": "어떤 취미가 있나요?",
     "options": _opts("음악 감상하기", "독서", "요리하기")},
    {"id": "sport-1", "topic": "운동", "kind": "topic", "question": "어떤 운동을 하나요?",
     "options": _opts("조깅", "걷기", "수영")},
]


def valid_answers(**overrides):
    answers = {
        "job-1": ["사업/회사"],
        "home-1": ["홀로 거주"],
        "leisure-1": ["영화 보기"],
        "hobby-1": ["독서"],
        "sport-1": ["조깅"],
    }
    answers.update(overrides)
    return answers
