import logging
import re
from typing import Dict, List

import pdfplumber

logger = logging.getLogger(__name__)

OPTION_RE = re.compile(r"^([A-Da-d])\)\s+(.*)$")
ANSWER_RE = re.compile(r"^Answer:\s*([A-Da-d])\b")


def _extract_text(filepath: str) -> str:
    text_parts: List[str] = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def parse_mcqs_from_pdf(filepath: str) -> List[Dict]:
    text = _extract_text(filepath)
    if not text.strip():
        return []

    blocks = re.split(r"(?m)^\s*\d+\.\s+", text)
    if blocks:
        blocks = blocks[1:]

    questions: List[Dict] = []

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        question_text = lines[0]
        if not question_text:
            continue

        options: List[str] = []
        option_letters: List[str] = []
        correct_index = None
        answer_letter = None

        for line in lines[1:]:
            answer_match = ANSWER_RE.match(line)
            if answer_match:
                answer_letter = answer_match.group(1).upper()
                continue

            option_match = OPTION_RE.match(line)
            if option_match:
                letter = option_match.group(1).upper()
                option_text = option_match.group(2).strip()
                if option_text.endswith("*"):
                    option_text = option_text[:-1].strip()
                    correct_index = len(options)
                options.append(option_text)
                option_letters.append(letter)
                continue

        if answer_letter and correct_index is None:
            if answer_letter in option_letters:
                correct_index = option_letters.index(answer_letter)

        if len(options) < 2:
            continue
        if correct_index is None or correct_index >= len(options):
            continue

        questions.append(
            {
                "question": question_text,
                "options": options,
                "correct_index": correct_index,
            }
        )

    logger.info("Parsed %s questions from PDF", len(questions))
    return questions
