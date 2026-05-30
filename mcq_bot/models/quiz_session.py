from dataclasses import dataclass
from typing import List, Optional


@dataclass
class QuizQuestion:
    question: str
    options: List[str]
    correct_index: int


@dataclass
class QuizSession:
    questions: List[QuizQuestion]
    current_index: int
    score: int
    timer_seconds: int
    total_questions: int
    answered_current: bool
    poll_message_id: Optional[int]
    poll_id: Optional[str]
    quiz_id: str
