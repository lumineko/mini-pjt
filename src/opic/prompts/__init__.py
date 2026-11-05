"""프롬프트 로더 (SERVICE §13 #3).

파일 형식 (`prompts/<name>.md`):
    ---
    id: scorer
    version: 1
    ---
    [system]
    ... ${변수} ...
    [user]
    ... ${변수} ...

- 머리말의 id·version을 읽어 `Prompt.ref`("id@version")로 호출 메타데이터에 넣는다. 프롬프트를 바꾸면 version을 올린다.
- 본문은 `[system]` / `[user]` 두 부분. 변수는 string.Template(`${name}`)로 채우며, 빠진 변수가 있으면 KeyError.
- 사용자 답변은 `wrap_answer()`로 `<answer>` 태그에 넣는다(답변 속 태그는 무력화해 격리를 깨지 못하게 함).
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parent
_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_SECTION = re.compile(r"^\[(system|user)\]\s*$", re.M)
_ANSWER_TAG = re.compile(r"<\s*/?\s*answer\s*>", re.I)


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    system: Template
    user: Template

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    @property
    def variables(self) -> set[str]:
        return set(self.system.get_identifiers()) | set(self.user.get_identifiers())

    def render(self, **values: object) -> tuple[str, str]:
        """(system, user) 문자열. 빠진 변수가 있으면 KeyError."""
        values = {k: str(v) for k, v in values.items()}
        return self.system.substitute(values), self.user.substitute(values)


def parse_prompt(text: str, source: str = "<text>") -> Prompt:
    m = _FRONT.match(text)
    if not m:
        raise ValueError(f"{source}: 머리말(---) 블록이 없습니다")
    header = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            header[key.strip()] = value.strip()
    if "id" not in header or "version" not in header:
        raise ValueError(f"{source}: 머리말에 id와 version이 필요합니다")
    try:
        version = int(header["version"])
    except ValueError as exc:
        raise ValueError(f"{source}: version은 정수여야 합니다: {header['version']!r}") from exc

    body = text[m.end():]
    parts = _SECTION.split(body)
    # split 결과: [앞부분, 'system', 내용, 'user', 내용]
    sections = dict(zip(parts[1::2], (p.strip("\n") for p in parts[2::2])))
    if set(sections) != {"system", "user"} or parts[1::2] != ["system", "user"]:
        raise ValueError(f"{source}: [system] 다음 [user] 순서로 두 부분이 있어야 합니다")
    return Prompt(id=header["id"], version=version, system=Template(sections["system"]), user=Template(sections["user"]))


@lru_cache(maxsize=16)
def load_prompt(name: str) -> Prompt:
    path = PROMPTS_DIR / f"{name}.md"
    prompt = parse_prompt(path.read_text(encoding="utf-8"), source=path.name)
    if prompt.id != name:
        raise ValueError(f"{path.name}: id({prompt.id})가 파일 이름과 다릅니다")
    return prompt


def wrap_answer(text: str) -> str:
    """답변을 <answer> 태그로 감싼다. 답변 안의 answer 태그는 지워 격리를 깨지 못하게 한다."""
    return f"<answer>\n{_ANSWER_TAG.sub('', text)}\n</answer>"
