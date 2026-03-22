"""Tests for the edu-fun quiz application."""

import pytest
from unittest.mock import patch
from quiz import QUESTIONS, get_questions, ask_question, run_quiz


def test_questions_structure():
    """Each question has required fields and valid answer index."""
    for category, questions in QUESTIONS.items():
        for q in questions:
            assert "question" in q
            assert "options" in q
            assert "answer" in q
            assert "explanation" in q
            assert len(q["options"]) == 4
            assert 0 <= q["answer"] <= 3


def test_get_questions_by_category():
    for category in QUESTIONS:
        questions = get_questions(category)
        assert len(questions) <= len(QUESTIONS[category])
        for q in questions:
            assert q in QUESTIONS[category]


def test_get_questions_random_mix():
    questions = get_questions("random", count=5)
    assert len(questions) == 5
    all_questions = [q for qs in QUESTIONS.values() for q in qs]
    for q in questions:
        assert q in all_questions


def test_get_questions_count_limit():
    questions = get_questions("math", count=2)
    assert len(questions) == 2


def test_ask_question_correct(capsys):
    question_data = {
        "question": "What is 1 + 1?",
        "options": ["1", "2", "3", "4"],
        "answer": 1,
        "explanation": "1 + 1 = 2.",
    }
    with patch("builtins.input", return_value="B"):
        result = ask_question(1, question_data)
    assert result == 1


def test_ask_question_invalid_then_valid(capsys):
    question_data = {
        "question": "What is 1 + 1?",
        "options": ["1", "2", "3", "4"],
        "answer": 1,
        "explanation": "1 + 1 = 2.",
    }
    with patch("builtins.input", side_effect=["X", "Z", "B"]):
        result = ask_question(1, question_data)
    assert result == 1


def test_all_categories_present():
    assert "math" in QUESTIONS
    assert "science" in QUESTIONS
    assert "general" in QUESTIONS


def test_each_category_has_enough_questions():
    for category, questions in QUESTIONS.items():
        assert len(questions) >= 3, f"Category '{category}' needs at least 3 questions"


def test_run_quiz_full(capsys):
    """Simulate a complete quiz run with all correct answers."""
    category = "math"
    questions = QUESTIONS[category][:3]

    inputs = [
        "1",   # choose math category
    ] + [chr(65 + q["answer"]) for q in questions]

    with patch("quiz.get_questions", return_value=questions), \
         patch("builtins.input", side_effect=inputs):
        score, total = run_quiz()

    assert total == len(questions)
    assert score == total
