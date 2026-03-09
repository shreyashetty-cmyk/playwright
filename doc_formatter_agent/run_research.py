#!/usr/bin/env python3
"""
Run the research agent from project root. No need to cd into agent/.

Usage (from project root):
  python run_research.py "Climate change agriculture"
  python run_research.py "AI in warfare" --articles 5 --duckduckgo
"""
import os
import sys

# Project root = directory containing this script
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.join(PROJECT_ROOT, "agent")

if not os.path.isdir(AGENT_DIR):
    print("Error: agent/ directory not found.")
    sys.exit(1)

# Add agent to path and run research_agent
sys.path.insert(0, AGENT_DIR)
os.chdir(AGENT_DIR)

# Run research_agent.main() with same argv (except script name)
import research_agent
research_agent.main()
