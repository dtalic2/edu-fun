#!/usr/bin/env python3
"""
edu-fun: An interactive educational quiz game.
Covers math, science, and general knowledge topics.
"""

import random
import sys


QUESTIONS = {
    "math": [
        {
            "question": "What is the value of π (pi) to 2 decimal places?",
            "options": ["3.14", "3.16", "3.12", "3.18"],
            "answer": 0,
            "explanation": "Pi (π) ≈ 3.14159..., rounded to 2 decimal places is 3.14.",
        },
        {
            "question": "What is 2^10?",
            "options": ["512", "1024", "2048", "256"],
            "answer": 1,
            "explanation": "2^10 = 2 × 2 × 2 × ... (10 times) = 1024.",
        },
        {
            "question": "What is the square root of 144?",
            "options": ["11", "12", "13", "14"],
            "answer": 1,
            "explanation": "12 × 12 = 144, so √144 = 12.",
        },
        {
            "question": "How many sides does a dodecagon have?",
            "options": ["10", "11", "12", "13"],
            "answer": 2,
            "explanation": "A dodecagon has 12 sides. 'Dodeca' is Greek for 12.",
        },
        {
            "question": "What is the sum of angles in a triangle?",
            "options": ["90°", "180°", "270°", "360°"],
            "answer": 1,
            "explanation": "The interior angles of any triangle always sum to 180°.",
        },
    ],
    "science": [
        {
            "question": "What is the chemical symbol for Gold?",
            "options": ["Go", "Gd", "Au", "Ag"],
            "answer": 2,
            "explanation": "Gold's symbol 'Au' comes from the Latin word 'Aurum'.",
        },
        {
            "question": "How many chromosomes do humans normally have?",
            "options": ["23", "44", "46", "48"],
            "answer": 2,
            "explanation": "Humans have 46 chromosomes arranged in 23 pairs.",
        },
        {
            "question": "What planet is closest to the Sun?",
            "options": ["Venus", "Earth", "Mercury", "Mars"],
            "answer": 2,
            "explanation": "Mercury is the closest planet to the Sun.",
        },
        {
            "question": "What is the speed of light (approx.) in km/s?",
            "options": ["200,000", "300,000", "400,000", "500,000"],
            "answer": 1,
            "explanation": "Light travels at approximately 299,792 km/s, often rounded to 300,000 km/s.",
        },
        {
            "question": "What is the powerhouse of the cell?",
            "options": ["Nucleus", "Ribosome", "Mitochondria", "Vacuole"],
            "answer": 2,
            "explanation": "The mitochondria produce ATP energy through cellular respiration.",
        },
    ],
    "general": [
        {
            "question": "How many continents are there on Earth?",
            "options": ["5", "6", "7", "8"],
            "answer": 2,
            "explanation": "Earth has 7 continents: Africa, Antarctica, Asia, Australia, Europe, North America, South America.",
        },
        {
            "question": "Which language has the most native speakers worldwide?",
            "options": ["English", "Spanish", "Hindi", "Mandarin Chinese"],
            "answer": 3,
            "explanation": "Mandarin Chinese has the most native speakers (~920 million).",
        },
        {
            "question": "In what year did World War II end?",
            "options": ["1943", "1944", "1945", "1946"],
            "answer": 2,
            "explanation": "World War II ended in 1945 with Germany surrendering in May and Japan in September.",
        },
        {
            "question": "What is the capital of Australia?",
            "options": ["Sydney", "Melbourne", "Brisbane", "Canberra"],
            "answer": 3,
            "explanation": "Canberra is the capital of Australia, chosen as a compromise between Sydney and Melbourne.",
        },
        {
            "question": "Who wrote 'Romeo and Juliet'?",
            "options": ["Charles Dickens", "William Shakespeare", "Jane Austen", "Mark Twain"],
            "answer": 1,
            "explanation": "Romeo and Juliet was written by William Shakespeare around 1594–1596.",
        },
    ],
}


def print_banner():
    print("\n" + "=" * 50)
    print("         Welcome to edu-fun Quiz Game!")
    print("=" * 50)
    print("Learn something new while having fun.\n")


def choose_category():
    categories = list(QUESTIONS.keys())
    print("Choose a category:")
    for i, cat in enumerate(categories, 1):
        print(f"  {i}. {cat.capitalize()}")
    print(f"  {len(categories) + 1}. Random mix")

    while True:
        try:
            choice = int(input("\nYour choice: ").strip())
            if 1 <= choice <= len(categories):
                return categories[choice - 1]
            elif choice == len(categories) + 1:
                return "random"
            else:
                print(f"Please enter a number between 1 and {len(categories) + 1}.")
        except ValueError:
            print("Please enter a valid number.")


def get_questions(category, count=5):
    if category == "random":
        all_q = [q for qs in QUESTIONS.values() for q in qs]
        return random.sample(all_q, min(count, len(all_q)))
    return random.sample(QUESTIONS[category], min(count, len(QUESTIONS[category])))


def ask_question(number, question_data):
    print(f"\nQuestion {number}: {question_data['question']}")
    for i, option in enumerate(question_data["options"]):
        print(f"  {chr(65 + i)}) {option}")

    while True:
        answer = input("\nYour answer (A/B/C/D): ").strip().upper()
        if answer in ("A", "B", "C", "D"):
            return ord(answer) - ord("A")
        print("Please enter A, B, C, or D.")


def run_quiz():
    print_banner()
    category = choose_category()
    questions = get_questions(category)

    score = 0
    total = len(questions)

    print(f"\nStarting {category.capitalize()} quiz with {total} questions!")
    print("-" * 50)

    for i, q in enumerate(questions, 1):
        user_answer = ask_question(i, q)
        correct = q["answer"]

        if user_answer == correct:
            print("  Correct! Well done!")
            score += 1
        else:
            correct_letter = chr(65 + correct)
            print(f"  Wrong. The correct answer was {correct_letter}) {q['options'][correct]}")

        print(f"  Explanation: {q['explanation']}")

    print("\n" + "=" * 50)
    print(f"Quiz complete! Your score: {score}/{total}")
    percentage = (score / total) * 100
    if percentage == 100:
        print("Perfect score! Outstanding!")
    elif percentage >= 80:
        print("Great job! You really know your stuff!")
    elif percentage >= 60:
        print("Good effort! Keep learning!")
    else:
        print("Keep studying — you'll get there!")
    print("=" * 50 + "\n")

    return score, total


def main():
    try:
        run_quiz()
        play_again = input("Play again? (y/n): ").strip().lower()
        if play_again == "y":
            main()
    except KeyboardInterrupt:
        print("\n\nThanks for playing edu-fun! Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
