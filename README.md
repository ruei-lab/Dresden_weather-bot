# Dresden_weather-bot

Project Overview
This repository contains the code and dataset for the Applied AI final project. It is a Telegram-based AI assistant designed to provide personalized, context-aware weather safety advice. To overcome the hallucination risks of pure Large Language Models in critical safety scenarios, this system implements a Two-Stage Hybrid Architecture. It combines a deterministic rule-based engine with Google's Gemini LLM to ensure 100% trigger accuracy for life-threatening conditions like black ice or high winds.

Key Features
  1.Hybrid AI Architecture: Integrates strict, physics-informed safety thresholds (the ACTIONS_DATASET) as a pre-filter before LLM generation.
  2.Scenario-Driven UI: Features a custom Telegram keyboard with persona-based quick actions (e.g., Driver condition assessment, Runner weather analysis) to reduce        user cognitive load and force context injection.
  3.Contextual LLM Reasoning: Gemini synthesizes raw meteorological data (via Open-Meteo) and active safety alerts into actionable, personalized user guidance.

Technology Stack
  1.Core Language: Python 3.x
  2.Generative AI: Google Gemini-2.5-flash
  3.Meteorological Data: Open-Meteo API
  4.User Interface: Telegram Bot API

Setup and Installation Instructions
To run this project locally, please follow these steps:
  1.Clone this repository to your local machine.
  2.Install the required Python dependencies:
  pip install -r requirements.txt
  3.Locate the .env.example file and rename it to .env.
  4.Open the .env file and insert your own TELEGRAM_BOT_TOKEN and GEMINI_API_KEY.
  5.Execute the main application:python main.py

Project Structure
  1.main.py: The core application logic, integrating the APIs and the Telegram interface.
  2.actions.py: Contains the deterministic rule engine and safety thresholds dataset.
  3..env.example: A template file for setting up local environment variables securely.
  4.requirements.txt: A list of all necessary Python packages.
