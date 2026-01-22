#!/usr/bin/env python3
"""Direct test script for LLM Council backend - runs without frontend.

This script reads the question from 'question.txt' file and runs the council process.
Usage: python test_council.py [output_file.json]
Example: python test_council.py results.json
"""

import asyncio
import json
import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.council import run_full_council
from backend.config import COUNCIL_MODELS, CHAIRMAN_MODEL


async def test_council(user_query: str, output_file: str = None):
    """Run the council process and display results."""

    print("🚀 Starting LLM Council Test")
    print(f"📝 Query: {user_query}")
    print(f"👥 Council Models: {len(COUNCIL_MODELS)}")
    print(f"🎯 Chairman Model: {CHAIRMAN_MODEL}")
    print("-" * 50)

    try:
        # Run the full council process
        stage1_results, stage2_results, stage3_result, metadata = await run_full_council(user_query)

        # Display results
        print("\n📊 STAGE 1: Individual Responses")
        print("-" * 30)
        for i, result in enumerate(stage1_results, 1):
            print(f"\n{i}. {result['model']}:")
            print(f"   {result['response'][:200]}{'...' if len(result['response']) > 200 else ''}")

        print("\n📊 STAGE 2: Rankings")
        print("-" * 30)
        for i, result in enumerate(stage2_results, 1):
            print(f"\n{i}. {result['model']}:")
            print(f"   {result['ranking'][:300]}{'...' if len(result['ranking']) > 300 else ''}")

        print("\n📊 AGGREGATE RANKINGS")
        print("-" * 30)
        for ranking in metadata.get('aggregate_rankings', []):
            print(f"• {ranking['model']}: Average rank {ranking['average_rank']} (from {ranking['rankings_count']} rankings)")

        print("\n🎯 STAGE 3: Final Synthesis")
        print("-" * 30)
        print(f"Chairman ({stage3_result['model']}):")
        print(stage3_result['response'])

        # Save to file if requested
        if output_file:
            output_data = {
                "query": user_query,
                "stage1": stage1_results,
                "stage2": stage2_results,
                "stage3": stage3_result,
                "metadata": metadata
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            print(f"\n💾 Results saved to: {output_file}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main function."""
    # Read question from file
    question_file = "question.txt"
    try:
        with open(question_file, 'r', encoding='utf-8') as f:
            user_query = f.read().strip()
        if not user_query:
            print(f"❌ Error: {question_file} is empty")
            return
    except FileNotFoundError:
        print(f"❌ Error: {question_file} not found")
        print(f"Please create {question_file} with your question")
        return
    except Exception as e:
        print(f"❌ Error reading {question_file}: {e}")
        return

    # Optional output file from command line argument
    output_file = sys.argv[1] if len(sys.argv) > 1 else None

    await test_council(user_query, output_file)


if __name__ == "__main__":
    asyncio.run(main())